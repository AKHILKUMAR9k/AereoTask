import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)  # "shapefile" or "kml"
    file_size = Column(Integer, nullable=False)
    feature_count = Column(Integer, default=0)
    crs = Column(String(64), default="Unknown")
    status = Column(String(32), default="PROCESSING")  # PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    features = relationship("FeatureRecord", back_populates="file", cascade="all, delete-orphan", order_by="FeatureRecord.feature_index")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "feature_count": self.feature_count,
            "crs": self.crs,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FeatureRecord(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(64), ForeignKey("files.id"), index=True, nullable=False)
    feature_index = Column(Integer, nullable=False)
    geometry_type = Column(String(64), nullable=False)
    geometry_geojson = Column(Text, nullable=False)  # GeoJSON string
    source_crs = Column(String(64), default="EPSG:4326")
    projected_crs = Column(String(64), nullable=True)
    measurement_type = Column(String(32), nullable=True)  # "area", "length", None
    measurement_value = Column(Float, nullable=True)
    measurement_unit = Column(String(32), nullable=True)  # "square_meters", "meters", None
    details_json = Column(Text, default="{}")  # Additional measurement breakdown
    properties_json = Column(Text, default="{}")  # Original feature attributes

    file = relationship("FileRecord", back_populates="features")

    def to_dict(self):
        properties = json.loads(self.properties_json) if self.properties_json else {}
        details = json.loads(self.details_json) if self.details_json else {}
        geojson = json.loads(self.geometry_geojson) if self.geometry_geojson else None

        return {
            "feature_id": self.feature_index,
            "geometry_type": self.geometry_type,
            "geometry": geojson,
            "source_crs": self.source_crs,
            "projected_crs": self.projected_crs,
            "measurement_type": self.measurement_type,
            "value": round(self.measurement_value, 4) if self.measurement_value is not None else None,
            "unit": self.measurement_unit,
            "properties": properties,
            "details": details,
        }
