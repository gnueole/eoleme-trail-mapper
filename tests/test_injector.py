import pytest
import xml.etree.ElementTree as ET
from garmin_course_injector import (
    haversine_km,
    abbreviate_name,
    clean_poi_name,
    process_gpx_and_stations_data
)

def test_haversine_km():
    # Distance between Chamonix (45.9233, 6.8689) and Courmayeur (45.7915, 6.9650)
    # is roughly ~16.4 km
    dist = haversine_km(45.9233, 6.8689, 45.7915, 6.9650)
    assert 15.0 < dist < 18.0
    
    # Same point should be 0
    assert haversine_km(45.9233, 6.8689, 45.9233, 6.8689) == 0.0

def test_abbreviate_name():
    # Test French replacements
    assert abbreviate_name("Ravitaillement de Chamonix") == "RAV de Chamonix"
    assert abbreviate_name("point d'eau du Col") == "EAU du Col"
    assert abbreviate_name("Point d eau du refuge") == "EAU du REF"
    assert abbreviate_name("Sommet du Mont Blanc") == "SMT du Mont Blanc"
    assert abbreviate_name("Refuge de la Balme") == "REF de la Balme"
    assert abbreviate_name("Col de la Seigne") == "COL Seigne"
    assert abbreviate_name("Chalet du Truc") == "CHAL Truc"
    
    # Test English replacements
    assert abbreviate_name("Aid Station 1") == "AID 1"
    assert abbreviate_name("Water Point 2") == "WTR 2"
    assert abbreviate_name("Checkpoint Alpha") == "CP Alpha"
    assert abbreviate_name("Start line") == "STR line"
    assert abbreviate_name("Finish line") == "FNS line"

def test_clean_poi_name():
    # Standard cleaning (accents removed, characters sanitized, truncated to 10 by default)
    assert clean_poi_name("Ravitaillement éóàü", max_len=10) == "Ravitaille"
    
    # With shortening
    assert clean_poi_name("Ravitaillement", max_len=10, shorten_names=True) == "RAV"
    
    # Shortening and character limit
    assert clean_poi_name("Ravitaillement de Chamonix", max_len=15, shorten_names=True) == "RAV de Chamonix"[:15]
    
    # Adding elevation suffix
    assert clean_poi_name("La Gittaz", max_len=15, add_elev=True, ele=1660.4) == "La Gittaz 1660m"
    
    # Combined shortening, elevation suffix, and character limit truncation
    # "Ravitaillement de Chamonix 1035m" ➔ "RAV de Chamonix 1035m" ➔ Truncated to 15 ➔ "RAV de Chamonix"
    assert clean_poi_name("Ravitaillement de Chamonix", max_len=15, shorten_names=True, add_elev=True, ele=1035) == "RAV de Chamonix"

def test_process_gpx_and_stations_data():
    mock_gpx = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Test Course</name>
    <trkseg>
      <trkpt lat="45.9233" lon="6.8689"><ele>1000.0</ele></trkpt>
      <trkpt lat="45.9300" lon="6.8750"><ele>1100.0</ele></trkpt>
      <trkpt lat="45.9400" lon="6.8850"><ele>1200.0</ele></trkpt>
    </trkseg>
  </trk>
</gpx>
"""
    stations = [
        {"name": "Start Line", "dist": 0.0, "symbol": "Checkpoint"},
        {"name": "Ravitaillement 1", "dist": 1.0, "symbol": "Food"},
        {"name": "Finish Line", "dist": 2.0, "symbol": "Checkpoint"}
    ]
    
    results = process_gpx_and_stations_data(
        gpx_content_bytes=mock_gpx.encode('utf-8'),
        stations_source=stations,
        official_dist=2.0,
        no_scale=True,
        generate_garmin=True,
        generate_suunto=True,
        shorten_names=True,
        char_limit=12,
        add_elev=True
    )
    
    assert "garmin_gpx" in results
    assert "suunto_gpx" in results
    assert "garmin_tcx" in results
    
    # 1. Inspect Garmin GPX output
    garmin_xml = ET.fromstring(results['garmin_gpx'])
    ns = '{http://www.topografix.com/GPX/1/1}'
    wpts = garmin_xml.findall(f'{ns}wpt')
    assert len(wpts) == 3
    
    # Verify name cleaning/abbreviation/elevation suffix:
    # "Ravitaillement 1" ➔ "RAV 1 1200m" (snapped to last point ele=1200m)
    names = [w.find(f'{ns}name').text for w in wpts]
    assert names[0] == "STR Line 100"
    assert names[1] == "RAV 1 1100m"
    
    # 2. Inspect Suunto GPX output
    suunto_xml = ET.fromstring(results['suunto_gpx'])
    wpts_suunto = suunto_xml.findall(f'{ns}wpt')
    assert len(wpts_suunto) == 3
    assert wpts_suunto[1].find(f'{ns}type').text == "Food"
    
    # 3. Inspect Garmin TCX output
    tcx_str = results['garmin_tcx']
    assert "<CoursePoint>" in tcx_str
    assert "<Name>RAV 1 1100m</Name>" in tcx_str
