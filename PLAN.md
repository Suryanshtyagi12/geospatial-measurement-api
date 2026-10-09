# Project Implementation Plan: Geospatial File Measurement API

This plan outlines the phase-by-phase implementation of the Geospatial File Measurement API, directly following the build order defined in the project specification. After each phase, we will run tests and commit the changes.

## Phase 1: Scaffold
**Goal:** Set up the foundational project structure, environment, and basic FastAPI app.
- Initialize the git repository.
- Create the Python virtual environment (`.venv`) and install baseline dependencies.
- Set up `pyproject.toml` with `ruff` configuration for linting and formatting.
- Add a `.gitignore` file.
- Create the initial FastAPI application structure (`app/main.py`) with a `/health` endpoint.
- Configure settings (`app/config.py`) and database connection (`app/database.py`).
- *Action:* Commit changes.

## Phase 2: Core Geo Logic (No API yet)
**Goal:** Implement the mathematical and geospatial core of the application.
- Implement CRS logic in `app/services/crs.py` (CRS detection, UTM selection, `pyproj.Transformer`).
- Implement measurement logic in `app/services/measurement.py` (area and length calculations using `shapely` and `pyproj.Geod`).
- Write comprehensive unit tests for core logic as per Section 9 (Items 1-6), validating exact areas, lengths, and UTM zone selection.
- *Action:* Run tests. Commit changes.

## Phase 3: Parser
**Goal:** Build the file parsing capability to handle KML and zipped shapefiles safely.
- Implement `app/utils/zip_safety.py` to securely extract whitelisted files, preventing zip-slip and enforcing size limits.
- Implement `app/services/parser.py` to read files into a `GeoDataFrame`, including CRS detection and validation errors.
- Write tests for parser edge cases (missing CRS, bad inputs, etc.) as per Section 9 (Items 7, 8).
- *Action:* Run tests. Commit changes.

## Phase 4: Persistence
**Goal:** Define the database schema and build the service layer.
- Define SQLAlchemy models in `app/models.py` (`UploadedFile`, `Feature`).
- Define Pydantic schemas in `app/schemas.py`.
- Implement `app/services/file_service.py` to orchestrate the entire flow: upload -> parse -> measure -> bulk insert.
- *Action:* Commit changes.

## Phase 5: API Routes
**Goal:** Expose the functionality via REST endpoints.
- Implement the three main endpoints in `app/api/files.py`:
  - `POST /api/files/`
  - `GET /api/files/{id}/`
  - `GET /api/files/{id}/measurements/`
- Add error handlers and pagination logic.
- Write API tests (Section 9, Items 9, 10).
- *Action:* Run tests. Commit changes.

## Phase 6: Docker + README
**Goal:** Containerize the application and finalize primary documentation.
- Create a `Dockerfile` using `python:3.11-slim` and a `docker-compose.yml`.
- Write the comprehensive `README.md` following the exact structure in Section 14 (Overview, Setup, API, Architecture, Decisions, etc.).
- *Action:* Commit changes.

## Phase 7: Optional Frontend (Static HTML)
**Goal:** Build a minimal visual demo interface.
- Create `static/index.html` with vanilla JS and Leaflet map.
- Serve via FastAPI `StaticFiles`.
- *Action:* Commit changes.

## Phase 8: Optional Deploy
**Goal:** Test deployment configuration.
- (If applicable/possible) Deploy the application.
- *Action:* Commit changes.

## Phase 9: Final Pass
**Goal:** Final quality assurance before completion.
- Run `ruff check .` and `ruff format .`.
- Execute the full test suite (`pytest`).
- Perform a fresh clone test following the README exactly.
- Tag as `v1.0`.
- *Action:* Final review and completion.
