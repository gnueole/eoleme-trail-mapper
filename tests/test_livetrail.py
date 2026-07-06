import pytest
from utils.parsers import parse_livetrail_xml, convert_livetrail_js_to_gpx
from server import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_parse_livetrail_xml():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <d>
        <courses>
            <c id="GRR" n="Diagonale des fous" nc="Diagonale des fous" color="#ffcd00" sel="1" />
            <c id="MAS" n="Mascareignes" nc="Mascareignes" color="#0c991f" />
        </courses>
        <points course="GRR">
            <pt idpt="0" n="St Pierre Ravine Blanche" nc="St Pierre" km="0" d="0" a="2" lon="55.459" lat="-21.339" hp="16-22:00" />
            <pt idpt="2" n="Domaine Vidot" nc="Dom Vidot" km="14.08" d="658" a="651" lon="55.545" lat="-21.312" hp="16-23:13" />
        </points>
    </d>
    """
    
    result = parse_livetrail_xml(mock_xml)
    assert result is not None
    assert result["course_id"] == "GRR"
    assert result["course_name"] == "Diagonale des fous"
    assert result["total_distance"] == 14.08
    assert result["total_gain"] == 658
    assert len(result["stations"]) == 2
    assert result["stations"][0]["name"] == "St Pierre Ravine Blanche"
    assert result["stations"][1]["dist"] == 14.08
    assert result["stations"][1]["ele"] == 651
    assert result["stations"][1]["icon"] == "Checkpoint"

def test_convert_livetrail_js_to_gpx():
    mock_js = """
    var b_GRR = null; var p_GRR=[];
    p_GRR[0]=[-21.33975,55.45966];
    p_GRR[1]=[-21.33986,55.45977];
    """
    
    gpx = convert_livetrail_js_to_gpx(mock_js, "GRR")
    assert gpx is not None
    assert '<trkpt lat="-21.33975" lon="55.45966"></trkpt>' in gpx
    assert '<trkpt lat="-21.33986" lon="55.45977"></trkpt>' in gpx
    assert '<name>GRR</name>' in gpx
