import logging
from typing import Any, Optional, Tuple
import shapely
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class MeasurementResult:
    def __init__(
        self,
        measurement_type: Optional[str],
        value: Optional[float],
        unit: Optional[str],
        projected_crs: Optional[str],
        details: dict[str, Any]
    ):
        self.measurement_type = measurement_type
        self.value = value
        self.unit = unit
        self.projected_crs = projected_crs
        self.details = details


class MeasurementService:
    @classmethod
    def calculate_measurement(
        cls,
        geom: shapely.Geometry,
        source_crs: str = "EPSG:4326"
    ) -> MeasurementResult:
        """
        Calculate measurement for any geometry.
        Transforms coordinates to metric projected CRS if needed.
        Gracefully handles unsupported or point geometries without raising exceptions.
        """
        if geom is None or geom.is_empty:
            return MeasurementResult(
                measurement_type=None,
                value=None,
                unit=None,
                projected_crs=None,
                details={"message": "Empty or null geometry provided"}
            )

        geom_type = geom.geom_type

        # Fix invalid geometries if possible (e.g. self-intersecting rings)
        if not geom.is_valid:
            try:
                geom = shapely.make_valid(geom)
            except Exception as e:
                logger.warning(f"Failed to repair invalid geometry {geom_type}: {e}")

        # 1. Point / MultiPoint - explicit rule: No measurement required
        if geom_type in ("Point", "MultiPoint"):
            return MeasurementResult(
                measurement_type=None,
                value=None,
                unit=None,
                projected_crs=None,
                details={"message": "Measurement not applicable for Point geometry"}
            )

        # 2. Polygon / MultiPolygon - calculate Area
        if geom_type in ("Polygon", "MultiPolygon"):
            try:
                proj_geom, proj_crs = CRSService.project_geometry_for_measurement(geom, source_crs)
                area_sq_m = float(proj_geom.area)
                perimeter_m = float(proj_geom.length)

                area_hectares = area_sq_m / 10_000.0
                area_sq_km = area_sq_m / 1_000_000.0

                return MeasurementResult(
                    measurement_type="area",
                    value=round(area_sq_m, 4),
                    unit="square_meters",
                    projected_crs=proj_crs,
                    details={
                        "area_sq_m": round(area_sq_m, 4),
                        "area_hectares": round(area_hectares, 6),
                        "area_sq_km": round(area_sq_km, 8),
                        "perimeter_m": round(perimeter_m, 4),
                        "is_valid": bool(geom.is_valid),
                    }
                )
            except Exception as e:
                logger.error(f"Error calculating area for {geom_type}: {e}", exc_info=True)
                return MeasurementResult(
                    measurement_type="area",
                    value=None,
                    unit="square_meters",
                    projected_crs=None,
                    details={"error": f"Failed to calculate area: {str(e)}"}
                )

        # 3. LineString / MultiLineString - calculate Length
        if geom_type in ("LineString", "MultiLineString", "LinearRing"):
            try:
                proj_geom, proj_crs = CRSService.project_geometry_for_measurement(geom, source_crs)
                length_m = float(proj_geom.length)
                length_km = length_m / 1000.0

                return MeasurementResult(
                    measurement_type="length",
                    value=round(length_m, 4),
                    unit="meters",
                    projected_crs=proj_crs,
                    details={
                        "length_m": round(length_m, 4),
                        "length_km": round(length_km, 6),
                        "is_valid": bool(geom.is_valid),
                    }
                )
            except Exception as e:
                logger.error(f"Error calculating length for {geom_type}: {e}", exc_info=True)
                return MeasurementResult(
                    measurement_type="length",
                    value=None,
                    unit="meters",
                    projected_crs=None,
                    details={"error": f"Failed to calculate length: {str(e)}"}
                )

        # 4. Other / Unsupported types (e.g. GeometryCollection) - graceful fallback
        return MeasurementResult(
            measurement_type=None,
            value=None,
            unit=None,
            projected_crs=None,
            details={"message": f"Geometry type '{geom_type}' is not supported for measurement calculation"}
        )
