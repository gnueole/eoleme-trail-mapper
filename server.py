import os
import socket
import ipaddress
import urllib.request
import json
import re
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import defusedxml.ElementTree as DET
from garmin_course_injector import process_gpx_and_stations_data

# Import split utility submodules
from utils.security import get_version, is_safe_url
from utils.parsers import guess_waypoint_symbol, parse_utmb_next_data, parse_livetrail_xml, convert_livetrail_js_to_gpx

app = FastAPI(title="Trail Mapper & GPX POI Injector Backend", version=get_version())

# Pydantic models for request bodies
class DownloadGpxRequest(BaseModel):
    url: str

class ParseUrlRequest(BaseModel):
    url: str

# Static files are mounted at root `/` at the end of the file, which automatically handles serving index.html on GET `/`

@app.get("/trail-mapper")
@app.get("/trail-mapper/{path:path}")
def redirect_old_trail_mapper_paths(request: Request):
    query_string = request.url.query
    url = "https://gpx.eole.me/"
    if query_string:
        url += f"?{query_string}"
    return RedirectResponse(url=url, status_code=301)

@app.post("/api/download-gpx")
def download_gpx(payload: DownloadGpxRequest):
    url = payload.url
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="URL is unsafe or resolved to a private network address (SSRF Protection).")
    
    parsed_url = urlparse(url)
    if 'livetrail.net' in parsed_url.netloc.lower() and ('/data/gmData_' in parsed_url.path or 'gmdata_' in parsed_url.path.lower()):
        m = re.search(r'gmData_([a-zA-Z0-9_-]+)\.js', url, re.I)
        if m:
            course_id = m.group(1)
            clean_url = re.sub(r'\.v\d+\.', '.', url, flags=re.I)
            try:
                req = urllib.request.Request(
                    clean_url,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    js_content = response.read().decode('utf-8', errors='replace')
                gpx_xml = convert_livetrail_js_to_gpx(js_content, course_id)
                if not gpx_xml:
                    raise HTTPException(status_code=400, detail="Failed to parse coordinate track array from LiveTrail JS payload.")
                return Response(content=gpx_xml, media_type="application/xml")
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(status_code=500, detail=f"Failed to fetch or parse LiveTrail JS data: {e}")

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

@app.post("/api/parse-url")
def parse_url(payload: ParseUrlRequest):
    url = payload.url
    if not is_safe_url(url):
        raise HTTPException(status_code=400, detail="URL is unsafe or resolved to a private network address (SSRF Protection).")
    
    parsed_url = urlparse(url)
    if 'livetrail.net' in parsed_url.netloc.lower():
        netloc = re.sub(r'\.v\d+\.', '.', parsed_url.netloc.lower())
        base_url = f"{parsed_url.scheme}://{netloc}"
        
        # Parse query params
        query_params = {}
        if parsed_url.query:
            for q in parsed_url.query.split('&'):
                if '=' in q:
                    k, v = q.split('=', 1)
                    query_params[k] = v
        course_id = query_params.get('course')
        
        parcours_url = f"{base_url}/parcours.php"
        if course_id:
            parcours_url += f"?course={course_id}"
            
        try:
            req = urllib.request.Request(
                parcours_url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_content = response.read().decode('utf-8', errors='replace')
                
            parsed_data = parse_livetrail_xml(xml_content, course_id)
            if parsed_data:
                actual_course_id = parsed_data["course_id"]
                return JSONResponse(content={
                    "stations": parsed_data["stations"],
                    "gpx_link": f"{base_url}/data/gmData_{actual_course_id}.js",
                    "metadata": {
                        "course_name": parsed_data["course_name"],
                        "distance": f"{parsed_data['total_distance']:.1f} km",
                        "elevation": f"{parsed_data['total_gain']} m D+",
                        "start_location": "LiveTrail",
                        "start_date": None,
                        "category": actual_course_id,
                        "running_stones": None,
                        "direct_entry": None,
                        "logo_url": f"{base_url}/im/favicon.png"
                    }
                })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch or parse LiveTrail course data: {e}")
    
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
            html = response.read().decode('utf-8', errors='replace')
            
        # Try to parse as Next.js __NEXT_DATA__
        next_data_parsed = parse_utmb_next_data(html)
        if next_data_parsed:
            return JSONResponse(content=next_data_parsed)
            
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
        # Initialize metadata block for non-NextJS pages
        metadata = {
            "course_name": "Custom Trail Race",
            "distance": None,
            "elevation": None,
            "start_location": None,
            "start_date": None
        }
        
        # Try to guess course name from title
        title_m = re.search(r'<title>(.*?)</title>', html, re.I)
        if title_m:
            clean_title = re.sub(r'\s+', ' ', title_m.group(1))
            metadata["course_name"] = clean_title.split('|')[0].split('-')[0].strip()

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
                    sym = guess_waypoint_symbol(name_val)
                        
                    stations.append({
                        "id": f"scraped_{idx}",
                        "name": name_val[:30],
                        "dist": dist_val,
                        "ele": 0,
                        "icon": sym,
                        "use": True
                    })
        
        # If no stations found via tables, run text-based regex parser fallback (e.g. for Templiers wordpress page)
        if not stations:
            # Strip HTML tags by replacing them with space
            text = re.sub(r'<[^>]*>', ' ', html)
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&#8211;', '–')
            text = text.replace('&#8217;', '’')
            text = re.sub(r'\s+', ' ', text)
            
            parsed_list = []
            
            # Regex 1: "Name : km Dist" or "Name - km Dist"
            pattern1 = r'([A-ZÀ-Ÿ][a-zA-ZÀ-ÿ\s\-\'\’]{2,30}?)\s*(?::|-|–|—|\s)\s*(?:km|km\s*:?\s*)\s*(\d+(?:[.,]\d+)?)\b'
            for match in re.finditer(pattern1, text):
                name = match.group(1).strip()
                dist_str = match.group(2).replace(',', '.')
                dist = float(dist_str)
                name = re.sub(r'^[\.\-\>\s\•]+', '', name).strip()
                if len(name) < 3 or "Départ" in name or "Distance" in name or "Dénivelé" in name:
                    continue
                if dist > 180:
                    continue
                parsed_list.append((name, dist))
                
            # Regex 2: "Name (km Dist)"
            pattern2 = r'([A-ZÀ-Ÿ][a-zA-ZÀ-ÿ\s\-\'\’]{2,30}?)\s*\(\s*(?:km\s*)?(\d+(?:[.,]\d+)?)\s*\)'
            for match in re.finditer(pattern2, text):
                name = match.group(1).strip()
                dist_str = match.group(2).replace(',', '.')
                dist = float(dist_str)
                name = re.sub(r'^[\.\-\>\s\•]+', '', name).strip()
                if len(name) < 3 or "Départ" in name or "Distance" in name or "Dénivelé" in name:
                    continue
                if dist > 180:
                    continue
                parsed_list.append((name, dist))
                
            # Deduplicate and sort
            unique_stations = {}
            for name, dist in parsed_list:
                name_clean = re.sub(r'\s+', ' ', name).strip()
                found_close = False
                for k_dist, k_name in list(unique_stations.items()):
                    if abs(k_dist - dist) < 0.3:
                        found_close = True
                        if len(name_clean) > len(k_name):
                            unique_stations[k_dist] = name_clean
                        break
                if not found_close:
                    unique_stations[dist] = name_clean
            
            # Map to expected output structure
            for idx, (dist, name) in enumerate(sorted(unique_stations.items())):
                sym = guess_waypoint_symbol(name)
                
                stations.append({
                    "id": f"parsed_text_{idx}",
                    "name": name[:30],
                    "dist": dist,
                    "ele": 0,
                    "icon": sym,
                    "use": True
                })
        
        # Populate distance from parsed stations if we have them
        if stations:
            max_parsed_dist = max(s["dist"] for s in stations)
            metadata["distance"] = f"{max_parsed_dist:.1f} km"
            
        return JSONResponse(content={
            "stations": stations,
            "gpx_link": gpx_link,
            "metadata": metadata
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse URL: {str(e)}")

@app.post("/api/merge")
async def merge_data(
    gpx_file: UploadFile = File(...),
    stations_json: str = Form(...),
    official_dist: float = Form(None),
    no_scale: bool = Form(False),
    shorten_names: bool = Form(False),
    char_limit: int = Form(15),
    add_elev: bool = Form(False),
    start_date: str = Form(None),
    unit: str = Form("km")
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
        symbol_map = {
            'Food': 'Food',
            'Water Source': 'Water',
            'Summit': 'Summit',
            'Medical Facility': 'First Aid',
            'Aid Station': 'Aid Station',
            'Toilet': 'Toilet',
            'Shower': 'Shower',
            'Campsite': 'Campsite',
            'Shelter': 'Shelter',
            'Rest Area': 'Rest Area',
            'Transition': 'Transition',
            'Danger': 'Danger',
            'Checkpoint': 'Checkpoint',
            'Residence': 'Residence'
        }
        
        mapped_stations = []
        for s in stations_list:
            if not s.get('use', True):
                continue
            icon = s.get('icon', 'Residence')
            mapped_stations.append({
                'name': s.get('name', 'Station'),
                'dist': float(s.get('dist', 0.0)),
                'symbol': symbol_map.get(icon, 'Checkpoint'),
                'time': s.get('time', '')
            })
            
        # Run processing engine
        results = process_gpx_and_stations_data(
            gpx_content_bytes=gpx_bytes,
            stations_source=mapped_stations,
            official_dist=official_dist,
            no_scale=no_scale,
            generate_garmin=True,
            generate_suunto=True,
            shorten_names=shorten_names,
            char_limit=char_limit,
            add_elev=add_elev,
            start_date=start_date,
            unit=unit
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

# Telemetry Payload Model
class TelemetryRequest(BaseModel):
    event_type: str
    user_id: str
    session_id: str
    locale: str
    theme: str
    payload: dict

@app.post("/api/telemetry")
async def receive_telemetry(data: TelemetryRequest):
    """
    Forwards event telemetry payloads to the configured n8n webhook URL.
    Bypasses execution if running in dev environment.
    """
    env = os.environ.get("DOPPLER_ENVIRONMENT", "prod")
    if env == "dev":
        return {"status": "skipped", "reason": "dev_environment"}
        
    n8n_url = os.environ.get("N8N_TRAIL_MAPPER_TELEMETRY_WEBHOOK_URL") or os.environ.get("N8N_TELEMETRY_WEBHOOK_URL")
    if not n8n_url:
        return {"status": "skipped", "reason": "webhook_not_configured"}

    try:
        req_payload = data.dict()
        req_data = json.dumps(req_payload).encode('utf-8')
        req = urllib.request.Request(
            n8n_url,
            data=req_data,
            headers={'Content-Type': 'application/json'}
        )
        # Timeout at 2 seconds so we don't block
        with urllib.request.urlopen(req, timeout=2) as response:
            pass
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Mount static files folder with cache validation control headers
class CacheControlledStaticFiles(StaticFiles):
    def __init__(self, *args, cache_control: str = "no-cache, must-revalidate", **kwargs):
        self.cache_control = cache_control
        super().__init__(*args, **kwargs)

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = self.cache_control
        return response

app.mount("/", CacheControlledStaticFiles(directory="public", html=True), name="public")
