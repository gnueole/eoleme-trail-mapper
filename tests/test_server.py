import pytest
import io
import json
import re
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


def _merge_with_start_date(start_date):
    """Merges one course carrying a 'Sat 11:45 AM' cutoff, returns its CoursePoint times."""
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
        {"name": "Start Line", "dist": 0.0, "icon": "Flag, Red", "use": True, "time": ""},
        {"name": "Aid", "dist": 1.0, "icon": "Food", "use": True, "time": "Sat 11:45 AM"}
    ]
    data_payload = {
        "stations_json": json.dumps(stations),
        "official_dist": "2.0",
        "no_scale": "true",
        "char_limit": "12"
    }
    if start_date:
        data_payload["start_date"] = start_date

    response = client.post(
        "/api/merge",
        files={"gpx_file": ("test.gpx", mock_gpx.encode("utf-8"), "application/gpx+xml")},
        data=data_payload
    )
    assert response.status_code == 200
    return re.findall(r'<Time>([^<]+)</Time>', response.json()["garmin_tcx"])


def test_merge_honours_iso_start_date():
    """
    UTMB GPX files carry no <time>, so without an explicit start the injector
    falls back to a hardcoded Friday and every weekday cutoff lands on the wrong
    day. pageHeader.startDateIso is what the frontend now sends to prevent that.
    """
    # Nice 100K starts on a Saturday: the cutoff belongs to the start day itself.
    times = _merge_with_start_date("2026-09-26T08:00:00")
    assert times[0] == "2026-09-26T08:00:00Z"
    assert times[1] == "2026-09-26T11:45:00Z"

    # Same course with no start date: the Friday fallback pushes it a day out.
    fallback = _merge_with_start_date(None)
    assert fallback[1] == "2026-07-04T11:45:00Z"

def test_parse_utmb_next_data():
    from server import parse_utmb_next_data
    # Mirrors a current UTMB race page: attributes in Next.js' own order, a null
    # raceLogo with the event logo alongside it, and the none/drink/food/hotFood
    # supply vocabulary with hasMedical set on every staffed aid station.
    mock_html = """
    <html>
      <body>
        <script type="application/json" id="__NEXT_DATA__" crossorigin="">
        {
          "props": {
            "pageProps": {
              "gpxUrl": "https://example.com/route.gpx",
              "raceLogo": null,
              "event": {
                "siteLogo": {"publicId": "nice/logo_nice", "format": "png"}
              },
              "pageHeader": {
                "title": "Roubion - Nice - 100K",
                "startDate": "26th September 2026",
                "startDateIso": "2026-09-26T08:00:00"
              },
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
                    "hasMedical": true
                  },
                  {
                    "name": "Lac Combal",
                    "distance": 15000,
                    "elevation": 1968,
                    "lat": 45.7725,
                    "lon": 6.8624,
                    "supplies": "drink",
                    "hasMedical": true
                  },
                  {
                    "name": "Champex-Lac",
                    "distance": 20000,
                    "elevation": 1470,
                    "supplies": "hotFood",
                    "hasMedical": true
                  },
                  {
                    "name": "Brec d Utelle",
                    "distance": 25000,
                    "elevation": 1100,
                    "supplies": "none",
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
    assert len(stations) == 5

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

    # Supplies win over hasMedical, which UTMB now sets on every aid station
    assert stations[2]["icon"] == "Water Source"
    assert stations[3]["icon"] == "Food"
    # ...so a red cross is left for points that hand out nothing
    assert stations[4]["icon"] == "Medical Facility"

    # World Series races leave raceLogo null and carry the logo on the event
    assert result["metadata"]["logo_url"] == (
        "https://res.cloudinary.com/utmb-world/image/upload/f_auto,q_auto/nice/logo_nice.png"
    )
    assert result["metadata"]["course_name"] == "Roubion - Nice - 100K"

    # The race card keeps the human date; the injector needs the ISO one
    assert result["metadata"]["start_date"] == "26th September 2026"
    assert result["metadata"]["start_date_iso"] == "2026-09-26T08:00:00"


def test_parse_utmb_next_data_ignores_app_router_page():
    """live.utmb.world streams its payload into __next_f and holds no course."""
    from utils.parsers import is_client_rendered_next_page, parse_utmb_next_data

    app_router_html = (
        '<html><body><script>self.__next_f.push([1,"3:I[41060,[],\\"\\"]\\n"])'
        '</script></body></html>'
    )
    assert parse_utmb_next_data(app_router_html) is None
    assert is_client_rendered_next_page(app_router_html) is True
    assert is_client_rendered_next_page(
        '<script id="__NEXT_DATA__" type="application/json">{}</script>'
    ) is False


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

