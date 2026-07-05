#!/usr/bin/env python3
"""
Garmin Course Points Injector
Author: Éole <hi@eole.me> & Antigravity (AI Data Engineering Expert)

This utility automates the placement of Garmin course points / waypoints along a GPX track
for any outdoor race (trail, road, cycling). It generates:
1. A modified GPX file containing waypoints (<wpt>) with icons (Food, Water, Residence, etc.).
2. A TCX file containing native Course Points, which is the most reliable format for
   Garmin Fenix's "Up Ahead" (Suivant) screen.
"""

import argparse
import csv
import io
import urllib.request
import xml.etree.ElementTree as ET
import math
import os
import re
import unicodedata
from datetime import datetime, timedelta

# ==========================================
# 1. CONFIGURATION & PREDEFINED DATA
# ==========================================

# Default total distance of the race (in km)
# Used to scale GPX track distances to official distances.
DEFAULT_OFFICIAL_TOTAL_DISTANCE = 110.4

# Default aid station data (CDH 110k Val d'Aran sample data)
# Symbol mapping: "Water", "Food", "House" (Drop Bag life base), "Summit" (Peak/Pass)
DEFAULT_AID_STATIONS = [
    {"name": "Canejan", "dist": 5.7, "symbol": "Water"},
    {"name": "EraHoneria", "dist": 12.9, "symbol": "Food"},
    {"name": "M. Liat", "dist": 22.8, "symbol": "Checkpoint"},   # Mines de Liat - Checkpoint (no food/water)
    {"name": "Varrados", "dist": 28.9, "symbol": "Water"},      # Coth de Varrados
    {"name": "P. Urets", "dist": 37.4, "symbol": "Summit"},     # Port d'Urets peak/pass
    {"name": "Montgarri", "dist": 46.8, "symbol": "Food"},
    {"name": "Beret", "dist": 51.9, "symbol": "House"},        # Life Base / Drop Bag
    {"name": "Salardu", "dist": 60.8, "symbol": "Food"},
    {"name": "Tredos", "dist": 69.7, "symbol": "Food"},
    {"name": "Est. Obago", "dist": 76.4, "symbol": "Checkpoint"},  # Estanh Obago - Checkpoint (no food/water)
    {"name": "Colomers", "dist": 81.2, "symbol": "Water"},
    {"name": "M. Romies", "dist": 91.5, "symbol": "Water"},
    {"name": "Arties", "dist": 96.0, "symbol": "Food"},
    {"name": "Escunhau", "dist": 101.8, "symbol": "Water"},     # Stet Escunhau
    {"name": "M. Meddia", "dist": 103.7, "symbol": "Summit"},   # Tuc de Meddia peak/pass
]

# File defaults
AUTO_DETECT_INPUT = "CDH_2026.gpx" if os.path.exists("CDH_2026.gpx") else "route.gpx"

# ==========================================
# 2. UTILITY FUNCTIONS
# ==========================================

