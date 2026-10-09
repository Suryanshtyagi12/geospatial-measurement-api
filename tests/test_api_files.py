import os
import tempfile
import zipfile
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.parser import parse_geospatial_file
from tests.test_parser import create_dummy_shapefile

client = TestClient(app)

def create_valid_zip_in_memory():
    with tempfile.TemporaryDirectory() as td:
        create_dummy_shapefile(td, basename="test")
        zip_path = os.path.join(td, "archive.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                fpath = os.path.join(td, f"test{ext}")
                if os.path.exists(fpath):
                    zf.write(fpath, arcname=f"test{ext}")
        with open(zip_path, "rb") as f:
            return f.read()

def create_corrupt_zip_in_memory():
    return b"PK\x03\x04This is a corrupt zip file content"

def create_dummy_kml_in_memory():
    # Very minimal valid KML with one point
    kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Point</name>
      <Point>
        <coordinates>-122.0822035425683,37.42228990140251,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    return kml.encode('utf-8')

def test_upload_kml():
    kml_bytes = create_dummy_kml_in_memory()
    response = client.post("/api/files/", files={"file": ("test.kml", kml_bytes, "application/vnd.google-earth.kml+xml")})
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1
    assert "id" in data
    return data["id"]

def test_upload_shapefile_zip():
    zip_bytes = create_valid_zip_in_memory()
    response = client.post("/api/files/", files={"file": ("test.zip", zip_bytes, "application/zip")})
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1

def test_get_file():
    # Upload first
    file_id = test_upload_kml()
    response = client.get(f"/api/files/{file_id}/")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == file_id
    assert data["status"] == "COMPLETED"

def test_get_measurements():
    file_id = test_upload_kml()
    response = client.get(f"/api/files/{file_id}/measurements/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["features"]) == 1
    # Point should be NOT_REQUIRED
    assert data["features"][0]["measurement_status"] == "NOT_REQUIRED"

def test_unknown_id():
    response = client.get("/api/files/nonexistent-id/")
    assert response.status_code == 404

def test_bad_extension():
    response = client.post("/api/files/", files={"file": ("test.txt", b"hello", "text/plain")})
    assert response.status_code == 415

def test_corrupt_zip():
    bad_zip = create_corrupt_zip_in_memory()
    response = client.post("/api/files/", files={"file": ("test.zip", bad_zip, "application/zip")})
    # Pre-checks pass (extension .zip), but extraction/parsing fails -> 422
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "file_id" in data

def test_oversized_file(monkeypatch):
    # Mock settings to small size to trigger 413
    import app.config
    monkeypatch.setattr(app.config.settings, "max_upload_size_mb", 0) # 0 MB max
    response = client.post("/api/files/", files={"file": ("test.zip", b"some content", "application/zip")})
    assert response.status_code == 413
