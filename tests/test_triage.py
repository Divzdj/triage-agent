from fastapi.testclient import TestClient
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app

client = TestClient(app)

def test_triage_happy_path():
    payload = {"description": "Checkout failing with 500 error on mobile when submitting payment."}
    r = client.post("/triage", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "category" in data
    assert "severity" in data
    assert "known_issue" in data
    assert "suggested_next_step" in data

def test_empty_description():
    r = client.post("/triage", json={"description": ""})
    assert r.status_code == 400
