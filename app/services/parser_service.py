import json
import logging
import os
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional, Tuple, List
from dataclasses import dataclass, field

import shapefile
import shapely
import shapely.geometry
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiLineString, GeometryCollection

from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


@dataclass
class ParsedFeature:
    index: int
    geometry_type: str
    geometry: shapely.Geometry
    geojson: dict[str, Any]
    crs: str
    properties: dict[str, Any] = field(default_factory=dict)


class ShapefileParser:
    @classmethod
    def parse_zip(cls, zip_path: Path) -> Tuple[List[ParsedFeature], str]:
        """
        Extracts a .zip archive containing shapefile (.shp, .shx, .dbf, .prj),
        extracts features, properties, and detected CRS.
        """
        temp_dir = tempfile.mkdtemp(prefix="shapefile_")
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                # Security check against Zip Slip
                for member in archive.namelist():
                    resolved_target = (Path(temp_dir) / member).resolve()
                    if not str(resolved_target).startswith(str(Path(temp_dir).resolve())):
                        raise ValueError(f"Dangerous path in zip archive: {member}")
                archive.extractall(temp_dir)

            # Locate the .shp file
            shp_files = list(Path(temp_dir).rglob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found in the uploaded zip archive.")

            shp_path = shp_files[0]
            prj_path = shp_path.with_suffix(".prj")

            # Extract CRS from .prj if available
            detected_crs = "EPSG:4326"
            if prj_path.exists():
                try:
                    with open(prj_path, "r", encoding="utf-8", errors="ignore") as pf:
                        wkt_str = pf.read().strip()
                        if wkt_str:
                            detected_crs = CRSService.normalize_crs(wkt_str)
                except Exception as e:
                    logger.warning(f"Error reading .prj file {prj_path}: {e}")

            features: List[ParsedFeature] = []
            with shapefile.Reader(str(shp_path)) as sf:
                for idx, shape_rec in enumerate(sf.shapeRecords()):
                    geo_interface = shape_rec.shape.__geo_interface__
                    geom = shapely.geometry.shape(geo_interface)

                    # Extract record properties
                    properties = {}
                    try:
                        properties = shape_rec.record.as_dict()
                    except Exception:
                        # Fallback to field names mapping
                        fields = [f[0] for f in sf.fields[1:]]
                        properties = dict(zip(fields, shape_rec.record))

                    # Ensure properties are JSON serializable
                    clean_properties = {}
                    for k, v in properties.items():
                        if isinstance(v, (bytes, bytearray)):
                            clean_properties[k] = v.decode("utf-8", errors="ignore")
                        elif hasattr(v, "isoformat"):
                            clean_properties[k] = v.isoformat()
                        else:
                            clean_properties[k] = v

                    geojson = shapely.geometry.mapping(geom)

                    features.append(ParsedFeature(
                        index=idx,
                        geometry_type=geom.geom_type,
                        geometry=geom,
                        geojson=geojson,
                        crs=detected_crs,
                        properties=clean_properties
                    ))

            return features, detected_crs

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class KMLParser:
    @classmethod
    def _parse_coordinates(cls, text: Optional[str]) -> List[Tuple[float, ...]]:
        """Parses coordinate tuples from KML <coordinates> string."""
        if not text:
            return []
        coords = []
        for token in text.strip().split():
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    if len(parts) >= 3:
                        alt = float(parts[2])
                        coords.append((lon, lat, alt))
                    else:
                        coords.append((lon, lat))
                except ValueError:
                    continue
        return coords

    @classmethod
    def _parse_polygon_elem(cls, poly_elem: ET.Element) -> Optional[Polygon]:
        """Parses outer boundary and optional inner boundaries (holes)."""
        outer_elem = poly_elem.find(".//outerBoundaryIs") or poly_elem.find(".//OuterBoundaryIs")
        if outer_elem is None:
            return None
        outer_coords = cls._parse_coordinates(outer_elem.findtext(".//coordinates"))
        if len(outer_coords) < 3:
            return None

        # Inner holes
        holes = []
        inner_elems = poly_elem.findall(".//innerBoundaryIs") + poly_elem.findall(".//InnerBoundaryIs")
        for inner_elem in inner_elems:
            inner_coords = cls._parse_coordinates(inner_elem.findtext(".//coordinates"))
            if len(inner_coords) >= 3:
                holes.append(inner_coords)

        return Polygon(shell=outer_coords, holes=holes if holes else None)

    @classmethod
    def _extract_geometry_from_element(cls, elem: ET.Element) -> Optional[shapely.Geometry]:
        """Extracts Shapely geometry from an XML element (Placemark or MultiGeometry)."""
        # 1. Polygon
        poly_elem = elem.find(".//Polygon")
        if poly_elem is not None:
            poly = cls._parse_polygon_elem(poly_elem)
            if poly:
                return poly

        # 2. LineString
        line_elem = elem.find(".//LineString")
        if line_elem is not None:
            coords = cls._parse_coordinates(line_elem.findtext(".//coordinates"))
            if len(coords) >= 2:
                return LineString(coords)

        # 3. LinearRing
        ring_elem = elem.find(".//LinearRing")
        if ring_elem is not None:
            coords = cls._parse_coordinates(ring_elem.findtext(".//coordinates"))
            if len(coords) >= 3:
                return LineString(coords)

        # 4. Point
        pt_elem = elem.find(".//Point")
        if pt_elem is not None:
            coords = cls._parse_coordinates(pt_elem.findtext(".//coordinates"))
            if coords:
                return Point(coords[0])

        # 5. MultiGeometry
        multi_elem = elem.find(".//MultiGeometry")
        if multi_elem is not None:
            sub_geoms = []
            for child in multi_elem:
                sub = cls._extract_geometry_from_element(child)
                if sub:
                    sub_geoms.append(sub)
            if sub_geoms:
                # If all are Polygons -> MultiPolygon
                if all(g.geom_type == "Polygon" for g in sub_geoms):
                    return MultiPolygon(sub_geoms)
                # If all are LineStrings -> MultiLineString
                if all(g.geom_type == "LineString" for g in sub_geoms):
                    return MultiLineString(sub_geoms)
                return GeometryCollection(sub_geoms)

        return None

    @classmethod
    def parse_kml(cls, kml_path: Path) -> Tuple[List[ParsedFeature], str]:
        """
        Parses a .kml file, extracting Placemarks, metadata properties, and geometries.
        Default standard KML CRS is EPSG:4326.
        """
        with open(kml_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid KML XML format: {e}")

        # Remove XML namespaces to simplify querying
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        placemarks = root.findall(".//Placemark")
        features: List[ParsedFeature] = []
        crs = "EPSG:4326"

        for idx, placemark in enumerate(placemarks):
            # Extract properties
            name = placemark.findtext("name")
            description = placemark.findtext("description")

            properties: dict[str, Any] = {}
            if name:
                properties["name"] = name.strip()
            if description:
                properties["description"] = description.strip()

            # Parse ExtendedData if present
            ext_data = placemark.find("ExtendedData")
            if ext_data is not None:
                for data in ext_data.findall("Data"):
                    d_name = data.get("name")
                    d_val = data.findtext("value")
                    if d_name and d_val is not None:
                        properties[d_name] = d_val.strip()

                for s_data in ext_data.findall(".//SimpleData"):
                    s_name = s_data.get("name")
                    s_val = s_data.text
                    if s_name and s_val is not None:
                        properties[s_name] = s_val.strip()

            geom = cls._extract_geometry_from_element(placemark)
            if geom is not None and not geom.is_empty:
                geojson = shapely.geometry.mapping(geom)
                features.append(ParsedFeature(
                    index=idx,
                    geometry_type=geom.geom_type,
                    geometry=geom,
                    geojson=geojson,
                    crs=crs,
                    properties=properties
                ))

        return features, crs


class GeospatialParserService:
    @classmethod
    def parse_file(cls, file_path: Path, filename: str) -> Tuple[List[ParsedFeature], str, str]:
        """
        Dispatch parser based on file extension.
        Returns: (features, crs, file_type)
        """
        suffix = Path(filename).suffix.lower()

        if suffix == ".zip":
            features, crs = ShapefileParser.parse_zip(file_path)
            return features, crs, "shapefile"
        elif suffix == ".kml":
            features, crs = KMLParser.parse_kml(file_path)
            return features, crs, "kml"
        else:
            raise ValueError(f"Unsupported file extension '{suffix}'. Expected .zip (Shapefile) or .kml")
