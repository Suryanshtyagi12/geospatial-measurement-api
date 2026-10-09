import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..exceptions import APIException
from ..models import Feature, UploadedFile
from ..schemas import (
    FeatureResponse,
    FileMeasurementsResponse,
    MeasurementData,
    UploadedFileResponse,
)
from ..services.file_service import process_and_save_file
from ..utils.zip_safety import extract_shapefile_safe

router = APIRouter(prefix="/api/files", tags=["Files"])


@router.post(
    "/", response_model=UploadedFileResponse, status_code=status.HTTP_201_CREATED
)
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Pre-checks (cheap, 4xx)
    ext = Path(file.filename).suffix.lower()
    if ext not in [".zip", ".kml"]:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file extension: {ext}. Allowed: .zip, .kml",
        )

    # Read bytes to check size (in memory for now, up to 25MB is fine)
    # Actually, we can save it directly to temp file and check size there.
    try:
        file_bytes = file.file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read file.")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large.")

    # 2. Create DB record as PROCESSING
    file_type = "kml" if ext == ".kml" else "shapefile"
    db_file = UploadedFile(
        filename=file.filename, file_type=file_type, status="PROCESSING"
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # 3. Synchronous parsing & processing block
    with tempfile.TemporaryDirectory() as td:
        temp_path = os.path.join(td, file.filename)
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        try:
            target_file_path = temp_path

            if file_type == "shapefile":
                # Safe extraction and validation
                target_file_path = extract_shapefile_safe(temp_path, td)

            # Process
            db_file = process_and_save_file(
                db, db_file.id, target_file_path, file.filename, file_type
            )

            if db_file.status == "FAILED":
                # Throw a 422 if parsing fails
                raise APIException(
                    status_code=422, detail=db_file.error_message, file_id=db_file.id
                )

        except APIException:
            raise
        except zipfile.BadZipFile as e:
            db_file.status = "FAILED"
            db_file.error_message = f"Corrupt or invalid zip file: {str(e)}"
            db.commit()
            raise APIException(
                status_code=422, detail=db_file.error_message, file_id=db_file.id
            )
        except HTTPException as he:
            # Re-wrap HTTPException as APIException with file_id
            db_file.status = "FAILED"
            db_file.error_message = he.detail
            db.commit()
            raise APIException(
                status_code=he.status_code, detail=he.detail, file_id=db_file.id
            )
        except Exception as e:
            # Unexpected exception (already handled in process_and_save_file, but just in case)
            db_file.status = "FAILED"
            db_file.error_message = str(e)
            db.commit()
            raise APIException(status_code=500, detail=str(e), file_id=db_file.id)

    return db_file


@router.get("/{id}/", response_model=UploadedFileResponse)
def get_file(id: str, db: Session = Depends(get_db)):
    db_file = db.query(UploadedFile).filter(UploadedFile.id == id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


@router.get("/{id}/measurements/", response_model=FileMeasurementsResponse)
def get_file_measurements(
    id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    geometry_type: str = Query(None),
    db: Session = Depends(get_db),
):
    db_file = db.query(UploadedFile).filter(UploadedFile.id == id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    query = db.query(Feature).filter(Feature.file_id == id)
    if geometry_type:
        query = query.filter(Feature.geometry_type == geometry_type)

    total = query.count()
    features = query.order_by(Feature.feature_index).offset(offset).limit(limit).all()

    feature_responses = []
    for f in features:
        measurements = None
        if f.area_m2 is not None or f.length_m is not None:
            measurements = MeasurementData(
                area_m2=f.area_m2,
                length_m=f.length_m,
                measurement_crs=f.measurement_crs,
                geodesic_area_m2=f.geodesic_area_m2,
                geodesic_length_m=f.geodesic_length_m,
            )

        feature_responses.append(
            FeatureResponse(
                index=f.feature_index,
                geometry_type=f.geometry_type,
                geometry=f.geometry,
                crs=f.crs,
                geometry_crs="EPSG:4326",  # Output is always EPSG:4326
                properties=f.properties,
                measurement_status=f.measurement_status,
                measurements=measurements,
                warnings=f.warnings,
            )
        )

    return FileMeasurementsResponse(
        file_id=id, total=total, limit=limit, offset=offset, features=feature_responses
    )
