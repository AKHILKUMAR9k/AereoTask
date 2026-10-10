import shapely
import pyproj
from fastapi import APIRouter
from app.core.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "geospatial_engine": {
            "shapely_version": shapely.__version__,
            "pyproj_version": pyproj.__version__,
            "proj_version": pyproj.proj_version_str,
        }
    }
