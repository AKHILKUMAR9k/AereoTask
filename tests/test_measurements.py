import pytest
import shapely.geometry
from app.services.measurement_service import MeasurementService


def test_polygon_area_measurement():
    poly = shapely.geometry.Polygon([
        (77.5900, 12.9700),
        (77.5950, 12.9700),
        (77.5950, 12.9750),
        (77.5900, 12.9750),
        (77.5900, 12.9700)
    ])

    res = MeasurementService.calculate_measurement(poly, source_crs="EPSG:4326")

    assert res.measurement_type == "area"
    assert res.unit == "square_meters"
    assert res.projected_crs == "EPSG:32643"
    assert res.value is not None
    # Area in square meters must be ~304,000 m2
    assert 250_000 < res.value < 350_000
    assert "area_hectares" in res.details
    assert "area_sq_km" in res.details
    assert "perimeter_m" in res.details


def test_linestring_length_measurement():
    line = shapely.geometry.LineString([
        (77.5900, 12.9700),
        (77.5950, 12.9750)
    ])

    res = MeasurementService.calculate_measurement(line, source_crs="EPSG:4326")

    assert res.measurement_type == "length"
    assert res.unit == "meters"
    assert res.projected_crs == "EPSG:32643"
    assert res.value is not None
    # Distance is roughly 775 meters
    assert 600 < res.value < 900
    assert "length_km" in res.details


def test_point_graceful_handling():
    pt = shapely.geometry.Point(77.5925, 12.9725)

    res = MeasurementService.calculate_measurement(pt, source_crs="EPSG:4326")

    assert res.measurement_type is None
    assert res.value is None
    assert res.unit is None
    assert "message" in res.details


def test_multipolygon_measurement():
    p1 = shapely.geometry.Polygon([
        (77.590, 12.970), (77.592, 12.970), (77.592, 12.972), (77.590, 12.972), (77.590, 12.970)
    ])
    p2 = shapely.geometry.Polygon([
        (77.595, 12.975), (77.597, 12.975), (77.597, 12.977), (77.595, 12.977), (77.595, 12.975)
    ])
    multi_poly = shapely.geometry.MultiPolygon([p1, p2])

    res = MeasurementService.calculate_measurement(multi_poly, source_crs="EPSG:4326")

    assert res.measurement_type == "area"
    assert res.value is not None
    assert res.value > 0


def test_unsupported_geometry_graceful_handling():
    gc = shapely.geometry.GeometryCollection([
        shapely.geometry.Point(0, 0),
        shapely.geometry.LineString([(0, 0), (1, 1)])
    ])

    res = MeasurementService.calculate_measurement(gc, source_crs="EPSG:4326")

    assert res.measurement_type is None
    assert res.value is None
    assert "message" in res.details


def test_self_intersecting_polygon_auto_repair():
    # Bow-tie polygon (self-intersecting)
    bowtie = shapely.geometry.Polygon([
        (0.0, 0.0), (0.01, 0.01), (0.0, 0.01), (0.01, 0.0), (0.0, 0.0)
    ])
    assert not bowtie.is_valid

    res = MeasurementService.calculate_measurement(bowtie, source_crs="EPSG:4326")
    # Must not crash, should calculate repaired area
    assert res.measurement_type == "area"
    assert res.value is not None
    assert res.value > 0


def test_southern_hemisphere_reprojection():
    # Polygon near Sydney, Australia
    sydney_poly = shapely.geometry.Polygon([
        (151.20, -33.86), (151.21, -33.86), (151.21, -33.85), (151.20, -33.85), (151.20, -33.86)
    ])

    res = MeasurementService.calculate_measurement(sydney_poly, source_crs="EPSG:4326")
    assert res.projected_crs == "EPSG:32756"
    assert res.value > 0
