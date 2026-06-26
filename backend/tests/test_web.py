"""Tests for the single-service SPA serving via create_app() factory.

The backend optionally mounts the built React SPA from a web dir so the API
and the frontend are served from the same origin (single Cloud Run service).
"""
from fastapi.testclient import TestClient

from app.main import create_app

INDEX_HTML = "<!doctype html><title>Void Ranger</title>"


def _write_spa(web_dir):
    web_dir.mkdir(parents=True, exist_ok=True)
    (web_dir / "index.html").write_text(INDEX_HTML)
    assets = web_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "app.js").write_text("console.log('hi');")


def test_spa_served_when_web_dir_exists(tmp_path):
    _write_spa(tmp_path)
    client = TestClient(create_app(web_dir=tmp_path))

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Void Ranger" in resp.text

    resp = client.get("/assets/app.js")
    assert resp.status_code == 200


def test_healthz(tmp_path):
    _write_spa(tmp_path)
    client = TestClient(create_app(web_dir=tmp_path))

    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_route_not_shadowed_by_spa(tmp_path):
    _write_spa(tmp_path)
    client = TestClient(create_app(web_dir=tmp_path))

    resp = client.get("/api/stars")
    # The API route handles this, not the SPA: never the index HTML.
    assert "Void Ranger" not in resp.text
    if resp.status_code == 200:
        # Real stars.json present -> JSON payload, not HTML.
        assert isinstance(resp.json(), (list, dict))


def test_no_spa_mounted_when_web_dir_missing(tmp_path):
    missing = tmp_path / "nope"
    client = TestClient(create_app(web_dir=missing))

    resp = client.get("/healthz")
    assert resp.status_code == 200

    resp = client.get("/")
    assert resp.status_code == 404
