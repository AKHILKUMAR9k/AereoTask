import pytest
from pathlib import Path
from app.services.parser_service import ShapefileParser, KMLParser, GeospatialParserService

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_parse_sample_kml():
    kml_file = SAMPLES_DIR / "sample_survey.kml"
    assert kml_file.exists(), "Sample KML file missing"

    features, crs = KMLParser.parse_kml(kml_file)

    assert crs == "EPSG:4326"
    assert len(features) >= 3

    geom_types = [f.geometry_type for f in features]
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types

    # Check that properties/extended data was extracted
    names = [f.properties.get("name") for f in features]
    assert any("Parcel Alpha" in n for n in names if n)


def test_parse_sample_shapefile_zip():
    shp_zip = SAMPLES_DIR / "sample_shapefile.zip"
    assert shp_zip.exists(), "Sample Shapefile ZIP missing"

    features, crs = ShapefileParser.parse_zip(shp_zip)

    assert crs == "EPSG:4326"
    assert len(features) == 2
    assert all(f.geometry_type == "Polygon" for f in features)

    # Check attributes extracted from DBF
    plot_ids = [f.properties.get("PLOT_ID") for f in features]
    assert "PLOT-101" in plot_ids
    assert "PLOT-102" in plot_ids


def test_parser_dispatcher():
    kml_file = SAMPLES_DIR / "sample_survey.kml"
    features, crs, file_type = GeospatialParserService.parse_file(kml_file, "sample_survey.kml")

    assert file_type == "kml"
    assert len(features) > 0


def test_invalid_extension_rejection():
    with pytest.raises(ValueError) as exc:
        GeospatialParserService.parse_file(Path("test.txt"), "test.txt")
    assert "Unsupported file extension" in str(exc.value)
