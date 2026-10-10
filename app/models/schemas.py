from typing import Any, Optional
from pydantic import BaseModel, Field


class FileResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Uploaded file name")
    feature_count: int = Field(..., description="Total number of extracted features")
    crs: str = Field(..., description="Detected Coordinate Reference System")
    status: str = Field(..., description="Processing status (PROCESSING, COMPLETED, FAILED)")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")

    class Config:
        from_attributes = True


class MeasurementDetail(BaseModel):
    area_sq_m: Optional[float] = None
    area_hectares: Optional[float] = None
    area_sq_km: Optional[float] = None
    perimeter_m: Optional[float] = None
    length_m: Optional[float] = None
    length_km: Optional[float] = None
    message: Optional[str] = None


class MeasurementItem(BaseModel):
    feature_id: int = Field(..., description="Index of the feature")
    geometry_type: str = Field(..., description="Geometry type (Polygon, LineString, Point, etc.)")
    geometry: Optional[dict[str, Any]] = Field(None, description="GeoJSON geometry of the feature")
    source_crs: str = Field(..., description="Source coordinate reference system")
    projected_crs: Optional[str] = Field(None, description="Projected CRS used for measurement")
    measurement_type: Optional[str] = Field(None, description="Type of measurement (area, length, or None)")
    value: Optional[float] = Field(None, description="Calculated measurement value")
    unit: Optional[str] = Field(None, description="Measurement unit (square_meters, meters, or None)")
    properties: dict[str, Any] = Field(default_factory=dict, description="Feature attributes/properties")
    details: dict[str, Any] = Field(default_factory=dict, description="Detailed unit conversions and notes")


class MeasurementSummary(BaseModel):
    total_features: int
    geometry_distribution: dict[str, int]
    total_area_sq_m: Optional[float] = None
    total_area_hectares: Optional[float] = None
    total_length_m: Optional[float] = None
    total_length_km: Optional[float] = None


class FileMeasurementsResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Uploaded file name")
    feature_count: int = Field(..., description="Total number of features")
    crs: str = Field(..., description="Source Coordinate Reference System")
    status: str = Field(..., description="File status")
    summary: Optional[MeasurementSummary] = None
    measurements: list[MeasurementItem] = Field(default_factory=list, description="Measurements list")


class HealthResponse(BaseModel):
    status: str
    version: str
    geospatial_engine: dict[str, str]
