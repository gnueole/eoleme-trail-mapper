import os
import logging
import socket
import ipaddress
import time
import urllib.request
import urllib.error
import json
import re
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import defusedxml.ElementTree as DET
from garmin_course_injector import process_gpx_and_stations_data

# Import split utility submodules
from utils.security import get_version, is_safe_url, safe_urlopen
from utils.parsers import (
    guess_waypoint_symbol,
    is_client_rendered_next_page,
    parse_utmb_next_data,
    parse_livetrail_xml,
    convert_livetrail_js_to_gpx,
)

# Wall-clock ceiling on a whole remote transfer, on top of the per-read socket
# timeout, so a slow-drip server cannot hold a worker open indefinitely.
MAX_TRANSFER_SECONDS = 30

app = FastAPI(title="Trail Mapper & GPX POI Injector Backend", version=get_version())


class _IndentedTracebackFormatter(logging.Formatter):
    """Indents every traceback line, so Vector merges the whole trace into the
    log line above it: its multiline rule treats a line starting with
    whitespace as a continuation. Python's own "Traceback (most recent call
    last):" header and final "ValueError: ..." line start at column 0, and
    would otherwise arrive in Axiom as separate events."""

    def formatException(self, ei):
        return "\n".join("  " + line for line in super().formatException(ei).splitlines())


