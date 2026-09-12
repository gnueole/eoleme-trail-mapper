import pytest
import io
import json
import re
import socket
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


def test_guess_waypoint_symbol_matches_whole_words_only():
    """Keywords are stems, but must start on a word boundary, not mid-word."""
    from utils.parsers import guess_waypoint_symbol

    # Stems still match the longer words they were written for
    assert guess_waypoint_symbol("Ravitaillement 1") == "Food"
    assert guess_waypoint_symbol("Sources chaudes") == "Water Source"
    assert guess_waypoint_symbol("Secteur difficile") == "Danger"
    assert guess_waypoint_symbol("Sanitaires") == "Toilet"
    assert guess_waypoint_symbol("Point d'eau") == "Water Source"
    assert guess_waypoint_symbol("Mont Blanc") == "Summit"

    # ...but no longer fire from inside an unrelated word
    assert guess_waypoint_symbol("Plateau de la Justice") == "Checkpoint"
    assert guess_waypoint_symbol("Chateau Vieux") == "Checkpoint"
    assert guess_waypoint_symbol("Cascade") == "Checkpoint"
    assert guess_waypoint_symbol("Clermont") == "Checkpoint"


def test_merge_honours_start_date_utc_offset():
    """
    Course points are written with a Z suffix, so an offset-aware start has to
    be converted rather than truncated. UTMB itself publishes no offset, but a
    caller that supplies one must not be silently shifted by it.
    """
    aware = _merge_with_start_date("2026-09-26T08:00:00+02:00")
    assert aware[0] == "2026-09-26T06:00:00Z"

    # Z is equivalent to a naive value at the same wall clock
    assert _merge_with_start_date("2026-09-26T08:00:00Z")[0] == "2026-09-26T08:00:00Z"
    assert _merge_with_start_date("2026-09-26T08:00:00")[0] == "2026-09-26T08:00:00Z"


def test_parse_url_uses_ssrf_safe_fetch(monkeypatch):
    """The scrape fetch must go through safe_urlopen like every other fetch."""
    import server

    calls = []

    def _fail(*args, **kwargs):
        raise AssertionError("raw urlopen bypassed the SSRF guard")

    def _fake_safe(req, *args, **kwargs):
        calls.append(getattr(req, "full_url", req))
        raise ValueError("blocked in test")

    monkeypatch.setattr(server.urllib.request, "urlopen", _fail)
    monkeypatch.setattr(server, "safe_urlopen", _fake_safe)

    response = client.post("/api/parse-url", json={"url": "https://montblanc.utmb.world/races/utmb"})
    assert calls == ["https://montblanc.utmb.world/races/utmb"]
    assert response.status_code == 500


def test_trusted_domain_matching_is_not_a_bare_suffix():
    """
    "evilgoogle.com".endswith("google.com") is True, so the old suffix test gave
    the allow-list to anyone who registered such a name.
    """
    from utils.security import is_trusted_domain

    assert is_trusted_domain("utmb.world") is True
    assert is_trusted_domain("montblanc.utmb.world") is True
    assert is_trusted_domain("MONTBLANC.UTMB.WORLD") is True
    assert is_trusted_domain("github.com") is True

    assert is_trusted_domain("evilgoogle.com") is False
    assert is_trusted_domain("notutmb.world") is False
    assert is_trusted_domain("utmb.world.attacker.net") is False
    assert is_trusted_domain("") is False


def test_trusted_domain_still_validated_when_it_resolves(monkeypatch):
    """
    The allow-list is a fallback for unresolvable hosts, not a way to skip the
    IP check: a trusted name pointing at loopback must still be refused.
    """
    import utils.security as security

    def _resolve_to_loopback(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 0))]

    monkeypatch.setattr(security, "_original_getaddrinfo", _resolve_to_loopback)
    assert security.is_safe_url("https://montblanc.utmb.world/races/utmb") is False

    with pytest.raises(ValueError) as exc:
        security.safe_urlopen("https://montblanc.utmb.world/races/utmb")
    assert "private/reserved" in str(exc.value)


def test_untrusted_host_rejected_when_dns_fails(monkeypatch):
    """An unresolvable host gets the allow-list treatment only if it is on it."""
    import utils.security as security

    def _no_dns(host, port, *args, **kwargs):
        raise socket.gaierror("name resolution disabled")

    monkeypatch.setattr(security, "_original_getaddrinfo", _no_dns)
    assert security.is_safe_url("https://montblanc.utmb.world") is True
    assert security.is_safe_url("https://example.com") is False


def test_livetrail_js_handles_segmented_tracks():
    """
    LiveTrail writes the track flat, p_<id>[i], or split into legs,
    p_<id>[seg][i]. SaintéLyon's 160km is the second shape; matching only the
    flat form found no coordinates and failed the whole GPX download.
    """
    from utils.parsers import convert_livetrail_js_to_gpx

    flat = ('var p_Templi=[];'
            'p_Templi[0]=[44.11460,3.08683];p_Templi[1]=[44.11474,3.08690];')
    gpx = convert_livetrail_js_to_gpx(flat, "Templi")
    assert gpx.count("<trkpt") == 2
    assert 'lat="44.1146"' in gpx

    # Two legs, deliberately out of order in the source, must join end to end
    segmented = ('var p_160km=[];p_160km[1]=[];p_160km[2]=[];'
                 'p_160km[2][0]=[45.44444,4.44444];'
                 'p_160km[1][0]=[45.72979,4.82499];'
                 'p_160km[1][1]=[45.72982,4.82476];')
    gpx = convert_livetrail_js_to_gpx(segmented, "160km")
    assert gpx.count("<trkpt") == 3
    order = re.findall(r'lat="([\d.]+)"', gpx)
    assert order == ["45.72979", "45.72982", "45.44444"]


def test_livetrail_day_of_month_survives_a_multi_day_race():
    """
    'DD-HH:MM' carries the day but no month, and the old fallback could only
    ever roll over by one day — so a checkpoint two days in, at a time of day
    later than the start, collapsed back onto the start day.
    """
    from datetime import datetime
    from garmin_course_injector import livetrail_day_of_month, resolve_cutoff_time

    assert livetrail_day_of_month("30-05:09") == 30
    assert livetrail_day_of_month("19-05:10") == 19
    # Other formats must fall through to the weekday logic untouched
    assert livetrail_day_of_month("Fri 07:45 PM") is None
    assert livetrail_day_of_month("05:10") is None
    assert livetrail_day_of_month("") is None

    start = datetime(2026, 10, 19, 5, 10)
    # Without an offset the third day folds back onto the first
    assert resolve_cutoff_time("21-09:00", start) == datetime(2026, 10, 19, 9, 0)
    # Counting rollovers puts it where it belongs
    assert resolve_cutoff_time("21-09:00", start, day_offset=2) == datetime(2026, 10, 21, 9, 0)
    assert resolve_cutoff_time("20-08:00", start, day_offset=1) == datetime(2026, 10, 20, 8, 0)


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

