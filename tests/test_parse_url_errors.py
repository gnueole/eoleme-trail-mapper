"""The error contract of /api/parse-url and /api/download-gpx.

A third party's failure must never surface as a bare 500: the answer carries
{"error": {"code", "source", "upstream_status", "message"}}, the code says whose
fault it is, the message is safe to show, and the logs keep the upstream URL,
its status and the traceback. Each class of failure is mocked at safe_urlopen,
which every fetch goes through.
"""
import io
import json
import socket
import sys
import urllib.error

import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(app=server.app)

LIVETRAIL = "https://volvic.livetrail.net/"
LIVETRAIL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<d><courses><c id="VLV" n="Volvic Volcanic" nc="VVX" color="#000" sel="1" /></courses>
<points course="VLV"><pt idpt="0" n="Start" nc="Start" km="0" d="0" a="500" lon="3.0" lat="45.8" hp="" />
<pt idpt="1" n="Finish" nc="Finish" km="42" d="1800" a="500" lon="3.1" lat="45.9" hp="" /></points></d>"""


class _Response:
    """What safe_urlopen hands back: a context manager with read() and headers."""

    def __init__(self, payload, headers=None):
        self._payload = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.headers = headers or {}

    def read(self, *args):
        data, self._payload = self._payload, b""
        return data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _upstream(monkeypatch, outcome):
    """Makes every fetch raise `outcome` (an exception) or answer it (a string)."""
    seen = []

    def fake(req, *args, **kwargs):
        seen.append(getattr(req, "full_url", req))
        if isinstance(outcome, BaseException):
            raise outcome
        return _Response(outcome)

    monkeypatch.setattr(server, "safe_urlopen", fake)
    return seen


def _logs(monkeypatch, capsys):
    monkeypatch.setattr(server._handler, "stream", sys.stderr)
    return lambda: capsys.readouterr().err


def _http_error(status):
    return urllib.error.HTTPError("https://volvic.livetrail.net/parcours.php", status, "nope", {}, io.BytesIO(b""))


def _assert_contract(response, status, code, source=None):
    assert response.status_code == status
    body = response.json()
    err = body["error"]
    assert err["code"] == code
    assert err["source"] == source
    assert isinstance(err["message"], str) and err["message"]
    assert body["detail"] == err["message"]
    # Nothing internal leaks: no traceback, no path, no exception class
    text = json.dumps(body)
    for leak in ("Traceback", "/app/", "server.py", "Error:", "Exception"):
        assert leak not in text, leak
    return err


# --- the source answered 404: the incident of 2026-10-04 -------------------

def test_upstream_404_is_not_found_and_a_warning(monkeypatch, capsys):
    read = _logs(monkeypatch, capsys)
    seen = _upstream(monkeypatch, _http_error(404))

    response = client.post("/api/parse-url", json={"url": LIVETRAIL})

    err = _assert_contract(response, 404, "UPSTREAM_NOT_FOUND", source="livetrail")
    assert err["upstream_status"] == 404
    assert err["source_url"] == "https://volvic.livetrail.net/"
    assert seen == ["https://volvic.livetrail.net/parcours.php"]

    lines = read().splitlines()
    assert lines[0].startswith("WARNING:")
    assert "UPSTREAM_NOT_FOUND" in lines[0]
    assert "https://volvic.livetrail.net/parcours.php" in lines[0] and "404" in lines[0]
    assert any("HTTPError" in line for line in lines[1:]), "the traceback stays in the logs"


def test_upstream_5xx_is_unavailable(monkeypatch):
    _upstream(monkeypatch, _http_error(503))
    err = _assert_contract(client.post("/api/parse-url", json={"url": LIVETRAIL}), 502, "UPSTREAM_UNAVAILABLE", "livetrail")
    assert err["upstream_status"] == 503


@pytest.mark.parametrize("exc", [socket.timeout("timed out"), urllib.error.URLError(socket.timeout("timed out")), TimeoutError()])
def test_upstream_timeout(monkeypatch, exc):
    _upstream(monkeypatch, exc)
    err = _assert_contract(client.post("/api/parse-url", json={"url": LIVETRAIL}), 504, "UPSTREAM_TIMEOUT", "livetrail")
    assert err["upstream_status"] is None


def test_upstream_connection_refused(monkeypatch):
    _upstream(monkeypatch, urllib.error.URLError(ConnectionRefusedError(111, "refused")))
    _assert_contract(client.post("/api/parse-url", json={"url": LIVETRAIL}), 502, "UPSTREAM_UNAVAILABLE", "livetrail")


def test_upstream_dns_failure_is_unavailable_not_internal(monkeypatch):
    # safe_urlopen's own refusal when the host does not resolve
    _upstream(monkeypatch, ValueError("Failed to resolve host: [Errno -2] Name or service not known"))
    _assert_contract(client.post("/api/parse-url", json={"url": LIVETRAIL}), 502, "UPSTREAM_UNAVAILABLE", "livetrail")


def test_upstream_answered_garbage_is_format_changed(monkeypatch, capsys):
    read = _logs(monkeypatch, capsys)
    _upstream(monkeypatch, "<html><body>Maintenance</body></html>")
    err = _assert_contract(client.post("/api/parse-url", json={"url": LIVETRAIL}), 502, "UPSTREAM_FORMAT_CHANGED", "livetrail")
    assert err["upstream_status"] is None
    assert read().startswith("WARNING:")


def test_livetrail_still_works_when_the_source_answers(monkeypatch):
    _upstream(monkeypatch, LIVETRAIL_XML)
    response = client.post("/api/parse-url", json={"url": LIVETRAIL})
    assert response.status_code == 200
    assert response.json()["metadata"]["course_name"] == "Volvic Volcanic"
    assert len(response.json()["stations"]) == 2


# --- the user's URL -------------------------------------------------------

def test_invalid_url_is_the_callers_mistake(monkeypatch, capsys):
    read = _logs(monkeypatch, capsys)
    response = client.post("/api/parse-url", json={"url": "http://127.0.0.1/table"})
    err = _assert_contract(response, 400, "INVALID_URL")
    assert "SSRF" in err["message"]
    assert "answered" not in read(), "a 4xx is not logged"


def test_client_rendered_utmb_page_is_invalid_url_with_help(monkeypatch):
    html = '<html><body><script>self.__next_f.push([1,"3:I[41060,[],\\"\\"]\\n"])</script></body></html>'
    _upstream(monkeypatch, html)
    response = client.post("/api/parse-url", json={"url": "https://live.utmb.world/utmb/2026/ccc"})
    err = _assert_contract(response, 422, "INVALID_URL", source="utmb")
    assert "montblanc.utmb.world" in err["message"]


# --- ours -----------------------------------------------------------------

def test_internal_error_is_the_only_500_and_hides_its_cause(monkeypatch, capsys):
    read = _logs(monkeypatch, capsys)
    _upstream(monkeypatch, RuntimeError("secret internal detail /app/server.py"))
    response = client.post("/api/parse-url", json={"url": LIVETRAIL})
    err = _assert_contract(response, 500, "INTERNAL_ERROR")
    assert err["message"] == "Something went wrong on our side."
    lines = read().splitlines()
    assert lines[0].startswith("ERROR:") and "secret internal detail" in lines[0]
    assert any("RuntimeError" in line for line in lines[1:])


# --- /api/download-gpx goes through the same contract ---------------------

def test_download_gpx_livetrail_404(monkeypatch):
    _upstream(monkeypatch, _http_error(404))
    response = client.post("/api/download-gpx", json={"url": "https://volvic.livetrail.net/data/gmData_VLV.js"})
    err = _assert_contract(response, 404, "UPSTREAM_NOT_FOUND", "livetrail")
    assert err["upstream_status"] == 404


def test_download_gpx_livetrail_payload_without_track(monkeypatch):
    _upstream(monkeypatch, "var b_VLV = null;")
    _assert_contract(client.post("/api/download-gpx", json={"url": "https://volvic.livetrail.net/data/gmData_VLV.js"}),
                     502, "UPSTREAM_FORMAT_CHANGED", "livetrail")


def test_download_gpx_timeout_on_any_host(monkeypatch):
    _upstream(monkeypatch, socket.timeout("timed out"))
    _assert_contract(client.post("/api/download-gpx", json={"url": "https://example.org/route.gpx"}),
                     504, "UPSTREAM_TIMEOUT", "example.org")
