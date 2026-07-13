import pytest
import io
import json
from fastapi.testclient import TestClient
from server import app, is_safe_url

client = TestClient(app)

def test_is_safe_url():
    # Loopback/private IPs must be unsafe
    assert is_safe_url("http://127.0.0.1") is False
    assert is_safe_url("http://localhost") is False
    assert is_safe_url("http://192.168.1.1") is False
    assert is_safe_url("http://10.0.0.1") is False
    
    # Public domains must be safe
    assert is_safe_url("https://montblanc.utmb.world") is True
    assert is_safe_url("https://google.com") is True

def test_root_serves_html():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]

def test_old_trail_mapper_path_redirects():
    response = client.get("/trail-mapper", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "https://gpx.eole.me/"

    response2 = client.get("/trail-mapper/some-subpath/sub", follow_redirects=False)
    assert response2.status_code == 301
    assert response2.headers["location"] == "https://gpx.eole.me/"

def test_download_gpx_ssrf_protection():
    # Test that downloading from localhost is blocked
    response = client.post("/api/download-gpx", json={"url": "http://127.0.0.1/route.gpx"})
    assert response.status_code == 400
    assert "SSRF Protection" in response.json()["detail"]

def test_parse_url_ssrf_protection():
    # Test that parsing localhost URL is blocked
    response = client.post("/api/parse-url", json={"url": "http://localhost/table"})
    assert response.status_code == 400
    assert "SSRF Protection" in response.json()["detail"]

def test_merge_endpoint():
    # Mock GPX file to upload
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
        {"name": "Start Line", "dist": 0.0, "icon": "Flag, Red", "use": True},
        {"name": "Ravitaillement 1", "dist": 1.0, "icon": "Food", "use": True}
    ]
    
    # Upload parameters matching server expectation
    file_payload = {
        "gpx_file": ("test.gpx", mock_gpx.encode("utf-8"), "application/gpx+xml")
    }
    data_payload = {
        "stations_json": json.dumps(stations),
        "official_dist": "2.0",
        "no_scale": "true",
        "shorten_names": "true",
        "char_limit": "12",
        "add_elev": "true"
    }
    
    response = client.post(
        "/api/merge",
        files=file_payload,
        data=data_payload
    )
    
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert "garmin_gpx" in res_json
    assert "suunto_gpx" in res_json
    assert "garmin_tcx" in res_json
    
    # Check that "Ravitaillement 1" was successfully abbreviated and had elevation appended
    # in the generated XML files returned:
    assert "RAV 1 1100m" in res_json["garmin_gpx"]
    assert "RAV 1 1100m" in res_json["garmin_tcx"]

def test_parse_utmb_next_data():
    from server import parse_utmb_next_data
    mock_html = """
    <html>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "gpxUrl": "https://example.com/route.gpx",
              "track": {
                "points": [
                  {
                    "name": "Courmayeur (Start)",
                    "distance": 0,
                    "elevation": 1220,
                    "lat": 45.7915,
                    "lon": 6.9650,
                    "supplies": "none",
                    "hasMedical": false
                  },
                  {
                    "name": "Maison Vieille",
                    "distance": 6800,
                    "elevation": 1956,
                    "lat": 45.7831,
                    "lon": 6.9242,
                    "supplies": "food",
                    "hasMedical": false
                  },
                  {
                    "name": "Lac Combal",
                    "distance": 15000,
                    "elevation": 1968,
                    "lat": 45.7725,
                    "lon": 6.8624,
                    "supplies": "drink",
                    "hasMedical": true
                  }
                ]
              }
            }
          }
        }
        </script>
      </body>
    </html>
    """
    
    result = parse_utmb_next_data(mock_html)
    assert result is not None
    assert result["gpx_link"] == "https://example.com/route.gpx"
    stations = result["stations"]
    assert len(stations) == 3
    
    # Verify points mapping
    assert stations[0]["name"] == "Courmayeur (Start)"
    assert stations[0]["dist"] == 0.0
    assert stations[0]["ele"] == 1220
    assert stations[0]["icon"] == "Checkpoint"
    assert stations[0]["lat"] == 45.7915
    assert stations[0]["lon"] == 6.9650
    
    assert stations[1]["name"] == "Maison Vieille"
    assert stations[1]["dist"] == 6.8
    assert stations[1]["ele"] == 1956
    assert stations[1]["icon"] == "Food"
    
    # Medical facility takes priority over drink supply
    assert stations[2]["name"] == "Lac Combal"
    assert stations[2]["dist"] == 15.0
    assert stations[2]["ele"] == 1968
    assert stations[2]["icon"] == "Medical Facility"


def test_merge_endpoint_size_limit():
    large_gpx = "A" * (6 * 1024 * 1024)  # 6MB
    stations = []
    file_payload = {
        "gpx_file": ("test.gpx", large_gpx.encode("utf-8"), "application/gpx+xml")
    }
    data_payload = {
        "stations_json": json.dumps(stations),
        "official_dist": "2.0",
        "no_scale": "true",
        "shorten_names": "true",
        "char_limit": "12",
        "add_elev": "true"
    }
    response = client.post(
        "/api/merge",
        files=file_payload,
        data=data_payload
    )
    assert response.status_code == 400
    assert "File size exceeds the 5MB limit" in response.json()["detail"]


def test_safe_urlopen_protection():
    from utils.security import safe_urlopen
    # Unsafe local IP should raise ValueError
    with pytest.raises(ValueError) as exc:
        safe_urlopen("http://127.0.0.1/test.gpx")
    assert "Unsafe URL resolved to private/reserved IP address" in str(exc.value)

    with pytest.raises(ValueError) as exc2:
        safe_urlopen("http://localhost/test.gpx")
    assert "Unsafe URL" in str(exc2.value)