def haversine_km(lat1, lon1, lat2, lon2):
    """
    Computes the 2D geodesic distance between two GPS coordinates using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def clean_poi_name(name, max_len=10):
    """
    Cleans a string to be Garmin-compatible (ASCII only, no special characters or accents)
    and truncates it to prevent clipping on the watch screen (default max 10 characters).
    """
    nfkd_form = unicodedata.normalize('NFKD', name)
    ascii_only = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    cleaned = re.sub(r'[^a-zA-Z0-9\s\-\.]', '', ascii_only)
    cleaned = cleaned.strip()
    return cleaned[:max_len]

def get_namespace(tag):
    """
    Extracts the XML namespace prefix from a tag if present.
    """
    match = re.match(r'(\{.*\})', tag)
    return match.group(1) if match else ''

def download_file(url, local_path):
    """
    Downloads a file from a URL to a local path.
    """
    print(f"Downloading GPX from URL: {url} ...")
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        with open(local_path, 'wb') as f:
            f.write(response.read())
    print("Download completed.")

def fetch_aid_stations(url):
    """
    Fetches aid station data from a URL (JSON or CSV).
    Handles common column headers and parses cumulative distances.
    """
    print(f"Fetching aid stations from URL: {url} ...")
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
    
    # 1. Try parsing as JSON
    try:
        import json
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0:
            name_keys = ['name', 'nom', 'label', 'station', 'poi']
            dist_keys = ['dist', 'distance', 'km', 'cum_dist', 'cumulative_distance']
            sym_keys = ['symbol', 'sym', 'icon', 'type', 'category']
            
            stations = []
            for item in data:
                name_val = next((item[k] for k in name_keys if k in item), None)
                dist_val = next((item[k] for k in dist_keys if k in item), None)
                sym_val = next((item[k] for k in sym_keys if k in item), 'Checkpoint')
                
                if name_val is not None and dist_val is not None:
                    try:
                        dist_cleaned = float(re.sub(r'[^\d\.]', '', str(dist_val)))
                        stations.append({
                            "name": str(name_val),
                            "dist": dist_cleaned,
                            "symbol": str(sym_val)
                        })
                    except ValueError:
                        continue
            if stations:
                print(f"Successfully parsed JSON: found {len(stations)} stations.")
                return stations
    except Exception:
        pass
        
    # 2. Try parsing as CSV (handles Google Sheets public CSV export)
    try:
        f = io.StringIO(content)
        reader = csv.reader(f)
        rows = [r for r in reader if r]
        if len(rows) > 0:
            header = [h.strip().lower() for h in rows[0]]
            stations = []
            
            name_idx, dist_idx, sym_idx = -1, -1, -1
            name_fields = ['name', 'nom', 'label', 'station', 'poi', 'title']
            dist_fields = ['dist', 'distance', 'km', 'cum_dist', 'cumulative', 'cumulative_distance']
            sym_fields = ['symbol', 'sym', 'icon', 'type', 'category']
            
            for i, col in enumerate(header):
                if any(f in col for f in name_fields):
                    name_idx = i
                elif any(f in col for f in dist_fields):
                    dist_idx = i
                elif any(f in col for f in sym_fields):
                    sym_idx = i
            
            if name_idx == -1: name_idx = 0
            if dist_idx == -1: dist_idx = 1 if len(header) > 1 else 0
            if sym_idx == -1: sym_idx = 2 if len(header) > 2 else -1
            
            is_header = any(any(f in col for f in name_fields + dist_fields) for col in header)
            start_row = 1 if is_header else 0
            
            for r in rows[start_row:]:
                if len(r) <= max(name_idx, dist_idx):
                    continue
                name = r[name_idx].strip()
                try:
                    dist_str = re.sub(r'[^\d\.]', '', r[dist_idx])
                    dist = float(dist_str)
                except ValueError:
                    continue
                
                sym = "Checkpoint"
                if sym_idx != -1 and len(r) > sym_idx:
                    sym_val = r[sym_idx].strip()
                    if sym_val:
                        sym = sym_val
                
                stations.append({"name": name, "dist": dist, "symbol": sym})
                
            if len(stations) > 0:
                print(f"Successfully parsed CSV: found {len(stations)} stations.")
                return stations
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        
    raise ValueError("Failed to parse aid stations URL. Ensure it is a valid public CSV or JSON URL.")

# ==========================================
# 3. CORE PROCESSING LOGIC
# ==========================================

def process_gpx_and_stations_data(
    gpx_content_bytes,
    stations_source,
    official_dist=None,
    no_scale=False,
    generate_garmin=True,
    generate_suunto=True
):
    """
    Processes the raw GPX XML bytes and aid stations list.
    Returns a dict with GPX and TCX string/bytes payloads.
    """
    # Parse XML GPX File
    root = ET.fromstring(gpx_content_bytes)
    
    # Determine the namespace used in GPX
    ns = get_namespace(root.tag)
    
    # Register namespaces to write out cleanly
    ET.register_namespace('', 'http://www.topografix.com/GPX/1/1')
    ET.register_namespace('gpxtpx', 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1')
    ET.register_namespace('gpxx', 'http://www.garmin.com/xmlschemas/GpxExtensions/v3')
    
    # Extract trackpoints from trk -> trkseg -> trkpt
    trackpoints_elements = root.findall(f'.//{ns}trkpt')
    num_pts = len(trackpoints_elements)
    
    if num_pts == 0:
        raise ValueError("No trackpoints found in the GPX file.")
        
    # Calculate cumulative distance along GPX track
    track_points = []
    cumulative_distances = []
    total_gpx_distance = 0.0
    
    # Base timestamp if times are missing
    base_time = datetime(2026, 7, 3, 6, 0, 0)
    
    for idx, trkpt in enumerate(trackpoints_elements):
        lat = float(trkpt.attrib['lat'])
        lon = float(trkpt.attrib['lon'])
        
        # Read elevation
        ele_elem = trkpt.find(f'{ns}ele')
        ele = float(ele_elem.text) if ele_elem is not None else 0.0
        
        # Read time or synthesize
        time_elem = trkpt.find(f'{ns}time')
        if time_elem is not None and time_elem.text:
            time_str = time_elem.text
        else:
            time_str = (base_time + timedelta(seconds=idx * 15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
        if idx == 0:
            dist = 0.0
        else:
            prev = track_points[-1]
            dist = haversine_km(prev['lat'], prev['lon'], lat, lon)
            
        total_gpx_distance += dist
        cumulative_distances.append(total_gpx_distance)
        
        track_points.append({
            'lat': lat,
            'lon': lon,
            'ele': ele,
            'time': time_str,
            'dist': total_gpx_distance,
            'element': trkpt
        })
        
    # Prepare aid stations
    aid_stations = []
    for station in stations_source:
        aid_stations.append({
            'name': station['name'],
            'official_dist': station['dist'],
            'symbol': station['symbol']
        })

    # Determine official total distance
    if official_dist is None:
        official_dist = max(s['official_dist'] for s in aid_stations)
        
    if no_scale:
        scale_factor = 1.0
    else:
        scale_factor = total_gpx_distance / official_dist
    
    # Match aid stations to track coordinates
    matched_stations = []
    for station in aid_stations:
        calibrated_dist = station['official_dist'] * scale_factor
        
        best_idx = 0
        min_diff = float('inf')
        for i, dist in enumerate(cumulative_distances):
            diff = abs(dist - calibrated_dist)
            if diff < min_diff:
                min_diff = diff
                best_idx = i
                
        matched_pt = track_points[best_idx]
        
        matched_stations.append({
            'name': station['name'],
            'official_dist': station['official_dist'],
            'calibrated_dist': calibrated_dist,
            'matched_dist_gpx': matched_pt['dist'],
            'lat': matched_pt['lat'],
            'lon': matched_pt['lon'],
            'ele': matched_pt['ele'],
            'time': matched_pt['time'],
            'symbol': station['symbol'],
            'index': best_idx
        })
        
    results = {
        'matched_stations': matched_stations,
        'total_gpx_distance': total_gpx_distance,
        'track_points': track_points
    }

    # ==========================================
    # 4. EXPORT GPX (GARMIN COMPATIBLE)
    # ==========================================
    if generate_garmin:
        import copy
        garmin_root = copy.deepcopy(root)
        
        for wpt in list(garmin_root.findall(f'{ns}wpt')):
            garmin_root.remove(wpt)
            
        trk_elem = garmin_root.find(f'{ns}trk')
        trk_idx = list(garmin_root).index(trk_elem) if trk_elem is not None else 0
        
        gpx_sym_map = {
            'Water': 'Water',
            'Food': 'Food',
            'House': 'Residence',
            'Summit': 'Summit',
            'Checkpoint': 'Flag, Blue'
        }
        
        for station in matched_stations:
            wpt = ET.Element(f'{ns}wpt', lat=str(station['lat']), lon=str(station['lon']))
            
            ele = ET.SubElement(wpt, f'{ns}ele')
            ele.text = f"{station['ele']:.1f}"
            
            time_el = ET.SubElement(wpt, f'{ns}time')
            time_el.text = station['time']
            
            name = ET.SubElement(wpt, f'{ns}name')
            name.text = clean_poi_name(station['name'], max_len=10)
            
            sym = ET.SubElement(wpt, f'{ns}sym')
            sym.text = gpx_sym_map.get(station['symbol'], 'Waypoint')
            
            garmin_root.insert(trk_idx, wpt)
            trk_idx += 1
            
        results['garmin_gpx'] = ET.tostring(garmin_root, encoding='UTF-8', xml_declaration=True)
     
    # ==========================================
    # 5. EXPORT GPX (SUUNTO COMPATIBLE)
    # ==========================================
    if generate_suunto:
        import copy
        suunto_root = copy.deepcopy(root)
        
        for wpt in list(suunto_root.findall(f'{ns}wpt')):
            suunto_root.remove(wpt)
            
        trk_elem = suunto_root.find(f'{ns}trk')
        trk_idx = list(suunto_root).index(trk_elem) if trk_elem is not None else 0
        
        suunto_type_map = {
            'Water': 'Water',
            'Food': 'Food',
            'House': 'Hostel',
            'Summit': 'Hill',
            'Checkpoint': 'Crossroads'
        }
        
        for station in matched_stations:
            wpt = ET.Element(f'{ns}wpt', lat=str(station['lat']), lon=str(station['lon']))
            
            ele = ET.SubElement(wpt, f'{ns}ele')
            ele.text = f"{station['ele']:.1f}"
            
            time_el = ET.SubElement(wpt, f'{ns}time')
            time_el.text = station['time']
            
            name = ET.SubElement(wpt, f'{ns}name')
            name.text = clean_poi_name(station['name'], max_len=10)
            
            type_el = ET.SubElement(wpt, f'{ns}type')
            type_el.text = suunto_type_map.get(station['symbol'], 'Aid_station')
            
            suunto_root.insert(trk_idx, wpt)
            trk_idx += 1
            
        results['suunto_gpx'] = ET.tostring(suunto_root, encoding='UTF-8', xml_declaration=True)

    # ==========================================
    # 6. EXPORT TCX (GARMIN COMPATIBLE)
    # ==========================================
    if generate_garmin:
        tcx_type_map = {
            'Water': 'Water',
            'Food': 'Food',
            'House': 'First Aid',
            'Summit': 'Summit',
            'Checkpoint': 'Generic'
        }
        
        tcx_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<TrainingCenterDatabase',
            '  xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"',
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '  xsi:schemaLocation="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd">',
            '  <Courses>',
            '    <Course>',
            f'      <Name>{clean_poi_name("CourseRoute", max_len=15)}</Name>',
            '      <Lap>',
            '        <TotalTimeSeconds>0.0</TotalTimeSeconds>',
            f'        <DistanceMeters>{total_gpx_distance * 1000:.1f}</DistanceMeters>',
            '        <BeginPosition>',
            f'          <LatitudeDegrees>{track_points[0]["lat"]}</LatitudeDegrees>',
            f'          <LongitudeDegrees>{track_points[0]["lon"]}</LongitudeDegrees>',
            '        </BeginPosition>',
            '        <EndPosition>',
            f'          <LatitudeDegrees>{track_points[-1]["lat"]}</LatitudeDegrees>',
            f'          <LongitudeDegrees>{track_points[-1]["lon"]}</LongitudeDegrees>',
            '        </EndPosition>',
            '        <Intensity>Active</Intensity>',
            '      </Lap>',
            '      <Track>'
        ]
        
        for i, pt in enumerate(track_points):
            tcx_lines.append('        <Trackpoint>')
            tcx_lines.append(f'          <Time>{pt["time"]}</Time>')
            tcx_lines.append('          <Position>')
            tcx_lines.append(f'            <LatitudeDegrees>{pt["lat"]}</LatitudeDegrees>')
            tcx_lines.append(f'            <LongitudeDegrees>{pt["lon"]}</LongitudeDegrees>')
            tcx_lines.append('          </Position>')
            tcx_lines.append(f'          <AltitudeMeters>{pt["ele"]:.1f}</AltitudeMeters>')
            tcx_lines.append(f'          <DistanceMeters>{pt["dist"] * 1000.0:.2f}</DistanceMeters>')
            tcx_lines.append('        </Trackpoint>')
            
        tcx_lines.append('      </Track>')
        
        for station in matched_stations:
            tcx_type = tcx_type_map.get(station['symbol'], 'Generic')
            name_clean = clean_poi_name(station['name'], max_len=10)
            
            tcx_lines.append('      <CoursePoint>')
            tcx_lines.append(f'        <Name>{name_clean}</Name>')
            tcx_lines.append(f'        <Time>{station["time"]}</Time>')
            tcx_lines.append('        <Position>')
            tcx_lines.append(f'          <LatitudeDegrees>{station["lat"]}</LatitudeDegrees>')
            tcx_lines.append(f'          <LongitudeDegrees>{station["lon"]}</LongitudeDegrees>')
            tcx_lines.append('        </Position>')
            tcx_lines.append(f'        <PointType>{tcx_type}</PointType>')
            tcx_lines.append(f'        <Notes>CDH Ravito: {station["name"]} ({station["official_dist"]:.1f}k)</Notes>')
            tcx_lines.append('      </CoursePoint>')
            
        tcx_lines.extend([
            '    </Course>',
            '  </Courses>',
            '</TrainingCenterDatabase>'
        ])
        
        results['garmin_tcx'] = '\n'.join(tcx_lines)

    return results


def main():
    # Setup command line argument parser
    parser = argparse.ArgumentParser(
        description="Injects Garmin-compatible Course Points (TCX) and Waypoints (GPX) along a GPX track."
    )
    parser.add_argument(
        "-i", "--input",
        default=AUTO_DETECT_INPUT,
        help=f"Local input GPX file path (default: {AUTO_DETECT_INPUT})"
    )
    parser.add_argument(
        "--input-url",
        help="URL of the input GPX file to download directly from the web"
    )
    parser.add_argument(
        "-u", "--stations-url",
        help="URL of the aid stations data (public JSON or CSV/Google Sheets URL)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Base path/name for output files. Suffixes and extensions will be appended automatically."
    )
    parser.add_argument(
        "-g", "--garmin",
        action="store_true",
        help="Generate Garmin-compatible files (GPX with <sym> and TCX)"
    )
    parser.add_argument(
        "-s", "--suunto",
        action="store_true",
        help="Generate Suunto-compatible GPX file (with <type>)"
    )
    parser.add_argument(
        "-d", "--official-dist",
        type=float,
        help="Official course total distance in km. Defaults to the last aid station's distance if not provided."
    )
    parser.add_argument(
        "--no-scale",
        action="store_true",
        help="Disable proportional scaling calibration (match exact raw distances instead)"
    )
    args = parser.parse_args()

    # Determine which platforms to generate
    generate_garmin = args.garmin
    generate_suunto = args.suunto
    if not generate_garmin and not generate_suunto:
        generate_garmin = True
        generate_suunto = True

    # Resolve base output path dynamically
    if not args.output:
        base_name, _ = os.path.splitext(os.path.basename(args.input))
        args.output = f"{base_name}_with_aid_stations"

    print("=" * 60)
    print(" Garmin & Suunto Course Points Injector ")
    print("=" * 60)
    
    # Handle GPX download if URL is provided
    if args.input_url:
        temp_gpx = "temp_input.gpx"
        try:
            download_file(args.input_url, temp_gpx)
            args.input = temp_gpx
        except Exception as e:
            print(f"Error downloading input GPX file: {e}")
            return

    if not os.path.exists(args.input):
        print(f"Error: Input GPX file '{args.input}' not found.")
        return

    # Parse XML GPX File
    print(f"Reading '{args.input}'...")
    with open(args.input, 'rb') as f:
        gpx_content_bytes = f.read()

    # Load aid stations (from URL if provided, otherwise fallback to default CDH data)
    stations_source = DEFAULT_AID_STATIONS
    if args.stations_url:
        try:
            stations_source = fetch_aid_stations(args.stations_url)
        except Exception as e:
            print(f"Error: {e}")
            return

    print("\n--- Aid Stations Calibration & Merging ---")
    try:
        results = process_gpx_and_stations_data(
            gpx_content_bytes=gpx_content_bytes,
            stations_source=stations_source,
            official_dist=args.official_dist,
            no_scale=args.no_scale,
            generate_garmin=generate_garmin,
            generate_suunto=generate_suunto
        )
    except Exception as e:
        print(f"Error executing engine: {e}")
        return

    # Log matching info
    for station in results['matched_stations']:
        print(f"- {station['name']:<12}: target {station['official_dist']:>5.1f} km -> matched GPX {station['matched_dist_gpx']:>5.2f} km")

    # Write files
    if generate_garmin and 'garmin_gpx' in results:
        output_gpx_garmin = f"{args.output}_garmin.gpx"
        print(f"\nWriting Garmin GPX File: {output_gpx_garmin}...")
        with open(output_gpx_garmin, 'wb') as f:
            f.write(results['garmin_gpx'])
        print(f"Garmin GPX file successfully generated: {output_gpx_garmin}")

    if generate_suunto and 'suunto_gpx' in results:
        output_gpx_suunto = f"{args.output}_suunto.gpx"
        print(f"\nWriting Suunto GPX File: {output_gpx_suunto}...")
        with open(output_gpx_suunto, 'wb') as f:
            f.write(results['suunto_gpx'])
        print(f"Suunto GPX file successfully generated: {output_gpx_suunto}")

    if generate_garmin and 'garmin_tcx' in results:
        output_tcx_garmin = f"{args.output}_garmin.tcx"
        print(f"\nWriting Garmin TCX File: {output_tcx_garmin}...")
        with open(output_tcx_garmin, 'w', encoding='utf-8') as f:
            f.write(results['garmin_tcx'])
        print(f"Garmin TCX file successfully generated: {output_tcx_garmin}")
    
    # Clean up temporary GPX file if downloaded from URL
    if args.input_url and os.path.exists("temp_input.gpx"):
        try:
            os.remove("temp_input.gpx")
            print("Removed temporary downloaded GPX file.")
        except Exception as e:
            print(f"Warning: Could not remove temporary file: {e}")
            
    print("\nExecution complete! Ready to load on your GPS device.")
    print("=" * 60)

if __name__ == "__main__":
    main()

