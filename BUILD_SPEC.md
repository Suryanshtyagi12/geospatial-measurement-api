# BUILD SPEC: Geospatial File Measurement API

> Instructions for the coding agent. Read the whole file before writing code.
> Build in the order given in **Section 12**. After each phase: run tests, commit.
> Priority: **correctness > clean structure > tests > docs > extras.**

---

## 1. Goal

Backend service (FastAPI) that accepts a geospatial file (`.zip` containing a Shapefile, or `.kml`), extracts features, calculates measurements (Polygon → area, LineString → length) **in a projected CRS, never in degrees**, stores results in a relational DB, and exposes them via REST.

This is a hiring assignment for a geospatial company (Aereo). The reviewer will check:
1. CRS handling is correct (the main trap).
2. Code is clean, layered, readable.
3. Edge cases don't crash the service.
4. Tests prove the numbers are right.
5. README is clear and honest (design decisions, learnings, future scope).

The author must be able to explain every line. **Prefer simple, readable code over clever code. No unnecessary abstractions.**

---

## 1A. Environment Rules (mandatory, apply to EVERY command)

- All work happens inside the project virtual environment `.venv` at the repo root. Never `pip install` globally. Never run the app or tests with the system Python.
- Create once: `python -m venv .venv`
- **Do not rely on activation.** Agent shells often do not keep state between commands, so a "activated" venv silently falls back to system Python. Call the venv interpreter explicitly:
  - Windows (PowerShell): `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
  - Windows (PowerShell): `.\.venv\Scripts\python.exe -m pytest`
  - Windows (PowerShell): `.\.venv\Scripts\python.exe -m ruff check .`
  - Windows (PowerShell): `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
  - Linux/macOS: same commands with `.venv/bin/python`
