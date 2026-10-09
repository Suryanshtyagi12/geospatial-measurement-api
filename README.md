# Geospatial File Measurement API

## 1. Overview
A FastAPI backend service that accepts geospatial files (Zipped Shapefiles or KML), extracts their features, and calculates highly accurate geodetic and projected measurements (Polygon → Area, LineString → Length).

## 2. Features
- Supports uploaded `.zip` shapefile archives and `.kml` files.
- Automatically handles coordinate transformations to an optimal per-feature UTM zone or equal-area polar CRS.
- Protects against `zip-slip` vulnerabilities and restricts upload boundaries cleanly.
- Offers independent Geodesic measurements via `pyproj` algorithms as a baseline sanity check against planar CRS distortions.

## 3. Setup
### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# (If blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### Docker Option
```bash
docker-compose up --build
```

## 4. Run
Start the development server using Uvicorn:
```bash
python -m uvicorn app.main:app --reload
```
Once running, the interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

## 5. Run tests
Execute the entire test suite directly through Pytest:
```bash
python -m pytest tests
```

## 6. API
### Upload a file
```bash
curl -X POST "http://127.0.0.1:8000/api/files/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_file.kml"
```
Response:
```json
{
  "id": "6f1c...",
  "filename": "your_file.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### Get file measurements
```bash
curl -X GET "http://127.0.0.1:8000/api/files/6f1c.../measurements/?limit=100&offset=0" \
  -H "accept: application/json"
```

## 7. Architecture
1. **API Router (`app/api/files.py`)**: Intercepts requests, validates extensions, handles file payload reading in memory (up to limit), and calls standard exception responses.
2. **Parser (`app/services/parser.py`)**: Uses GeoPandas + PyOgrio to securely unpack bytes and read geometries uniformly.
3. **Geo Logic (`app/services/crs.py`, `measurement.py`)**: Assigns dynamic CRSs to individual shapes for high precision UTM outputs. Evaluates cross-checks with standard geodesic logic.
4. **Orchestrator (`app/services/file_service.py`)**: Connects everything end-to-end and executes efficient bulk saving routines into the target SQLite DB.

## 8. Design Decisions
- **Sync Processing**: Opted for synchronous rather than async or background queues. With a 25MB file limit, GeoPandas operations resolve quickly, preventing the overhead of Redis/Celery queueing logic.
- **SQLite vs Postgres**: Opted for generic SQLite configured directly with SQLAlchemy to ensure reviewer-friendly setups without heavy external PostGIS dependencies, although the codebase natively maps cleanly to a Postgres DSN.
- **Per-feature UTM vs Alternatives**: Dynamically routing standard geometries to specific UTM zones keeps precision extremely high, especially across diverse multi-feature datasets where a single global metric or zone could radically skew local distortion limits.
- **Zip-slip Safety**: Rather than relying strictly on Python's built-in extraction mapping, specific file components (.shp, .shx, .dbf, etc.) are explicitly parsed and reassigned to completely detached generic naming variables. 

## 9. Known Limitations
- The current implementation only maps Point, LineString, and Polygon primitives (alongside their multi- counterparts). Complex geometries fall to an Unsupported fallback.
- Large processing batches hold multiple `Feature` copies in RAM directly before hitting bulk SQLite insertions. Over-limit constraints mitigate OOM errors, but streaming geometry parses could reduce maximum baseline footprint.

## 10. Learnings
- **Axis Logic (`always_xy=True`)**: Handling PyProj transformations required extensive manual testing given historical behaviors of Lat/Lon vs Lon/Lat assumptions differing between source specifications and older projection drivers. 
- **Degree Measurements**: Using planar formulas against unprojected lat/lon coordinates produces conceptually broken and practically useless values. 

## 11. Future Scope
- **PostGIS Integration**: Seamlessly swap SQLAlchemy JSON text fields out for standard geometry blocks inside Postgres allowing high-throughput geographic query filters (e.g. `ST_Intersects`).
- **Background Tasks**: Introduce `Celery/RQ` and Redis backends for handling shapefiles beyond the 25MB HTTP-timeout limit asynchronously.
- **Expanded Exports**: Add support for `.geojson` exports and native `.csv` tabular exports directly attached to processed measurements.