_handler = logging.StreamHandler()
_handler.setFormatter(_IndentedTracebackFormatter("%(levelname)s:    %(message)s"))
logger = logging.getLogger("trail-mapper")
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class ApiError(HTTPException):
    """A failure the client can act on, answered as
    {"error": {"code", "source", "source_url", "upstream_status", "message"}}
    (plus "detail" = message, which older callers read).

    `code` tells the frontend what to say; `source` names the third party when
    the failure is theirs ("livetrail", "utmb", or the host); `upstream_status`
    is their HTTP status when there was one. `message` is safe to show: it never
    carries an exception text or a path. What caused it goes to the logs through
    the handler below, never to the response.
    """

    def __init__(self, status_code, code, message, source=None, upstream_status=None,
                 source_url=None, log_detail=None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.source = source
        self.upstream_status = upstream_status
        self.source_url = source_url
        # What the logs get instead of `message`: the upstream URL and status,
        # or the exception text for an internal error.
        self.log_detail = log_detail or message

    def body(self):
        return {
            "detail": self.detail,
            "error": {
                "code": self.code,
                "source": self.source,
                "source_url": self.source_url,
                "upstream_status": self.upstream_status,
                "message": self.detail,
            },
        }


def _source_of(url):
    """Names the third party behind a URL, for the error contract and the logs."""
    host = (urlparse(url).hostname or "").lower()
    if "livetrail.net" in host:
        return "livetrail"
    if "utmb.world" in host:
        return "utmb"
    return host or None


def _site_of(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/" if parsed.netloc else None


def upstream_error(exc, url, parsing=False):
    """Turns what a third-party fetch raised into an ApiError.

    The mapping is the contract the frontend relies on:
      - the source answered 404                 -> 404 UPSTREAM_NOT_FOUND
      - the source answered another error       -> 502 UPSTREAM_UNAVAILABLE
      - no answer: timeout                      -> 504 UPSTREAM_TIMEOUT
      - no answer: refused, unreachable, no DNS -> 502 UPSTREAM_UNAVAILABLE
      - an answer we could not read             -> 502 UPSTREAM_FORMAT_CHANGED
      - the URL itself is refused               -> 400 INVALID_URL
    Anything else is ours: 500 INTERNAL_ERROR, logged as an error with its
    traceback, where the upstream ones are warnings.
    """
    source = _source_of(url)
    kwargs = dict(source=source, source_url=_site_of(url))

    if parsing:
        return ApiError(502, "UPSTREAM_FORMAT_CHANGED",
                        "The source answered, but not in the format this tool expects.",
                        log_detail=f"{source} answered {url} with data that could not be parsed: {exc}",
                        **kwargs)
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code
        if status == 404:
            return ApiError(404, "UPSTREAM_NOT_FOUND", "The source has no data at this address.",
                            upstream_status=status, log_detail=f"{source} answered {status} for {url}",
                            **kwargs)
        return ApiError(502, "UPSTREAM_UNAVAILABLE", "The source answered with an error.",
                        upstream_status=status, log_detail=f"{source} answered {status} for {url}",
                        **kwargs)
    timed_out = isinstance(exc, (socket.timeout, TimeoutError)) or (
        isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (socket.timeout, TimeoutError)))
    if timed_out:
        return ApiError(504, "UPSTREAM_TIMEOUT", "The source did not answer in time.",
                        log_detail=f"{source} timed out for {url}: {exc}", **kwargs)
    if isinstance(exc, (urllib.error.URLError, ConnectionError, OSError)):
        return ApiError(502, "UPSTREAM_UNAVAILABLE", "The source could not be reached.",
                        log_detail=f"{source} unreachable for {url}: {exc}", **kwargs)
    if isinstance(exc, ValueError):
        # safe_urlopen refuses what it cannot vouch for
        text = str(exc).lower()
        if "resolve" in text:
            return ApiError(502, "UPSTREAM_UNAVAILABLE", "The source's address could not be resolved.",
                            log_detail=f"{source} did not resolve for {url}: {exc}", **kwargs)
        if "unsafe" in text or "scheme" in text or "hostname" in text:
            return ApiError(400, "INVALID_URL", "This URL cannot be fetched.",
                            log_detail=f"refused a URL: {exc}")
    # Ours. The submitted URL is deliberately left out of the log line.
    return ApiError(500, "INTERNAL_ERROR", "Something went wrong on our side.",
                    log_detail=f"{type(exc).__name__}: {exc}")


def fetch_upstream(req, timeout):
    """safe_urlopen with every failure translated by upstream_error. Returns the
    response; callers read it themselves, since what counts as a parse failure
    differs per endpoint."""
    url = req.full_url if isinstance(req, urllib.request.Request) else req
    try:
        return safe_urlopen(req, timeout=timeout)
    except ApiError:
        raise
    except Exception as exc:
        raise upstream_error(exc, url) from exc


@app.exception_handler(HTTPException)
async def log_server_errors(request: Request, exc: HTTPException):
    """Every 500 here is an HTTPException raised from an `except Exception`
    block, and uvicorn prints nothing but the access line: four 500s on
    /api/parse-url in September 2026 left no trace of what failed. The cause is
    the exception being handled when the HTTPException was raised.

    An ApiError is answered with its structured body. A third party's failure is
    a warning naming the upstream URL and status, so Axiom can group them by
    source; a failure of ours stays an error with its traceback. The submitted
    URL is not logged, only the upstream one an ApiError names."""
    cause = exc.__cause__ or exc.__context__
    exc_info = (type(cause), cause, cause.__traceback__) if cause else None
    is_api = isinstance(exc, ApiError)
    detail = exc.log_detail if is_api else exc.detail
    if is_api and exc.code.startswith("UPSTREAM_"):
        logger.warning("%s %s answered %d %s: %s", request.method, request.url.path,
                       exc.status_code, exc.code, detail, exc_info=exc_info)
    elif exc.status_code >= 500:
        logger.error("%s %s answered %d: %s", request.method, request.url.path,
                     exc.status_code, detail, exc_info=exc_info)
    if is_api:
        return JSONResponse(status_code=exc.status_code, content=exc.body())
    return await http_exception_handler(request, exc)

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
        raise ApiError(400, "INVALID_URL", "URL is unsafe or resolved to a private network address (SSRF Protection).")
    
    parsed_url = urlparse(url)
    if 'livetrail.net' in parsed_url.netloc.lower() and ('/data/gmData_' in parsed_url.path or 'gmdata_' in parsed_url.path.lower()):
        m = re.search(r'gmData_([a-zA-Z0-9_-]+)\.js', url, re.I)
        if m:
            course_id = m.group(1)
            clean_url = re.sub(r'\.v\d+\.', '.', url, flags=re.I)
            req = urllib.request.Request(clean_url, headers={'User-Agent': 'Mozilla/5.0'})
            with fetch_upstream(req, timeout=10) as response:
                js_content = response.read().decode('utf-8', errors='replace')
            try:
                gpx_xml = convert_livetrail_js_to_gpx(js_content, course_id)
            except Exception as e:
                raise upstream_error(e, clean_url, parsing=True) from e
            if not gpx_xml:
                raise upstream_error(ValueError("no coordinate track array in the JS payload"), clean_url, parsing=True)
            return Response(content=gpx_xml, media_type="application/xml")

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        # Timeout at 5 seconds, read in chunks to prevent zip bomb / infinite stream
        with fetch_upstream(req, timeout=5) as response:
            content_type = response.headers.get('Content-Type', '')
            # Verify file size limit (5MB)
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="GPX file size exceeds the 5MB limit.")
            
            # urllib's timeout is per socket operation, so a server dripping
            # bytes just inside it can hold the worker indefinitely. Bound the
            # whole transfer, not just each individual read.
            chunk_size = 1024 * 1024
            deadline = time.monotonic() + MAX_TRANSFER_SECONDS
            content = b""
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                content += chunk
                if len(content) > 5 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="GPX file size limit exceeded during transfer.")
                if time.monotonic() > deadline:
                    raise HTTPException(status_code=504, detail="GPX download exceeded the transfer time limit.")
            
            # Safe XML Validation
            try:
                DET.fromstring(content)
            except Exception as xml_err:
                raise HTTPException(status_code=400, detail=f"Invalid XML / GPX content: {xml_err}")
                
            return Response(content=content.decode('utf-8'), media_type="application/xml")
    except HTTPException:
        raise
    except Exception as e:
        raise ApiError(500, "INTERNAL_ERROR", "Something went wrong on our side.",
                       log_detail=f"Failed to download GPX file: {type(e).__name__}: {e}") from e