- Always use the `python -m <tool>` form (pip, pytest, ruff, uvicorn) so the tool is bound to the venv interpreter.
- Sanity check at the start of a session and before any install: `.\.venv\Scripts\python.exe -c "import sys; print(sys.prefix)"` must print a path inside this repo's `.venv`. If not, stop and fix it.
- `.venv/` is in `.gitignore`. Any new dependency is added to `requirements.txt` / `requirements-dev.txt` in the same commit, pinned (`==`) after tests pass.
- Human activation for the README: `.\.venv\Scripts\Activate.ps1` (if blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`).
- Inside Docker the container is the isolation; no venv there.

---

## 2. Tech Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | Type hints everywhere |
| Framework | FastAPI | Auto docs at `/docs` |
| Geo reading | `geopandas` + `pyogrio` | Reads shapefile and KML via GDAL |
| Geometry | `shapely` 2.x | |
| CRS / projection | `pyproj` | Transformer, CRS, Geod |
| DB | SQLite (default) via SQLAlchemy 2.x | Postgres-compatible; URL from env |
| Migrations | `create_all` on startup (decided, see 2B-4) | Alembic goes in Future Scope |
| Validation | Pydantic v2 + `pydantic-settings` | |
| Tests | `pytest`, `httpx` / FastAPI `TestClient` | |
| Lint/format | `ruff` (lint + format) | Config in `pyproject.toml` |
| Packaging | `requirements.txt` + `requirements-dev.txt` | |
| Container | `Dockerfile` + `docker-compose.yml` | Solves GDAL install pain |

Dev machine is **Windows / PowerShell**. README must include PowerShell commands (venv activation: `.\.venv\Scripts\Activate.ps1`) and recommend Docker if GDAL wheels fail.

**Early check (do first):** confirm `pyogrio` can read a `.kml` and a zipped shapefile in the dev environment. If the KML driver is unavailable, fall back to `fastkml` or parse KML with `lxml`, and document it.

---

## 2B. Decision Log (each option was judged; do not relitigate without a concrete reason)

**2B-1. Processing model: synchronous.**
Options: synchronous, FastAPI `BackgroundTasks`, Celery/RQ + Redis.
Verdict: synchronous. Upload limit is 25 MB, so processing takes seconds, the client gets a final result in one call, and there is no queue to deploy or explain. Celery adds Redis, workers, and failure modes that the task does not need.
Rule: declare the upload route with plain `def`, NOT `async def`. GeoPandas work is blocking and CPU-bound; `async def` would freeze the event loop, while `def` runs in FastAPI's threadpool.
Upgrade path: the `status` field already exists, so moving to a background worker later changes the service layer, not the API. Document this.

**2B-2. CRS strategy: per-feature UTM + geodesic cross-check.**
Options: raw degrees (wrong), one UTM zone per file, UTM zone per feature, local equal-area CRS (LAEA/Albers), geodesic only.
Verdict: per-feature UTM for the reported value, `pyproj.Geod` stored beside it as a sanity check.
Why: the task explicitly asks for projected measurement; UTM has a standard, reportable EPSG code; per-feature selection avoids distortion when a file spans several zones.
Honest caveat (put in README): UTM is conformal, not equal-area. Area error is about 0.1% at 2-3 degrees from the central meridian and up to about 0.2% at the zone edge, and grows outside the zone. The geodesic columns make this visible.
Rejected: geodesic only (ignores the stated requirement and is not what GIS users expect); custom equal-area CRS (exact area but non-standard and harder to explain).

**2B-3. Transform path: always source CRS -> EPSG:4326 once, then 4326 -> UTM per feature.**
Do the first hop vectorised with `GeoDataFrame.to_crs(4326)`. Output geometry needs 4326 anyway, so one path serves output and measurement. It also removes any dependence on the source CRS units (feet, etc.). Cost: one extra hop, error is negligible.
Rejected: direct source -> UTM (needs a second code path for output and for unit handling).
Zone selection uses the centroid of the 4326 geometry; planar degrees are fine here because it only picks a zone.

**2B-4. Storage: SQLite default, `DATABASE_URL` for Postgres, no PostGIS.**
The task needs no spatial queries, and a reviewer must be able to run it with zero setup. Geometry is stored as GeoJSON (JSON column, EPSG:4326). SQLAlchemy `JSON` works on SQLite and Postgres. Use `Base.metadata.create_all` on startup; Alembic is Future Scope.
Insert features in bulk: `session.execute(insert(Feature), rows)`, one commit per file. Add an index on `(file_id, feature_index)`.
PostGIS + spatial indexes belong in Future Scope together with spatial queries.

**2B-5. Zip handling: whitelist extraction; reject multiple shapefiles.**
Extract only `.shp .shx .dbf .prj .cpg` members, written to names we choose inside a temp dir (never the archive's own paths). This removes zip-slip by construction. Check total uncompressed size from `infolist()` before extracting.
If the zip holds more than one `.shp`, return `422` naming them. Merging would make CRS, indexes and attribute schemas ambiguous, and silently picking the first would surprise the user. Explicit error beats guessing. Processing all of them is Future Scope.
KML: read all layers (one per Folder) and concatenate in order; `feature_index` is global across the file.

**2B-6. Failure semantics: three levels.**
- Pre-check failures (extension, empty, too large): `4xx`, no DB record.
- Parse/processing failures (corrupt zip, unreadable KML, zero features, multiple shapefiles): record saved as `FAILED` with `error_message`, `422` response includes `file_id`.
- Per-feature failures: that feature gets `measurement_status = FAILED` plus a warning; the file still `COMPLETED`.
Unexpected exceptions: rollback, log, `500`.

**2B-7. Reader: GeoPandas + pyogrio.**
pyogrio is the default engine in GeoPandas 1.x and ships wheels with GDAL bundled, which matters on Windows. Fiona is the older path. A hand-written KML parser is only a fallback if the KML driver is missing in the environment.

**2B-8. Response shape: nested `measurements` object, per-feature `measurement_status`, `limit/offset` pagination.**
The nested object keeps non-measurable features (`null`) clean. Offset pagination is enough here; cursor pagination is overkill. Each feature returns both `crs` (source CRS of the file) and `geometry_crs` (always EPSG:4326) so the reviewer is never unsure what the coordinates mean.

**2B-9. Frontend: optional single static HTML page, only after all required phases pass.**
It adds visible value for little code, but also extra surface to review. If it needs any backend change, drop it.

**2B-10. Docker: `python:3.11-slim`, no apt GDAL.**
The pip wheels (shapely, pyproj, pyogrio) bundle their native libs, so slim works and the image stays small. Run as a non-root user and add a `HEALTHCHECK` on `/health`.

---

## 3. Project Structure

```
geo-measure-api/
├── app/
│   ├── main.py                # FastAPI app factory, router include, startup
│   ├── config.py              # Settings (env): DB URL, max upload size, etc.
│   ├── database.py            # Engine, SessionLocal, get_db dependency
│   ├── models.py              # SQLAlchemy models: UploadedFile, Feature
│   ├── schemas.py             # Pydantic response/request schemas
│   ├── exceptions.py          # Custom exceptions + FastAPI handlers
│   ├── api/
│   │   ├── __init__.py
│   │   └── files.py           # Routers only: thin, no business logic
│   ├── services/
│   │   ├── file_service.py    # Orchestrates upload -> parse -> measure -> persist
│   │   ├── parser.py          # Reads zip/kml -> GeoDataFrame, validates input
│   │   ├── crs.py             # CRS detection, UTM selection, transformers
│   │   └── measurement.py     # Area/length logic per geometry type
│   └── utils/
│       └── zip_safety.py      # Safe extraction (zip-slip, size limits)
├── tests/
│   ├── conftest.py            # Client fixture, temp DB, sample-file builders
│   ├── test_crs.py
│   ├── test_measurement.py
│   ├── test_parser.py
│   └── test_api_files.py
├── static/
│   └── index.html             # Optional demo page (Section 10)
├── sample_data/               # Small sample KML + zipped shapefile for demo
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml             # ruff config
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
└── README.md
```

**Rules**
- Routers: parse request, call a service, return a schema. Nothing else.
- Services: pure-ish functions, easy to unit test without HTTP.
- `measurement.py` and `crs.py` must be testable with no DB and no FastAPI.
- No global mutable state. DB session via dependency injection.

---

## 4. Data Model

**UploadedFile**
| Field | Type | Notes |
|---|---|---|
| id | UUID (str) | primary key |
| filename | str | original name |
| file_type | str | `kml` or `shapefile` |
| status | enum | `PROCESSING`, `COMPLETED`, `FAILED` |
| feature_count | int | |
| crs | str \| null | e.g. `EPSG:4326` |
| crs_assumed | bool | true if CRS was missing and defaulted |
| error_message | str \| null | set when status = FAILED |
| created_at | datetime (UTC) | |

**Feature**
| Field | Type | Notes |
|---|---|---|
| id | int | PK |
| file_id | FK → UploadedFile | indexed |
| feature_index | int | position in file |
| geometry_type | str | `Polygon`, `LineString`, `Point`, `MultiPolygon`, ... |
| geometry | JSON/text | GeoJSON geometry in EPSG:4326 |
| crs | str | source CRS of this file |
| properties | JSON | attributes (sanitize non-JSON values: dates, NaN, bytes) |
| measurement_status | enum | `MEASURED`, `NOT_REQUIRED`, `UNSUPPORTED`, `FAILED` |
| area_m2 | float \| null | |
| length_m | float \| null | |
| measurement_crs | str \| null | projected CRS used, e.g. `EPSG:32643` |
| geodesic_area_m2 / geodesic_length_m | float \| null | cross-check via `pyproj.Geod` |
| warnings | JSON list[str] | e.g. "geometry was invalid and repaired" |

---

## 5. CRS Handling (the core of the assignment: get this right)

1. **Determine source CRS**
   - Shapefile: from `.prj` via GeoPandas.
   - KML: always EPSG:4326 by spec.
   - If CRS is missing: assume EPSG:4326, set `crs_assumed = true`, add a warning. Never silently guess.
2. **Never compute area/length on degrees.**
3. **Select projected CRS per feature** (`crs.py`):
   - Transform feature to EPSG:4326 first (so we have lon/lat).
   - Take the feature's centroid (compute centroid in a safe way, e.g. from the 4326 geometry's representative point or bounds center).
   - UTM zone = `int((lon + 180) / 6) + 1`; north → `EPSG:326xx`, south → `EPSG:327xx`.
   - Latitudes beyond UTM range (|lat| > 84 or so): fallback to an equal-area CRS (`EPSG:6933`) and note it in warnings.
   - Use `pyproj.Transformer.from_crs(..., always_xy=True)`. **Axis order bugs are the #1 pitfall; always use `always_xy=True`.** Cache transformers (e.g. `functools.lru_cache`) per CRS pair.
4. **Calculate** in the projected CRS: `shapely.area` (m²) and `.length` (m).
5. **Cross-check with geodesic** using `pyproj.Geod(ellps="WGS84")`: `geometry_area_perimeter` and `geometry_length` on the 4326 geometry. Store as `geodesic_*`. README should compare both and explain differences (UTM distortion is small within a zone but grows for features spanning zones).
6. Document alternatives considered: single UTM zone per file, equal-area projection, geodesic-only, and why per-feature UTM was chosen.

---

## 6. Measurement Rules (`measurement.py`)

| Geometry | Behaviour |
|---|---|
| Polygon | area_m2 (+ geodesic). Perimeter optional. |
| MultiPolygon | sum of areas |
| LineString | length_m (+ geodesic) |
| MultiLineString | sum of lengths |
| Point / MultiPoint | `NOT_REQUIRED`, no measurement |
| GeometryCollection, LinearRing, others | `UNSUPPORTED`, graceful, no crash |
| Empty / null geometry | `UNSUPPORTED`, warning "empty geometry" |
| Invalid geometry (self-intersection) | `shapely.make_valid`, keep only the polygonal parts of the result (it can return a GeometryCollection), set warning, still measure |
| Z coordinates (KML often has altitude) | drop Z (`shapely.force_2d`) before measuring |

**A failure on one feature must never fail the whole file.** Wrap per-feature measurement in try/except, mark that feature `FAILED` with a warning, continue.

Return a small dataclass, e.g. `MeasurementResult(status, area_m2, length_m, crs, geodesic_area_m2, geodesic_length_m, warnings)`.

---

## 7. API Contract

Base path `/api`. All responses JSON. Error shape: `{"detail": "<message>"}`.

### `POST /api/files/` (multipart/form-data, field `file`)
- Accept `.kml` or `.zip` (zip must contain a `.shp` plus its `.shx` and `.dbf`).
- Validate extension, size limit (default 25 MB, configurable), non-empty.
- Process **synchronously** inside a plain `def` route (not `async def`, see 2B-1), return `201`:
```json
{
  "id": "6f1c...",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```
- Failure semantics (see 2B-6):
  - Cheap pre-checks fail (extension, empty file, over size limit): `4xx`, **no DB record**.
  - Parsing/processing fails (corrupt zip, unreadable KML, zero features, multiple shapefiles): record saved as `FAILED` with `error_message`; return `422` with `{"detail": "...", "file_id": "..."}` so `GET /api/files/{id}/` shows the reason.
  - Unexpected exception: roll back, log, return `500`.

### `GET /api/files/{id}/` → `200`
Same shape as above plus `crs_assumed`, `created_at`, `error_message`. `404` if unknown.

### `GET /api/files/{id}/measurements/` → `200`
Query params: `limit` (default 100, max 1000), `offset` (default 0).
```json
{
  "file_id": "6f1c...",
  "total": 120,
  "limit": 100,
  "offset": 0,
  "features": [
    {
      "index": 0,
      "geometry_type": "Polygon",
      "geometry": {"type": "Polygon", "coordinates": [[[77.59, 12.97], "..."]]},
      "crs": "EPSG:4326",
      "geometry_crs": "EPSG:4326",
      "properties": {"name": "Plot A"},
      "measurement_status": "MEASURED",
      "measurements": {
        "area_m2": 10234.5,
        "area_hectares": 1.02345,
        "measurement_crs": "EPSG:32643",
        "geodesic_area_m2": 10231.9
      },
      "warnings": []
    },
    {
      "index": 1,
      "geometry_type": "Point",
      "geometry": {"type": "Point", "coordinates": [77.6, 12.9]},
      "crs": "EPSG:4326",
      "geometry_crs": "EPSG:4326",
      "properties": {},
      "measurement_status": "NOT_REQUIRED",
      "measurements": null,
      "warnings": []
    }
  ]
}
```
Optional filter: `?geometry_type=Polygon`.

`crs` = source CRS of the uploaded file. `geometry_crs` = CRS of the returned geometry, always EPSG:4326 (GeoJSON, RFC 7946).

### `GET /health` → `{"status": "ok"}`

**Status codes:** 201, 200, 404, 413 (too large), 415 or 422 (bad type / unreadable file).

---

## 8. Edge Cases (each needs handling and ideally a test)

- Unsupported extension (`.txt`, `.geojson`, etc.).
- Zip without a `.shp`, or missing `.shx` / `.dbf`.
- Zip with multiple shapefiles: **reject** with `422` listing the `.shp` names (decided, see 2B-5).
- Zip-slip and zip bombs: extract only whitelisted members, write them under names we choose inside a temp dir, check total uncompressed size from `infolist()` first (`utils/zip_safety.py`). Always clean up with `TemporaryDirectory`; close file handles before reading, because Windows locks open files.
- KML with mixed geometry types, nested folders, placemarks with no geometry.
- KML with multiple layers/folders (read all layers, not just the first).
- Missing CRS / missing `.prj`.
- Projected source CRS (not 4326): transform correctly.
- Features that cross the antimeridian or span multiple UTM zones: warn.
- NaN / datetime / bytes in attributes: sanitize to JSON-safe values.
- Empty file, zero features.
- Large files: bulk-insert features, not one-by-one commits.

---

## 9. Testing Requirements

Generate fixtures **in code** (conftest) rather than committing big files. Small sample files in `sample_data/` are for demo only.

Must-have tests:
1. **Known-area polygon** (two assertions, see 2B-2):
   - Exact: build a 1000 m x 1000 m square in EPSG:32643 coordinates near Bengaluru, convert its corners to EPSG:4326, run the service. `area_m2` must equal 1,000,000 within 1e-6 relative error (round trip through the same projection).
   - Independent: `area_m2` must agree with the geodesic area within 0.3% (UTM scale distortion is about 0.1% this far from the central meridian).
2. **Known-length line**: a 1000 m line built in EPSG:32643 and converted to EPSG:4326 → `length_m` ≈ 1000 (1e-6 relative); geodesic length within 0.3%.
3. **Degrees guard**: assert the result is NOT the raw degree-based number.
4. UTM zone selection: Bengaluru → `EPSG:32643`; a southern-hemisphere point → `327xx`; polar → fallback.
5. Point → `NOT_REQUIRED`. GeometryCollection → `UNSUPPORTED`, no exception.
6. MultiPolygon sums parts. Invalid (bow-tie) polygon repaired with warning.
7. Missing CRS → assumed 4326, flag true.
8. Projected-CRS shapefile input (e.g. EPSG:32643) gives the same area as the 4326 version (within tolerance).
9. API: upload KML → 201; get file → 200; measurements → 200 with pagination; unknown id → 404; bad extension → 4xx; oversized → 413; corrupt zip → 422.
10. One bad feature does not fail the file.

Use a temp SQLite DB per test session (override `get_db`). Target meaningful coverage of `services/`; do not chase 100%.

---

## 10. Optional Frontend (single static HTML page): build ONLY after Section 12 phases 1–6 are done

Goal: make the demo visual and reviewable in 30 seconds. Keep it to **one file** `static/index.html`, served by FastAPI `StaticFiles` at `/`.

- File input + Upload button → `POST /api/files/`.
- Shows file info (id, status, CRS, feature count).
- Fetches measurements and renders a table (index, type, area/length, status, warnings).
- Leaflet map (CDN) draws the returned GeoJSON, popup shows measurements.
- Vanilla JS, no build step, no framework. Clean, minimal styling.
- Must not change API behaviour. If it adds complexity to the backend, skip it.

---

## 11. Deployment (optional, low priority)

- Provide `Dockerfile` (use a base image where GDAL wheels install cleanly, e.g. `python:3.11-slim` with `pyogrio`/`geopandas` wheels) and `docker-compose.yml` (app + volume for SQLite, optionally Postgres service).
- `README` must work **without** any deployment: `git clone` → run in <5 commands.
- If deploying a live demo: Docker-based web service on Render / Railway / Fly.io free tier. Note cold starts and ephemeral storage (SQLite resets on redeploy; fine for a demo). Put the live URL in the README only if it works reliably.

---

## 12. Build Order (follow strictly; commit after each phase)

1. **Scaffold**: repo, venv, requirements, `pyproject.toml` (ruff), `.gitignore`, FastAPI app with `/health`, config, DB session. Commit.
2. **Core geo logic (no API yet)**: `crs.py` + `measurement.py` with unit tests (Section 9 items 1–6). This is the heart; get it right first. Commit.
3. **Parser**: `parser.py` + `zip_safety.py` reading KML and zipped shapefile into a GeoDataFrame, with CRS detection and validation errors. Tests (items 7, 8). Commit.
4. **Persistence**: models, schemas, `file_service.py` orchestrating parse → measure → bulk insert. Commit.
5. **API routes**: the 3 endpoints + error handlers + pagination. API tests (items 9, 10). Commit.
6. **Docker + README**: Dockerfile, compose, full README. Commit.
7. **Optional frontend** (Section 10). Commit.
8. **Optional deploy** (Section 11). Commit.
9. **Final pass**: run `ruff check`, `ruff format`, full test suite, fresh-clone test following the README exactly. Tag `v1.0`.

---

## 13. Code Quality Rules

- Type hints on all functions; docstrings on public functions (one-liner is fine).
- Functions small and single-purpose; no function > ~40 lines without good reason.
- No bare `except:`. Catch specific exceptions; log with `logging`, never `print`.
- No magic numbers: constants at top of module or in `config.py`.
- No secrets in repo; `.env.example` only.
- Meaningful names; avoid abbreviations except `crs`, `utm`, `id`.
- Commit messages: imperative, small commits (`Add UTM zone selection`, not `update`).
- No dead code, no commented-out blocks, no unused dependencies.
- Don't over-engineer: no repository pattern, no DI frameworks, no Celery.

---

## 14. README.md Requirements

Sections, in this order:
1. **Overview** (2–3 lines) + optional live demo link / screenshot.
2. **Features**.
3. **Setup**: Windows PowerShell and Linux/macOS; Docker option.
4. **Run**: command + where to find `/docs`.
5. **Run tests**.
6. **API**: each endpoint with curl examples and example responses (copy from Section 7).
7. **Architecture**: folder layout, file-processing flow, measurement flow, CRS handling (short diagram or numbered steps).
8. **Design Decisions**: sync vs async processing, SQLite vs Postgres/PostGIS, per-feature UTM vs alternatives, geodesic cross-check, geometry stored as GeoJSON, what happens with missing CRS, multiple shapefiles in zip. State alternatives considered and why rejected.
9. **Known Limitations**.
10. **Learnings** (honest, specific: e.g. axis order with `always_xy`, why degree-based area is wrong, UTM distortion).
11. **Future Scope**: async processing (Celery/RQ + Redis) for big files, PostGIS + spatial indexes, GeoJSON/GeoPackage upload, GeoTIFF/drone orthomosaic support, auth + per-user files, vector tiles for large datasets, perimeter/centroid/bbox outputs, CSV export, CI via GitHub Actions.

Tone: clear, honest, no fluff, no marketing language.

---

## 15. Definition of Done

- [ ] All three endpoints work as specified; `/docs` renders cleanly.
- [ ] Known-area test passes within tolerance.
- [ ] Bad input and bad single features never crash the service.
- [ ] `pytest` green; `ruff check` clean.
- [ ] Every command was run through the project `.venv` interpreter (Section 1A); no global installs.
- [ ] Fresh clone + README steps run successfully (test on a clean venv and via Docker).
- [ ] README complete including Learnings and Future Scope.
- [ ] Public GitHub repo, no secrets, sensible commit history.
- [ ] Author can explain: why UTM, what `always_xy` does, why geodesic cross-check, why sync processing.
