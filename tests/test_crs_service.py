import pytest
import shapely.geometry
from app.services.crs_service import CRSService


def test_normalize_crs():
    assert CRSService.normalize_crs("EPSG:4326") == "EPSG:4326"
    assert CRSService.normalize_crs(None) == "EPSG:4326"
    assert CRSService.normalize_crs("") == "EPSG:4326"
    assert CRSService.normalize_crs("unknown") == "EPSG:4326"


def test_utm_zone_calculation():
    # Bengaluru (12.97 N, 77.59 E) -> UTM Zone 43N (EPSG:32643)
    epsg_bengaluru = CRSService.get_utm_epsg_for_lat_lon(12.97, 77.59)
    assert epsg_bengaluru == "EPSG:32643"

    # Sydney (-33.86 S, 151.20 E) -> UTM Zone 56S (EPSG:32756)
    epsg_sydney = CRSService.get_utm_epsg_for_lat_lon(-33.86, 151.20)
    assert epsg_sydney == "EPSG:32756"

    # New York (40.71 N, -74.00 W) -> UTM Zone 18N (EPSG:32618)
    epsg_ny = CRSService.get_utm_epsg_for_lat_lon(40.71, -74.00)
    assert epsg_ny == "EPSG:32618"


def test_reproject_geometry_to_metric_system():
    # Create a polygon in geographic degrees
    poly = shapely.geometry.Polygon([
        (77.5900, 12.9700),
        (77.5950, 12.9700),
        (77.5950, 12.9750),
        (77.5900, 12.9750),
        (77.5900, 12.9700)
    ])

    proj_geom, proj_crs = CRSService.project_geometry_for_measurement(poly, source_crs="EPSG:4326")

    assert proj_crs == "EPSG:32643"
    assert proj_geom.is_valid
    # In UTM meters, coordinates should be large metric values (e.g., > 100,000 meters)
    assert proj_geom.centroid.x > 100_000
    assert proj_geom.centroid.y > 100_000
    # Area must be in square meters (approx ~304,000 m2) instead of square degrees (0.000025 deg2)
    assert proj_geom.area > 200_000
    assert proj_geom.area < 400_000