@app.post("/api/parse-url")
def parse_url(payload: ParseUrlRequest):
    url = payload.url
    if not is_safe_url(url):
        raise ApiError(400, "INVALID_URL", "URL is unsafe or resolved to a private network address (SSRF Protection).")
    
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
            
        # LiveTrail answers 404 on parcours.php when a race is not published (or
        # no longer is): that is their answer, not our failure, and the frontend
        # says so. A page that answers but holds no course is a format change.
        req = urllib.request.Request(parcours_url, headers={'User-Agent': 'Mozilla/5.0'})
        with fetch_upstream(req, timeout=10) as response:
            xml_content = response.read().decode('utf-8', errors='replace')
        try:
            parsed_data = parse_livetrail_xml(xml_content, course_id)
        except Exception as e:
            raise upstream_error(e, parcours_url, parsing=True) from e
        if not parsed_data:
            raise upstream_error(ValueError("no course found in parcours.php"), parcours_url, parsing=True)
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
                "start_date_iso": None,
                "category": actual_course_id,
                "running_stones": None,
                "direct_entry": None,
                "logo_url": f"{base_url}/im/favicon.png"
            }
        })
    
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
        with fetch_upstream(req, timeout=5) as response:
            html = response.read().decode('utf-8', errors='replace')
            
        # Try to parse as Next.js __NEXT_DATA__
        next_data_parsed = parse_utmb_next_data(html)
        if next_data_parsed:
            return JSONResponse(content=next_data_parsed)
            
        # live.utmb.world has moved to the Next.js App Router and loads its
        # courses from its own API, so the HTML holds no aid stations at all.
        # Say so instead of letting the generic scraper return an empty course.
        if 'utmb.world' in parsed_url.netloc.lower() and is_client_rendered_next_page(html):
            raise ApiError(
                422, "INVALID_URL",
                "This UTMB page renders its course in the browser, so it exposes no "
                "aid stations to fetch. Use the race page on the event site instead "
                "(e.g. https://montblanc.utmb.world/races/utmb).",
                source="utmb", source_url=_site_of(url),
            )
            
        # Try to locate any GPX URL in the page to help the user
        gpx_link = None
        links = re.findall(r'href=["\']([^"\']+\.gpx)["\']', html, re.I)
        if links:
            gpx_link = links[0]
            if not gpx_link.startswith('http'):
                base = urlparse(url)
                gpx_link = f"{base.scheme}://{base.netloc}{gpx_link}"
        
        # Initialize metadata block for non-NextJS pages
        metadata = {
            "course_name": "Custom Trail Race",
            "distance": None,
            "elevation": None,
            "start_location": None,
            "start_date": None,
            "start_date_iso": None
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
        
    except HTTPException:
        raise
    except Exception as e:
        raise ApiError(500, "INTERNAL_ERROR", "Something went wrong on our side.",
                       log_detail=f"Failed to parse URL: {type(e).__name__}: {e}") from e

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
        
        # Read the upload in bounded chunks and stop at the cap, rather than
        # reading the whole body first and measuring it afterwards — the limit
        # should bound what the process accepts, not just what the parser sees.
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB limit
        gpx_bytes = b""
        while True:
            chunk = await gpx_file.read(1024 * 1024)
            if not chunk:
                break
            gpx_bytes += chunk
            if len(gpx_bytes) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail="File size exceeds the 5MB limit.")
        
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
        
    except HTTPException as he:
        raise he
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
        
    # Vector, not n8n. The receiving workflow wrote to a Notion database and
    # failed on every event; Vector ships straight to the Axiom eole-telemetry
    # dataset. The fallback matters: this container received no environment at
    # all until 2026-08-28, so the call was skipped in silence, always.
    n8n_url = (os.environ.get("TELEMETRY_WEBHOOK_URL")
               or os.environ.get("N8N_TRAIL_MAPPER_TELEMETRY_WEBHOOK_URL")
               or "http://vector:8080")

    try:
        # The Axiom dashboards group by `application`.
        req_payload = {"application": "trail-mapper", "environment": env, **data.dict()}
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
