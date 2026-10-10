import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import FileRecord
from app.models.schemas import FileResponse, FileMeasurementsResponse
from app.services.file_service import FileProcessingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Files & Measurements"])


@router.post(
    "/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Accepts a `.zip` containing a Shapefile (.shp, .shx, .dbf, and optional .prj) or a `.kml` file. "
                "Processes all geometries, normalizes CRS, and computes projected physical measurements."
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.zip or .kml)"),
    db: Session = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename must be provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".zip", ".kml"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Only .zip (Shapefile) and .kml files are supported."
        )

    try:
        file_id, dest_path, file_size = await FileProcessingService.save_upload(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upload file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

    # Process and extract measurements
    file_record = FileProcessingService.process_and_store_file(
        db=db,
        file_id=file_id,
        filename=file.filename,
        file_path=dest_path,
        file_size=file_size
    )

    if file_record.status == "FAILED":
        raise HTTPException(
            status_code=422,
            detail=f"File processing failed: {file_record.error_message}"
        )

    return file_record.to_dict()


@router.get(
    "/",
    response_model=List[FileResponse],
    summary="List uploaded files",
    description="Returns a list of all uploaded files with pagination."
)
def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    records = db.query(FileRecord).order_by(FileRecord.created_at.desc()).offset(skip).limit(limit).all()
    return [r.to_dict() for r in records]


@router.get(
    "/{id}/",
    response_model=FileResponse,
    summary="Get file information",
    description="Returns metadata about an uploaded geospatial file including feature count and detected CRS."
)
def get_file_info(
    id: str,
    db: Session = Depends(get_db)
):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail=f"File with ID '{id}' was not found.")
    return file_record.to_dict()


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get measurements for file features",
    description="Returns detailed measurements for all features in the specified file, including projected CRS and units."
)
def get_file_measurements(
    id: str,
    db: Session = Depends(get_db)
):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail=f"File with ID '{id}' was not found.")

    return FileProcessingService.get_file_measurements_payload(file_record)


@router.get(
    "/{id}/geojson/",
    summary="Export as GeoJSON FeatureCollection",
    description="Returns the extracted features formatted as a standard GeoJSON FeatureCollection with measurements in properties."
)
def get_file_geojson(
    id: str,
    db: Session = Depends(get_db)
):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail=f"File with ID '{id}' was not found.")

    features = []
    for f in file_record.features:
        f_dict = f.to_dict()
        props = f_dict["properties"].copy()
        props["feature_id"] = f_dict["feature_id"]
        props["measurement_type"] = f_dict["measurement_type"]
        props["measurement_value"] = f_dict["value"]
        props["measurement_unit"] = f_dict["unit"]
        props["projected_crs"] = f_dict["projected_crs"]
        props.update(f_dict["details"])

        features.append({
            "type": "Feature",
            "geometry": f_dict["geometry"],
            "properties": props
        })

    return {
        "type": "FeatureCollection",
        "file_id": file_record.id,
        "filename": file_record.filename,
        "crs": file_record.crs,
        "features": features
    }


@router.delete(
    "/{id}/",
    status_code=status.HTTP_200_OK,
    summary="Delete an uploaded file",
    description="Deletes the file metadata and associated features from the database."
)
def delete_file(
    id: str,
    db: Session = Depends(get_db)
):
    file_record = db.query(FileRecord).filter(FileRecord.id == id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail=f"File with ID '{id}' was not found.")

    db.delete(file_record)
    db.commit()
    return {"message": f"File '{id}' deleted successfully."}
