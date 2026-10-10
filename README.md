# 🌍 Geospatial File Measurement API

A robust, production-ready backend service built with **FastAPI**, **Shapely**, and **PyProj** that accepts geospatial files (Shapefile `.zip` and KML `.kml`), extracts vector features, dynamically transforms geographic coordinates into local projected coordinate systems (UTM), and calculates accurate metric measurements (Area, Length, and feature summaries).

Includes an interactive **Swagger/OpenAPI documentation** suite, comprehensive test suite (**20 unit & integration tests**), and a built-in **Web Visualizer Studio**.

---

## 📋 Table of Contents
1. [Key Features](#-key-features)
2. [Architecture & System Design](#-architecture--system-design)
3. [CRS Handling Strategy](#-crs-handling-strategy)
4. [File Processing & Measurement Flow](#-file-processing--measurement-flow)
5. [API Specification & Examples](#-api-specification--examples)
6. [Local Setup & Installation](#-local-setup--installation)
7. [Running with Docker](#-running-with-docker)
8. [Running the Test Suite](#-running-the-test-suite)
9. [Design Decisions & Alternatives](#-design-decisions--alternatives)
10. [Learnings & Future Scope](#-learnings--future-scope)

---

## ✨ Key Features

- **Multi-Format Ingestion**: Supports `.zip` containing Shapefile packages (`.shp`, `.shx`, `.dbf`, `.prj`) and `.kml` (Keyhole Markup Language).
- **Intelligent CRS Reprojection**: Detects source CRS (e.g. `EPSG:4326`) and transforms geometries to appropriate local **Universal Transverse Mercator (UTM)** metric projections prior to calculations, preventing distortion.
- **Accurate Metric Calculations**:
  - **Polygon / MultiPolygon**: Exact Area in $m^2$, hectares ($ha$), and $km^2$, plus perimeter in meters.
  - **LineString / MultiLineString**: Accurate geodesic length in meters and kilometers.
  - **Point / MultiPoint**: Gracefully handled without crashing (measurement explicitly noted as not applicable).
  - **Unsupported Geometries**: Captured safely and reported without service interruptions.
- **Robust Error Handling**: Zip Slip vulnerability prevention, malformed geometry auto-repair via `shapely.make_valid()`, and clean HTTP status codes.
- **Interactive Web Studio**: Integrated modern dashboard at `http://localhost:8000/` to test file uploads, review KPIs, and view feature breakdown.
- **Full Metadata Persistence**: Powered by SQLite via SQLAlchemy with full feature and measurement tracking.

---

## 🏛 Architecture & System Design

The application follows a clean, layered architecture separating routing, business domain logic, and data storage:

```
c:\AereoInternTask\
├── app/
│   ├── api/                     # API Routers (endpoints)
│   │   ├── routes.py            # /api/files endpoints
│   │   └── health.py            # /api/health endpoint
│   ├── core/                    # Application Configuration
│   │   └── config.py            # Environment settings & upload limits
│   ├── models/                  # Domain Schemas & DB Models
│   │   ├── db_models.py         # SQLAlchemy FileRecord & FeatureRecord
│   │   └── schemas.py           # Pydantic v2 schemas
│   ├── services/                # Core Business Logic
│   │   ├── crs_service.py       # CRS normalization & UTM projection engine
│   │   ├── measurement_service.py # Polygon area & LineString length calculations
│   │   ├── parser_service.py    # Shapefile & KML parsing engine
│   │   └── file_service.py      # Storage, lifecycle & payload assembler
│   ├── static/                  # Web Studio Frontend
│   │   ├── index.html           # Modern UI template
│   │   ├── style.css            # Dark slate glassmorphic styling
│   │   └── app.js               # Client upload & table rendering logic
│   ├── database.py              # Database connection & session management
│   └── main.py                  # FastAPI application entrypoint & middleware
├── samples/                     # Test data samples
│   ├── sample_survey.kml        # KML with Polygon, LineString, and Point
│   ├── sample_shapefile.zip     # Shapefile package with attributes and .prj
│   └── generate_samples.py      # Generator script for sample datasets
├── tests/                       # Comprehensive Test Suite
│   ├── test_api.py              # End-to-end endpoint tests
│   ├── test_crs_service.py      # CRS & UTM zone unit tests
│   ├── test_measurements.py     # Polygon, LineString, Point calculation tests
│   ├── test_parsers.py          # Shapefile & KML parsing tests
│   └── conftest.py              # Pytest fixtures & isolated test DB
├── Dockerfile                   # Production Docker image
├── docker-compose.yml           # Multi-container orchestration
├── requirements.txt             # Project dependencies
└── pytest.ini                   # Pytest configuration
```

---

## 🧭 CRS Handling Strategy

### Why We Cannot Measure Directly on Geographic Coordinates (EPSG:4326)
Geographic coordinate systems like **WGS 84 (EPSG:4326)** represent points as angular degrees of latitude and longitude on an ellipsoidal Earth.
1. One degree of longitude is $\approx 111.32\text{ km}$ at the Equator, but shrinks to $0\text{ km}$ at the poles ($\cos(\text{latitude})$ scaling).
2. Directly computing Euclidean area or distance on degrees produces nonsensical units ($\text{deg}^2$ and $\text{deg}$) that change drastically based on latitude.

### Dynamic UTM Projection Selection Strategy
1. **Source Detection**:
   - For **Shapefiles**: Extract WKT string from the accompanying `.prj` file and normalize using `pyproj.CRS`. Defaults to `EPSG:4326` if `.prj` is missing.
   - For **KML**: Standard OGC KML coordinates are strictly specified in WGS84 (`EPSG:4326`).
2. **Optimal UTM Zone Calculation**:
   - The centroid $(\text{lon}, \text{lat})$ of the geometry is calculated.
   - The Universal Transverse Mercator (UTM) zone is calculated:
     $$\text{zone} = \left\lfloor \frac{\text{lon} + 180}{6} \right\rfloor + 1 \quad (\text{clamped between } 1 \text{ and } 60)$$
   - If $\text{lat} \ge 0^\circ$ (Northern Hemisphere): $\text{EPSG Code} = 32600 + \text{zone}$
   - If $\text{lat} < 0^\circ$ (Southern Hemisphere): $\text{EPSG Code} = 32700 + \text{zone}$
3. **Reprojection via Vectorized Transformers**:
   - `pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)` transforms coordinates with millimeter precision.
   - 3D coordinates (with altitude/Z) are preserved without dropping data.
   - All measurements are then calculated on the projected Cartesian geometry in **SI metric units (meters and square meters)**.

---

## 🔄 File Processing & Measurement Flow

```
[Client Request: POST /api/files/]
             │
             ▼
[File Validation & Security Check]
  ├─ Verify extension (.zip or .kml)
  └─ Safe extraction (prevent Zip Slip)
             │
             ▼
[Geospatial Parser Service]
  ├─ .zip: Locate .shp, read attributes from .dbf, parse .prj
  └─ .kml: Parse XML Placemarks, coordinates, ExtendedData
             │
             ▼
[For Each Extracted Feature]
  ├─ 1. Identify Geometry Type (Polygon, LineString, Point)
  ├─ 2. Geometry Validation: Auto-repair invalid rings with make_valid()
  ├─ 3. CRS Reprojection: Determine UTM zone & transform coords
  ├─ 4. Metric Measurement:
  │      • Polygon   ──> Area (m²), hectares, km², perimeter (m)
  │      • LineString──> Length (m), length (km)
  │      • Point     ──> Handled gracefully (measurement: null)
  │      • Other     ──> Handled gracefully (message logged)
  └─ 5. Record Feature & Attributes in Database
             │
             ▼
[Persistence & Response]
  ├─ Status updated to "COMPLETED"
  └─ Returns File Metadata JSON to Client
```

---

## 📡 API Specification & Examples

### 1. Upload Geospatial File
`POST /api/files/`

**Request:** `multipart/form-data` with `file` (`.zip` or `.kml`).

```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -F "file=@samples/sample_survey.kml"
```

**Response (`201 Created`):**
```json
{
  "id": "e93f6bd5b630",
  "filename": "sample_survey.kml",
  "feature_count": 4,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error_message": null
}
```

---

### 2. Get File Information
`GET /api/files/{id}/`

```bash
curl -X GET "http://localhost:8000/api/files/e93f6bd5b630/" \
  -H "accept: application/json"
```

**Response (`200 OK`):**
```json
{
  "id": "e93f6bd5b630",
  "filename": "sample_survey.kml",
  "feature_count": 4,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error_message": null
}
```

---

### 3. Get Measurements
`GET /api/files/{id}/measurements/`

```bash
curl -X GET "http://localhost:8000/api/files/e93f6bd5b630/measurements/" \
  -H "accept: application/json"
```

**Response (`200 OK`):**
```json
{
  "id": "e93f6bd5b630",
  "filename": "sample_survey.kml",
  "feature_count": 4,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "summary": {
    "total_features": 4,
    "geometry_distribution": {
      "Polygon": 2,
      "LineString": 1,
      "Point": 1
    },
    "total_area_sq_m": 412495.1234,
    "total_area_hectares": 41.2495,
    "total_length_m": 776.4521,
    "total_length_km": 0.7765
  },
  "measurements": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[77.59, 12.97], [77.595, 12.97], [77.595, 12.975], [77.59, 12.975], [77.59, 12.97]]]
      },
      "source_crs": "EPSG:4326",
      "projected_crs": "EPSG:32643",
      "measurement_type": "area",
      "value": 303975.8219,
      "unit": "square_meters",
      "properties": {
        "name": "Parcel Alpha (Polygon)",
        "zone": "Commercial-IT",
        "status": "Approved"
      },
      "details": {
        "area_sq_m": 303975.8219,
        "area_hectares": 30.3976,
        "area_sq_km": 0.303976,
        "perimeter_m": 2205.12,
        "is_valid": true
      }
    },
    {
      "feature_id": 1,
      "geometry_type": "LineString",
      "geometry": {
        "type": "LineString",
        "coordinates": [[77.59, 12.97], [77.5925, 12.9725], [77.595, 12.975]]
      },
      "source_crs": "EPSG:4326",
      "projected_crs": "EPSG:32643",
      "measurement_type": "length",
      "value": 776.4521,
      "unit": "meters",
      "properties": {
        "name": "Access Road (LineString)",
        "lanes": "4",
        "speed_limit": "40 km/h"
      },
      "details": {
        "length_m": 776.4521,
        "length_km": 0.7765,
        "is_valid": true
      }
    },
    {
      "feature_id": 2,
      "geometry_type": "Point",
      "geometry": {
        "type": "Point",
        "coordinates": [77.5925, 12.9725, 920.45]
      },
      "source_crs": "EPSG:4326",
      "projected_crs": null,
      "measurement_type": null,
      "value": null,
      "unit": null,
      "properties": {
        "name": "Survey Benchmark BM-01 (Point)",
        "elevation_msl": "920.45"
      },
      "details": {
        "message": "Measurement not applicable for Point geometry"
      }
    }
  ]
}
```

---

### 4. Additional Endpoints
- `GET /api/files/`: List uploaded files with pagination (`?skip=0&limit=20`).
- `GET /api/files/{id}/geojson/`: Exports features as a standard **GeoJSON FeatureCollection** with measurements embedded in feature properties.
- `DELETE /api/files/{id}/`: Deletes an uploaded file and all associated features.
- `GET /api/health`: Health status and engine version telemetry.

---

## 💻 Local Setup & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, 3.13, 3.14)
- Git

### 1. Clone & Set Up Virtual Environment
```bash
git clone <your-repository-url>
cd AereoInternTask

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Generate Sample Datasets
```bash
python samples/generate_samples.py
```

### 4. Run the API Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application is now live:
- **Interactive Web Studio**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🐳 Running with Docker

Run the entire application in an isolated container without needing local GIS library installations:

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build and run with Docker directly
docker build -t geospatial-measurement-api .
docker run -p 8000:8000 geospatial-measurement-api
```

---

## 🧪 Running the Test Suite

A comprehensive test suite of **20 tests** validates end-to-end functionality:
- CRS normalization and UTM zone determination (both Northern and Southern hemispheres)
- Metric area and length calculations
- Graceful handling of Points, MultiPolygons, and unsupported types
- Auto-repair of self-intersecting polygons
- Shapefile ZIP and KML parsing
- REST API workflows (upload, fetch, list, export GeoJSON, delete)
- Error handling and invalid file rejection

Run the test suite with:
```bash
pytest -v
```

Output:
```
============================= test session starts =============================
collected 20 items

tests/test_api.py::test_health_check PASSED                              [  5%]
tests/test_api.py::test_upload_and_get_kml_flow PASSED                   [ 10%]
tests/test_api.py::test_upload_shapefile_zip_flow PASSED                 [ 15%]
tests/test_api.py::test_upload_invalid_extension PASSED                  [ 20%]
tests/test_api.py::test_get_nonexistent_file PASSED                      [ 25%]
tests/test_api.py::test_list_and_delete_files PASSED                     [ 30%]
tests/test_crs_service.py::test_normalize_crs PASSED                     [ 35%]
tests/test_crs_service.py::test_utm_zone_calculation PASSED              [ 40%]
tests/test_crs_service.py::test_reproject_geometry_to_metric_system PASSED [ 45%]
tests/test_measurements.py::test_polygon_area_measurement PASSED         [ 50%]
tests/test_measurements.py::test_linestring_length_measurement PASSED    [ 55%]
tests/test_measurements.py::test_point_graceful_handling PASSED          [ 60%]
tests/test_measurements.py::test_multipolygon_measurement PASSED         [ 65%]
tests/test_measurements.py::test_unsupported_geometry_graceful_handling PASSED [ 70%]
tests/test_measurements.py::test_self_intersecting_polygon_auto_repair PASSED [ 75%]
tests/test_measurements.py::test_southern_hemisphere_reprojection PASSED [ 80%]
tests/test_parsers.py::test_parse_sample_kml PASSED                      [ 85%]
tests/test_parsers.py::test_parse_sample_shapefile_zip PASSED            [ 90%]
tests/test_parsers.py::test_parser_dispatcher PASSED                     [ 95%]
tests/test_parsers.py::test_invalid_extension_rejection PASSED           [100%]

======================== 20 passed in 0.65s ===================================
```

---

## 💡 Design Decisions & Alternatives

| Decision | Selected Approach | Alternative Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **Framework** | **FastAPI** | Django + DRF | FastAPI provides high asynchronous performance, native Pydantic v2 data serialization, automatic OpenAPI documentation, and minimal footprint without bloated ORM migrations. |
| **Shapefile Parser** | **pyshp (`shapefile`)** | GDAL / Fiona bindings | `pyshp` is pure Python, zero-dependency, and doesn't suffer from platform-dependent GDAL C++ binary compatibility issues on Windows/macOS. |
| **KML Parser** | **XML ElementTree + shapely** | `fastkml` or `geopandas` | KML files in the wild have varying namespaces and XML structure. Custom namespace-agnostic ElementTree parsing guarantees fault tolerance against malformed attributes and nested tags. |
| **Projection Strategy** | **Local UTM Zones (EPSG:326XX / 327XX)** | Web Mercator (EPSG:3857) | EPSG:3857 severely distorts area away from the equator (e.g. Greenland appears the size of Africa). UTM preserves conformal metric accuracy locally with negligible distortion ($<0.04\%$). |
| **Reprojection Engine** | **`pyproj.Transformer` + `shapely.transform`** | `shapely.ops.transform` | Uses the modern vectorized coordinate mapping in Shapely 2.0 without triggering deprecation warnings, supporting both 2D and 3D coordinates. |
| **Data Persistence** | **SQLite with SQLAlchemy** | In-Memory Dictionary | Ensures uploaded files and measurements persist across server reboots, enables pagination and multi-session retrieval. |
| **Self-Healing Geometries** | **`shapely.make_valid()`** | Reject invalid geometry | Real-world survey data frequently contains bowtie or self-intersecting rings. Automatically repairing valid topologies ensures smooth operations without crashing. |

---

## 🚀 Learnings & Future Scope

### Learnings
1. **Handling Real-World KML Structure**: KML coordinates are arranged as $(x, y, z) = (\text{longitude}, \text{latitude}, \text{altitude})$ and separated by spaces or newlines. Explicitly handling 3D coordinate matrices during reprojection avoids dropping elevation information.
2. **Projected CRS Precision**: Using UTM projections derived from feature centroids ensures that polygon areas and line distances reflect physical ground truths, avoiding the severe scale distortion inherent to Web Mercator.
3. **Security in Archive Uploads**: Zip file uploads can be vectors for **Zip Slip** directory traversal attacks. Validating resolved paths against canonical target directories ensures secure extraction.

### Future Scope
1. **Asynchronous Background Processing**: For multi-gigabyte shapefiles containing millions of parcels, integrate **Celery / Redis** or **FastAPI BackgroundTasks** with WebSockets to stream real-time progress updates.
2. **Additional Format Support**: Extend parser support to **GeoJSON**, **GeoPackage (.gpkg)**, **FlatGeobuf**, and **DXF/DWG** CAD files.
3. **True 3D Surface Area with DTM/DEM**: When elevation data is present, compute true topographical 3D slope-adjusted surface area rather than planar 2D footprint area.
4. **PostGIS & Cloud Storage**: Migrate from SQLite to **PostgreSQL with PostGIS** for spatial indexing (`ST_Area`, `ST_Length`, `ST_Transform`) and **AWS S3 / GCP Cloud Storage** for file storage.
5. **Interactive 2D/3D Map Viewer**: Integrate **MapLibre GL** or **CesiumJS** in the Web Studio to render features dynamically over satellite imagery.

---

## 📦 Submission Guide

1. **Create a Public GitHub Repository**:
   ```bash
   git init
   git add .
   git commit -m "feat: complete Geospatial File Measurement API"
   git branch -M main
   git remote add origin https://github.com/<your-username>/geospatial-measurement-api.git
   git push -u origin main
   ```
2. Share the public repository URL as required.
