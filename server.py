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

def get_version() -> str:
    try:
        version_path = os.path.join(os.path.dirname(__file__), "public", "version.js")
        with open(version_path, "r", encoding="utf-8") as f:
            content = f.read()
            m = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", content)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "1.0.0"

app = FastAPI(title="Trail Mapper & GPX POI Injector Backend", version=get_version())

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

def guess_waypoint_symbol(name: str) -> str:
    name_lower = name.lower()
    
    # Food guessers
    if any(k in name_lower for k in ("ravit", "food", "repas", "restau", "cade", "brunch", "manger", "snack")):
        return "Food"
    
    # Water guessers
    if any(k in name_lower for k in ("eau", "water", "sourc", "fontaine", "peyreleau", "drink", "hydra")):
        return "Water Source"
        
    # Summit guessers
    if any(k in name_lower for k in ("sommet", "peak", "col", "mont", "aiguille", "tête", "tete", "crête", "crete", "dôme", "dome", "pouncho", "nez", "crest", "hill", "pass")):
        return "Summit"
        
    # Medical guessers
    if any(k in name_lower for k in ("secour", "medical", "aid", "croix", "red cross", "infirmerie", "doctor", "clinique")):
        return "Medical Facility"
        
    # Shelter guessers
    if any(k in name_lower for k in ("refuge", "chalet", "gîte", "gite", "shelter", "cabane", "auberge", "hut", "cabin")):
        return "Shelter"
        
    # Campsite guessers
    if any(k in name_lower for k in ("camp", "campsite", "camping", "bivouac")):
        return "Campsite"
        
    # Rest area / Restroom guessers
    if any(k in name_lower for k in ("toilet", "wc", "sanit", "restroom", "douche", "shower")):
        return "Toilet"
        
    # Danger guessers
    if any(k in name_lower for k in ("danger", "warning", "diffic", "risk", "attention", "caillou")):
        return "Danger"
        
    # Default fallback is Checkpoint instead of Residence (Generic Point)
    return "Checkpoint"

def parse_utmb_next_data(html: str) -> dict:
    """
    Parses the __NEXT_DATA__ script block from a UTMB Next.js page.
    Returns a dict with 'stations', 'gpx_link', and 'metadata' if successful, or None.
    """
    try:
        # Search for the script block
        match = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', html, re.S)
        if not match:
            return None
        
        data = json.loads(match.group(1))
        page_props = data.get("props", {}).get("pageProps", {})
        
        gpx_link = page_props.get("gpxUrl")
        track = page_props.get("track", {})
        points = track.get("points", [])
        
        if not points and not gpx_link:
            return None
            
        # Parse page metadata
        page_header = page_props.get("pageHeader", {})
        banner_stats = page_props.get("bannerStats", [])
        main_stats = page_props.get("mainStats", [])
        
        category = None
        running_stones = None
        direct_entry = None
        for ms in main_stats:
            if ms.get("name") == "categoryWorldSeries":
                category = ms.get("value")
            elif ms.get("name") == "runningStones":
                running_stones = ms.get("value")
            elif ms.get("name") == "directEntry":
                direct_entry = ms.get("value")
                
        logo_url = None
        race_logo = page_props.get("raceLogo", {})
        if race_logo:
            logo_img = race_logo.get("light") or race_logo.get("dark")
            if logo_img:
                pub_id = logo_img.get("publicId")
                fmt = logo_img.get("format", "png")
                if pub_id:
                    from urllib.parse import quote
                    logo_url = f"https://res.cloudinary.com/utmb-world/image/upload/f_auto,q_auto/{quote(pub_id)}.{fmt}"
        
        metadata = {
            "course_name": page_header.get("title") or "Custom Trail Race",
            "distance": None,
            "elevation": None,
            "start_location": None,
            "start_date": page_header.get("startDate"),
            "category": category,
            "running_stones": running_stones,
            "direct_entry": direct_entry,
            "logo_url": logo_url
        }
        
        for stat in banner_stats:
            name = stat.get("name")
            val = stat.get("value")
            postfix = stat.get("postfix") or ""
            if name == "distance":
                metadata["distance"] = f"{val} {postfix}".strip()
            elif name == "elevationGain":
                metadata["elevation"] = f"{val} {postfix} D+".strip()
            elif name == "startDate":
                metadata["start_date"] = val
            elif name == "startPlaceAndTime":
                metadata["start_location"] = val
                
        if not metadata["distance"] and track.get("distance"):
            metadata["distance"] = f"{track.get('distance') / 1000.0:.1f} km"
        if not metadata["elevation"] and track.get("gainElevation"):
            metadata["elevation"] = f"{track.get('gainElevation')} m D+"
            
        stations = []
        for idx, pt in enumerate(points):
            name = pt.get("name", f"Station {idx}")
            dist_m = pt.get("distance", 0.0)
            dist_val = dist_m / 1000.0  # Convert to km
            ele_val = pt.get("elevation", 0)
            
            # Map Garmin icon
            supplies = pt.get("supplies", "none")
            has_medical = pt.get("hasMedical", False)
            
            if has_medical:
                sym = "Medical Facility"
            elif supplies in ("food", "complete"):
                sym = "Food"
            elif supplies == "drink":
                sym = "Water Source"
            else:
                sym = guess_waypoint_symbol(name)
            
            stations.append({
                "id": f"scraped_{idx}",
                "name": name[:30],
                "dist": dist_val,
                "ele": ele_val,
                "icon": sym,
                "use": True,
                "lat": pt.get("lat"),
                "lon": pt.get("lon"),
                "time": pt.get("cutoff") or pt.get("slowest") or ""
            })
            
        return {
            "stations": stations,
            "gpx_link": gpx_link,
            "metadata": metadata
        }
    except Exception as e:
        print(f"Error parsing Next.js __NEXT_DATA__: {e}")
        return None

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

@app.post("/trail-mapper/api/merge")
async def merge_data(
    gpx_file: UploadFile = File(...),
    stations_json: str = Form(...),
    official_dist: float = Form(None),
    no_scale: bool = Form(False),
    shorten_names: bool = Form(False),
    char_limit: int = Form(15),
    add_elev: bool = Form(False),
    start_date: str = Form(None)
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
            start_date=start_date
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
