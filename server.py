import os
import socket
import ipaddress
import urllib.request
import json
import re
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
import defusedxml.ElementTree as DET
from garmin_course_injector import process_gpx_and_stations_data

app = FastAPI(title="Trail Mapper & GPX POI Injector Backend")

# SSRF Guard helper
def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Prevent DNS rebinding and internal network requests by resolving the IP
        addr_info = socket.getaddrinfo(hostname, None)
        for addr in addr_info:
            ip_str = addr[4][0]
            ip = ipaddress.ip_address(ip_str)
            if (ip.is_private or 
                ip.is_loopback or 
                ip.is_multicast or 
                ip.is_reserved or 
                ip.is_link_local or
                ip.is_unspecified):
                return False
        return True
    except Exception:
        return False

# Pydantic models for request bodies
class DownloadGpxRequest(BaseModel):
    url: str

class ParseUrlRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    # Redirect base root to the subpath /trail-mapper/ to match orchestration
    return RedirectResponse(url="/trail-mapper/")

@app.post("/trail-mapper/api/download-gpx")
def download_gpx(payload: DownloadGpxRequest):
    url = payload.url
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="URL is unsafe or resolved to a private network address (SSRF Protection).")
    
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        # Timeout at 5 seconds, read in chunks to prevent zip bomb / infinite stream
        with urllib.request.urlopen(req, timeout=5) as response:
            content_type = response.headers.get('Content-Type', '')
            # Verify file size limit (5MB)
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="GPX file size exceeds the 5MB limit.")
            
            chunk_size = 1024 * 1024
            content = b""
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                content += chunk
                if len(content) > 5 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="GPX file size limit exceeded during transfer.")
            
            # Safe XML Validation
            try:
                DET.fromstring(content)
            except Exception as xml_err:
                raise HTTPException(status_code=400, detail=f"Invalid XML / GPX content: {xml_err}")
                
            return Response(content=content.decode('utf-8'), media_type="application/xml")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to download GPX file: {str(e)}")

@app.post("/trail-mapper/api/parse-url")
def parse_url(payload: ParseUrlRequest):
    url = payload.url
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="URL is unsafe or resolved to a private network address (SSRF Protection).")
    
    # If the user has an n8n webhook URL configured in environment, route through it
    n8n_url = os.environ.get("N8N_PARSER_WEBHOOK_URL")
    if n8n_url:
        try:
            req = urllib.request.Request(
                n8n_url,
                data=json.dumps({"url": url}).encode("utf-8"),
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                # Expecting an array of stations: [{"name": "...", "dist": 5.7, "symbol": "Water"}]
                return JSONResponse(content=res_data)
        except Exception as e:
            # Fallback to simple scraping / error
            pass
            
    # Native fallback: fetch HTML and run simple regex parsing
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        # Try to locate any GPX URL in the page to help the user
        gpx_link = None
        links = re.findall(r'href=["\']([^"\']+\.gpx)["\']', html, re.I)
        if links:
            gpx_link = links[0]
            if not gpx_link.startswith('http'):
                base = urlparse(url)
                gpx_link = f"{base.scheme}://{base.netloc}{gpx_link}"
        
        # Extract table rows
        # Very simple heuristic for aid station rows containing dist, name
        stations = []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
        for idx, r in enumerate(rows):
            cols = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
            if len(cols) >= 2:
                # Strip HTML tags
                col_texts = [re.sub(r'<[^>]*>', '', c).strip() for c in cols]
                
                # Check if one column is distance (contains km or float) and name
                dist_val = None
                name_val = None
                
                for txt in col_texts:
                    m = re.match(r'^\s*([\d\.,]+)\s*(?:km)?\s*$', txt, re.I)
                    if m:
                        dist_val = float(m.group(1).replace(',', '.'))
                    elif len(txt) > 2 and not name_val:
                        name_val = txt
                
                if name_val and dist_val is not None:
                    sym = "Checkpoint"
                    name_lower = name_val.lower()
                    if "ravit" in name_lower or "food" in name_lower:
                        sym = "Food"
                    elif "eau" in name_lower or "water" in name_lower:
                        sym = "Water"
                    elif "sommet" in name_lower or "peak" in name_lower or "col " in name_lower:
                        sym = "Summit"
                    elif "secour" in name_lower or "medical" in name_lower:
                        sym = "Medical"
                        
                    stations.append({
                        "id": f"scraped_{idx}",
                        "name": name_val[:30],
                        "dist": dist_val,
                        "ele": 0,
                        "icon": sym,
                        "use": True
                    })
        
        return JSONResponse(content={
            "stations": stations,
            "gpx_link": gpx_link
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse URL: {str(e)}")

@app.post("/trail-mapper/api/merge")
async def merge_data(
    gpx_file: UploadFile = File(...),
    stations_json: str = Form(...),
    official_dist: float = Form(None),
    no_scale: bool = Form(False)
):
    try:
        # Load and validate stations json
        stations_list = json.loads(stations_json)
        
        # Read uploaded GPX bytes
        gpx_bytes = await gpx_file.read()
        
        # Safe XML Validation via defusedxml
        try:
            DET.fromstring(gpx_bytes)
        except Exception as xml_err:
            raise HTTPException(status_code=400, detail=f"Invalid XML in uploaded GPX: {str(xml_err)}")
        
        # Map frontend icon terms to backend symbols expected by garmin_course_injector.py
        # Frontend symbols: 'Food', 'Water Source', 'Summit', 'Danger', 'Medical Facility', 'Flag, Red', 'Flag, Blue', 'Residence'
        # Backend symbols: 'Water', 'Food', 'House', 'Summit', 'Checkpoint'
        symbol_map = {
            'Food': 'Food',
            'Water Source': 'Water',
            'Summit': 'Summit',
            'Medical Facility': 'House', # maps to First Aid / House
            'Residence': 'House',
            'Flag, Blue': 'Checkpoint',
            'Flag, Red': 'Checkpoint',
            'Danger': 'Checkpoint'
        }
        
        mapped_stations = []
        for s in stations_list:
            if not s.get('use', True):
                continue
            icon = s.get('icon', 'Residence')
            mapped_stations.append({
                'name': s.get('name', 'Station'),
                'dist': float(s.get('dist', 0.0)),
                'symbol': symbol_map.get(icon, 'Checkpoint')
            })
            
        # Run processing engine
        results = process_gpx_and_stations_data(
            gpx_content_bytes=gpx_bytes,
            stations_source=mapped_stations,
            official_dist=official_dist,
            no_scale=no_scale,
            generate_garmin=True,
            generate_suunto=True
        )
        
        # Return generated payloads as JSON
        # Frontend app.js will download them on demand
        return JSONResponse(content={
            "success": True,
            "garmin_gpx": results.get('garmin_gpx', b'').decode('utf-8'),
            "suunto_gpx": results.get('suunto_gpx', b'').decode('utf-8'),
            "garmin_tcx": results.get('garmin_tcx', '')
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

# Mount static files folder
app.mount("/trail-mapper", StaticFiles(directory="public", html=True), name="public")
