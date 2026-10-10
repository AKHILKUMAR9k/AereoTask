import json
import logging
import uuid
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import FileRecord, FeatureRecord
from app.services.parser_service import GeospatialParserService
from app.services.measurement_service import MeasurementService

logger = logging.getLogger(__name__)


class FileProcessingService:
    @classmethod
    async def save_upload(cls, upload_file: UploadFile) -> Tuple[str, Path, int]:
        """Saves an uploaded file to disk and generates a unique ID."""
        file_id = uuid.uuid4().hex[:12]
        file_ext = Path(upload_file.filename).suffix.lower()
        saved_filename = f"{file_id}_{upload_file.filename}"
        dest_path = settings.upload_dir / saved_filename

        total_bytes = 0
        with open(dest_path, "wb") as buffer:
            while chunk := await upload_file.read(1024 * 64):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size:
                    dest_path.unlink(missing_ok=True)
                    raise ValueError(f"File size exceeds maximum allowed limit of {settings.max_upload_size // (1024*1024)}MB.")
                buffer.write(chunk)

        return file_id, dest_path, total_bytes

    @classmethod
    def process_and_store_file(
        cls,
        db: Session,
        file_id: str,
        filename: str,
        file_path: Path,
        file_size: int
    ) -> FileRecord:
        """
        Parses geospatial features, computes metric projected measurements,
        and saves records to the database.
        """
        file_ext = Path(filename).suffix.lower()
        file_type = "shapefile" if file_ext == ".zip" else "kml"

        file_record = FileRecord(
            id=file_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            status="PROCESSING"
        )
        db.add(file_record)
        db.commit()

        try:
            # 1. Parse features and CRS
            features, detected_crs, _ = GeospatialParserService.parse_file(file_path, filename)

            file_record.crs = detected_crs
            file_record.feature_count = len(features)

            # 2. Process measurements for each feature
            for feat in features:
                meas_res = MeasurementService.calculate_measurement(feat.geometry, source_crs=feat.crs)

                feature_db = FeatureRecord(
                    file_id=file_id,
                    feature_index=feat.index,
                    geometry_type=feat.geometry_type,
                    geometry_geojson=json.dumps(feat.geojson),
                    source_crs=feat.crs,
                    projected_crs=meas_res.projected_crs,
                    measurement_type=meas_res.measurement_type,
                    measurement_value=meas_res.value,
                    measurement_unit=meas_res.unit,
                    details_json=json.dumps(meas_res.details),
                    properties_json=json.dumps(feat.properties)
                )
                db.add(feature_db)

            file_record.status = "COMPLETED"
            db.commit()
            db.refresh(file_record)
            logger.info(f"Successfully processed file {filename} ({file_id}) with {len(features)} features.")
            return file_record

        except Exception as e:
            logger.error(f"Failed processing file {filename} ({file_id}): {e}", exc_info=True)
            file_record.status = "FAILED"
            file_record.error_message = str(e)
            db.commit()
            db.refresh(file_record)
            return file_record

    @classmethod
    def get_file_measurements_payload(cls, file_record: FileRecord) -> dict:
        """Constructs response payload with full measurement details and summary."""
        items = []
        geom_dist = {}
        total_area = 0.0
        total_length = 0.0
        has_area = False
        has_length = False

        for f in file_record.features:
            item_dict = f.to_dict()
            items.append(item_dict)

            # Accumulate statistics
            g_type = f.geometry_type
            geom_dist[g_type] = geom_dist.get(g_type, 0) + 1

            if f.measurement_type == "area" and f.measurement_value is not None:
                total_area += f.measurement_value
                has_area = True
            elif f.measurement_type == "length" and f.measurement_value is not None:
                total_length += f.measurement_value
                has_length = True

        summary = {
            "total_features": file_record.feature_count,
            "geometry_distribution": geom_dist,
            "total_area_sq_m": round(total_area, 4) if has_area else None,
            "total_area_hectares": round(total_area / 10_000, 6) if has_area else None,
            "total_length_m": round(total_length, 4) if has_length else None,
            "total_length_km": round(total_length / 1000, 6) if has_length else None,
        }

        return {
            "id": file_record.id,
            "filename": file_record.filename,
            "feature_count": file_record.feature_count,
            "crs": file_record.crs,
            "status": file_record.status,
            "summary": summary,
            "measurements": items
        }
