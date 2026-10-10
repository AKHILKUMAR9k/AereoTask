import pytest
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "geospatial_engine" in data


def test_upload_and_get_kml_flow(client):
    kml_path = SAMPLES_DIR / "sample_survey.kml"

    with open(kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_survey.kml", f, "application/vnd.google-earth.kml+xml")}
        )

    assert response.status_code == 201
    file_info = response.json()
    assert "id" in file_info
    assert file_info["filename"] == "sample_survey.kml"
    assert file_info["feature_count"] >= 3
    assert file_info["status"] == "COMPLETED"
    assert file_info["crs"] == "EPSG:4326"

    file_id = file_info["id"]

    # 1. Test GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    assert info_resp.json()["id"] == file_id

    # 2. Test GET /api/files/{id}/measurements/
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["id"] == file_id
    assert "summary" in meas_data
    assert len(meas_data["measurements"]) == file_info["feature_count"]

    # Check that polygon has area and linestring has length
    types = {m["geometry_type"] for m in meas_data["measurements"]}
    assert "Polygon" in types
    assert "LineString" in types
    assert "Point" in types

    for item in meas_data["measurements"]:
        if item["geometry_type"] == "Polygon":
            assert item["measurement_type"] == "area"
            assert item["unit"] == "square_meters"
            assert item["value"] > 0
            assert item["projected_crs"] is not None
        elif item["geometry_type"] == "LineString":
            assert item["measurement_type"] == "length"
            assert item["unit"] == "meters"
            assert item["value"] > 0
        elif item["geometry_type"] == "Point":
            assert item["measurement_type"] is None
            assert item["value"] is None

    # 3. Test GET /api/files/{id}/geojson/
    geo_resp = client.get(f"/api/files/{file_id}/geojson/")
    assert geo_resp.status_code == 200
    geo_data = geo_resp.json()
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) == file_info["feature_count"]


def test_upload_shapefile_zip_flow(client):
    shp_path = SAMPLES_DIR / "sample_shapefile.zip"

    with open(shp_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_shapefile.zip", f, "application/zip")}
        )

    assert response.status_code == 201
    file_info = response.json()
    assert file_info["filename"] == "sample_shapefile.zip"
    assert file_info["feature_count"] == 2
    assert file_info["status"] == "COMPLETED"

    # Test measurements
    meas_resp = client.get(f"/api/files/{file_info['id']}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["summary"]["total_area_sq_m"] > 0


def test_upload_invalid_extension(client):
    response = client.post(
        "/api/files/",
        files={"file": ("test.txt", b"Invalid content", "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_get_nonexistent_file(client):
    response = client.get("/api/files/nonexistent-id-999/")
    assert response.status_code == 404


def test_list_and_delete_files(client):
    kml_path = SAMPLES_DIR / "sample_survey.kml"

    with open(kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("to_delete.kml", f, "application/vnd.google-earth.kml+xml")}
        )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # Test list files
    list_resp = client.get("/api/files/?limit=10")
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()]
    assert file_id in ids

    # Test delete file
    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 200

    # Verify deleted
    get_resp = client.get(f"/api/files/{file_id}/")
    assert get_resp.status_code == 404
