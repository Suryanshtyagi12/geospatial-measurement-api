# Geospatial File Measurement API

A highly precise, production-ready FastAPI service that ingests geospatial files (Zipped Shapefiles or KML), processes geographic geometries, and outputs calculated measurements (Area, Length) using dynamically assigned Projected Coordinate Systems (CRS).

## Key Features
* **Multi-Format Support:** Safely unpacks and parses `.zip` (Shapefiles) and `.kml` (Multi-layer) files.
* **Per-Feature UTM Projection:** Automatically transforms geographic coordinates (`EPSG:4326`) into localized UTM zones specific to each individual feature, ensuring minimal distortion on global datasets.
* **Geodesic Cross-Checks:** Runs rigorous secondary mathematical validations using `PyProj.Geod` on the pure ellipsoid.
* **Security & Resilience:** Implements active zip-slip protection, explicit payload size limits, and asynchronous-safe bulk SQLite persistence.

## Architecture & Flow
1. **API Router:** Validates incoming payloads and triggers the orchestration service.
2. **Parser Component:** Uses `GeoPandas` and `PyOgrio` to deserialize the uploaded geospatial geometries dynamically.
3. **Measurement Engine:** Filters out invalid coordinates, isolates Polygons/LineStrings, and calculates precise planimetric metrics in localized CRSs.
4. **Persistence:** Features are packaged via strictly-typed `Pydantic` schemas and bulk-inserted into a relational `SQLAlchemy` database (SQLite by default).

## Local Setup (Docker)
The easiest way to run this application locally without installing heavy GDAL binaries is via Docker.

```bash
# Build and start the container
docker-compose up --build
```
Once running:
- **Interactive API Docs (Swagger):** http://localhost:8000/docs
- **Web Interface:** http://localhost:8000/

*(To run locally without Docker, initialize a Python virtual environment and run `pip install -r requirements.txt -r requirements-dev.txt`)*

## Testing
The repository includes a comprehensive test suite covering API ingestion, exact coordinate math, and extraction security.
```bash
python -m pytest tests
```

## Learnings & Future Scope
* **Learnings:** Handling coordinate transformations accurately required deep manipulation of PyProj axis assumptions (`always_xy=True`). Additionally, constructing safe, transient zip-extraction algorithms proved vital to bypassing standard directory traversal vulnerabilities inherent in raw Python unzipping.
* **Future Scope:** For massive geospatial datasets (>25MB), scaling this service would require migrating the processing block into an asynchronous worker queue (e.g., Celery/Redis) and utilizing PostGIS instead of standard SQLite/JSON columns for faster spatial intersection queries.
