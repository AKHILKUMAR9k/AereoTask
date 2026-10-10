import logging
import numpy as np
import pyproj
import shapely
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CRSService:
    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

    @classmethod
    def normalize_crs(cls, crs_input: Optional[str]) -> str:
        """
        Normalize a CRS representation to standard EPSG:XXXX or authority string.
        Falls back to EPSG:4326 if not determinable.
        """
        if not crs_input or str(crs_input).strip() == "" or str(crs_input).lower() in ("unknown", "none", "null"):
            return cls.DEFAULT_GEOGRAPHIC_CRS

        try:
            crs_obj = pyproj.CRS.from_user_input(crs_input)
            epsg = crs_obj.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            # If no direct EPSG integer, try authority name & code
            auth_name = crs_obj.to_authority()
            if auth_name:
                return f"{auth_name[0]}:{auth_name[1]}"
            return crs_obj.to_string()
        except Exception as e:
            logger.warning(f"Could not parse CRS '{crs_input}': {e}. Defaulting to {cls.DEFAULT_GEOGRAPHIC_CRS}")
            return cls.DEFAULT_GEOGRAPHIC_CRS

    @classmethod
    def is_geographic(cls, crs_str: str) -> bool:
        """Check if CRS uses angular coordinates (latitude/longitude in degrees)."""
        try:
            crs = pyproj.CRS.from_user_input(crs_str)
            return crs.is_geographic
        except Exception:
            return True  # Treat unknown as geographic default

    @classmethod
    def get_utm_epsg_for_lat_lon(cls, lat: float, lon: float) -> str:
        """
        Calculate the appropriate UTM zone EPSG code for a latitude/longitude point.
        WGS 84 / UTM zone 1N-60N: EPSG:32601 - 32660
        WGS 84 / UTM zone 1S-60S: EPSG:32701 - 32760
        """
        # Clamp lon to [-180, 180]
        clamped_lon = max(-180.0, min(180.0, lon))
        zone = int((clamped_lon + 180) / 6) + 1
        zone = max(1, min(60, zone))

        if lat >= 0:
            epsg_code = 32600 + zone
        else:
            epsg_code = 32700 + zone

        return f"EPSG:{epsg_code}"

    @classmethod
    def get_projected_crs(cls, geometry: shapely.Geometry, source_crs: str = "EPSG:4326") -> str:
        """
        Determine the optimal projected CRS (in meters) for a given geometry.
        If already projected in meters, keeps the source CRS.
        If geographic, finds the local UTM zone based on geometry centroid.
        """
        norm_source = cls.normalize_crs(source_crs)

        try:
            crs_obj = pyproj.CRS.from_user_input(norm_source)
            if crs_obj.is_projected:
                # Check linear units
                unit_name = (crs_obj.axis_info[0].unit_name or "").lower()
                if "metre" in unit_name or "meter" in unit_name:
                    return norm_source
        except Exception as e:
            logger.debug(f"Error checking if CRS is projected: {e}")

        # If geometry is in geographic coords, compute centroid in lon/lat
        try:
            centroid = geometry.centroid
            lon = centroid.x
            lat = centroid.y
            return cls.get_utm_epsg_for_lat_lon(lat, lon)
        except Exception as e:
            logger.warning(f"Failed to calculate centroid for geometry: {e}. Fallback to EPSG:3857")
            return "EPSG:3857"

    @classmethod
    def transform_geometry(
        cls,
        geometry: shapely.Geometry,
        source_crs: str,
        target_crs: str
    ) -> shapely.Geometry:
        """
        Transform a Shapely geometry from source_crs to target_crs using pyproj.
        Handles 2D and 3D geometries with high precision and no deprecation warnings.
        """
        if source_crs == target_crs:
            return geometry

        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

        def _coord_transform(coords: np.ndarray) -> np.ndarray:
            x, y = transformer.transform(coords[:, 0], coords[:, 1])
            if coords.shape[1] > 2:
                return np.column_stack([x, y, coords[:, 2:]])
            return np.column_stack([x, y])

        return shapely.transform(geometry, _coord_transform)

    @classmethod
    def project_geometry_for_measurement(
        cls,
        geometry: shapely.Geometry,
        source_crs: str = "EPSG:4326"
    ) -> Tuple[shapely.Geometry, str]:
        """
        Prepares a geometry for physical measurement:
        1. Determines the best projected metric CRS (e.g. UTM zone).
        2. Transforms the geometry into that projected CRS.
        Returns: (projected_geometry, projected_crs_name)
        """
        norm_source = cls.normalize_crs(source_crs)
        target_crs = cls.get_projected_crs(geometry, norm_source)

        if norm_source == target_crs:
            return geometry, target_crs

        projected_geom = cls.transform_geometry(geometry, norm_source, target_crs)
        return projected_geom, target_crs
