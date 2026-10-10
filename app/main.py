import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.core.config import settings
from app.database import init_db
from app.api.routes import router as files_router
from app.api.health import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("geospatial-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
# 🌍 Geospatial File Measurement API

Production-ready backend API that accepts geospatial files (Shapefile `.zip` or KML `.kml`),
extracts features, gracefully handles geographic vs projected coordinate systems, and accurately
computes physical measurements (Polygon Area, LineString Length, Point handling) in metric units.

### Key Capabilities:
- **Shapefile (.zip) & KML (.kml)** parsing
- **Dynamic Projected Coordinate Reference System (CRS) Selection**: Converts geographic angular coordinates (e.g., EPSG:4326) into optimal local UTM metric projections
- **Accurate Metric Calculations**:
  - Polygons / MultiPolygons: Area in $m^2$, hectares, $km^2$, and perimeter in meters
  - LineStrings / MultiLineStrings: Length in meters and kilometers
  - Points: Gracefully handled without crashes (measurement not applicable)
  - Unsupported geometry types handled gracefully
- **Clean RESTful endpoints**:
  - `POST /api/files/`
  - `GET /api/files/{id}/`
  - `GET /api/files/{id}/measurements/`
  - `GET /api/files/{id}/geojson/`
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(files_router, prefix="/api")
app.include_router(health_router, prefix="/api")

# Static files for UI and samples
samples_dir = Path(__file__).resolve().parent.parent / "samples"
if samples_dir.exists():
    app.mount("/samples", StaticFiles(directory=str(samples_dir)), name="samples")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Welcome to Geospatial File Measurement API. Visit /docs for API documentation."}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred while processing the request."}
    )
