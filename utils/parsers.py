import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, quote

# Dictionary mapping Garmin course point symbols to lists of name keywords.
# To add a new symbol/theme, simply insert it into this mapping.
SYMBOL_KEYWORDS = {
    "Food": ("ravit", "food", "repas", "restau", "cade", "brunch", "manger", "snack"),
    "Water Source": ("eau", "water", "sourc", "fontaine", "peyreleau", "drink", "hydra"),
    "Summit": ("sommet", "peak", "col", "mont", "aiguille", "tête", "tete", "crête", "crete", "dôme", "dome", "pouncho", "nez", "crest", "hill", "pass"),
    "Medical Facility": ("secour", "medical", "aid", "croix", "red cross", "infirmerie", "doctor", "clinique"),
    "Shelter": ("refuge", "chalet", "gîte", "gite", "shelter", "cabane", "auberge", "hut", "cabin"),
    "Campsite": ("camp", "campsite", "camping", "bivouac"),
    "Toilet": ("toilet", "wc", "sanit", "restroom", "douche", "shower"),
    "Danger": ("danger", "warning", "diffic", "risk", "attention", "caillou"),
}

def guess_waypoint_symbol(name: str) -> str:
    """
    Scans a waypoint name to guess its Garmin symbol type using keyword mappings.
    Returns the mapped symbol, or 'Checkpoint' (default fallback).
    """
    name_lower = name.lower()
    for symbol, keywords in SYMBOL_KEYWORDS.items():
        if any(k in name_lower for k in keywords):
            return symbol
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
        
        stat_keys = {
            "categoryWorldSeries": "category",
            "runningStones": "running_stones",
            "directEntry": "direct_entry",
        }
        for ms in main_stats:
            name = ms.get("name")
            if name in stat_keys:
                val = ms.get("value")
                if stat_keys[name] == "category":
                    category = val
                elif stat_keys[name] == "running_stones":
                    running_stones = val
                elif stat_keys[name] == "direct_entry":
                    direct_entry = val
                 
        logo_url = None
        race_logo = page_props.get("raceLogo", {})
        if race_logo:
            logo_img = race_logo.get("light") or race_logo.get("dark")
            if logo_img:
                pub_id = logo_img.get("publicId")
                fmt = logo_img.get("format", "png")
                if pub_id:
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

def parse_livetrail_xml(xml_content: str, course_id: str = None) -> dict:
    """
    Parses LiveTrail XML content (typically from parcours.php) to extract courses,
    aid stations/checkpoints, and course metadata.
    """
    try:
        root = ET.fromstring(xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content)
        
        # Get courses
        courses = []
        courses_el = root.find('courses')
        if courses_el is not None:
            for c in courses_el.findall('c'):
                courses.append({
                    "id": c.get('id'),
                    "n": c.get('n'),
                    "nc": c.get('nc'),
                    "color": c.get('color'),
                    "sel": c.get('sel')
                })
        
        if not courses:
            return None
            
        # Determine course ID to parse
        selected_course = None
        if course_id:
            # Match case-insensitive
            for c in courses:
                if c["id"].upper() == course_id.upper():
                    selected_course = c
                    break
        
        # Fallback to sel="1" or first course
        if not selected_course:
            for c in courses:
                if c.get("sel") == "1":
                    selected_course = c
                    break
            if not selected_course:
                selected_course = courses[0]
                
        actual_course_id = selected_course["id"]
        course_name = selected_course["n"]
        
        # Find points for this course
        points_el = root.find(f"./points[@course='{actual_course_id}']")
        if points_el is None:
            # Try matching any points container
            points_el = root.find("./points")
            if points_el is None:
                return None
                
        stations = []
        max_dist = 0.0
        max_gain = 0
        
        for idx, pt in enumerate(points_el.findall('pt')):
            name = pt.get('n') or pt.get('nc') or f"Station {idx}"
            dist_val = float(pt.get('km', 0.0))
            ele_val = float(pt.get('a', 0.0))
            gain_val = int(pt.get('d', 0))
            lat = float(pt.get('lat', 0.0))
            lon = float(pt.get('lon', 0.0))
            time_val = pt.get('hp') or pt.get('hd') or ""
            
            if dist_val > max_dist:
                max_dist = dist_val
            if gain_val > max_gain:
                max_gain = gain_val
                
            sym = guess_waypoint_symbol(name)
            
            stations.append({
                "id": f"scraped_{actual_course_id}_{idx}",
                "name": name[:30],
                "dist": dist_val,
                "ele": ele_val,
                "icon": sym,
                "use": True,
                "lat": lat,
                "lon": lon,
                "time": time_val
            })
            
        return {
            "course_id": actual_course_id,
            "course_name": course_name,
            "total_distance": max_dist,
            "total_gain": max_gain,
            "stations": stations
        }
    except Exception as e:
        print(f"Error parsing LiveTrail XML: {e}")
        return None

def convert_livetrail_js_to_gpx(js_content: str, course_id: str) -> str:
    """
    Extracts p_<course_id> track coordinate arrays from LiveTrail data JS
    and constructs a standard GPX file.
    """
    try:
        # Regex to find p_<course_id>[idx] = [lat, lon]
        pattern = r'p_' + re.escape(course_id) + r'\[(\d+)\]\s*=\s*\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]'
        matches = re.findall(pattern, js_content)
        
        if not matches:
            # Try case insensitive fallback
            pattern_ci = r'p_' + re.escape(course_id) + r'\[(\d+)\]\s*=\s*\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]'
            matches = re.findall(pattern_ci, js_content, re.I)
            
        if not matches:
            # Try finding any coordinate array pattern
            pattern_any = r'p_[a-zA-Z0-9_]+\[(\d+)\]\s*=\s*\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]'
            matches = re.findall(pattern_any, js_content)
            
        if not matches:
            return None
            
        pts = sorted([(int(idx), float(lat), float(lon)) for idx, lat, lon in matches], key=lambda x: x[0])
        
        gpx_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="Trail Mapper" xmlns="http://www.topografix.com/GPX/1/1">',
            '  <metadata>',
            f'    <name>{course_id}</name>',
            '  </metadata>',
            '  <trk>',
            f'    <name>{course_id}</name>',
            '    <trkseg>'
        ]
        for _, lat, lon in pts:
            gpx_lines.append(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>')
        gpx_lines.extend([
            '    </trkseg>',
            '  </trk>',
            '</gpx>'
        ])
        return '\n'.join(gpx_lines)
    except Exception as e:
        print(f"Error converting LiveTrail JS to GPX: {e}")
        return None
