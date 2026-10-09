import logging

from shapely.geometry import mapping
from sqlalchemy.orm import Session

from ..models import Feature, UploadedFile
from .measurement import measure_feature
from .parser import _sanitize_properties, parse_geospatial_file

logger = logging.getLogger(__name__)


def process_and_save_file(
    db: Session, file_id: str, file_path: str, filename: str, file_type: str
) -> UploadedFile:
    """
    Orchestrates parsing, measuring, and saving to DB.
    The UploadedFile record must already be created in PROCESSING state.
    """
    db_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not db_file:
        raise ValueError(f"UploadedFile {file_id} not found in database.")

    try:
        # 1. Parse File
        parse_result = parse_geospatial_file(file_path, file_type)
        gdf = parse_result.gdf

        # Update file metadata
        db_file.feature_count = parse_result.feature_count
        db_file.crs = parse_result.crs_str
        db_file.crs_assumed = parse_result.crs_assumed

        # 2. Extract properties & geometry
        properties_list = _sanitize_properties(gdf)

        # Ensure we always transform geometry to EPSG:4326 for DB storage and output
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        feature_objects = []

        # 3. Measure & Build Feature Models
        for idx, row in gdf.iterrows():
            geom = row.geometry
            props = properties_list[idx]

            # GeoJSON geometry
            geom_json = mapping(geom) if geom else None
            geom_type = geom.geom_type if geom else "None"

            # Measure
            try:
                meas_result = measure_feature(geom)
            except Exception as e:
                # Per-feature failure does not fail the whole file
                meas_result = measure_feature(None)  # Returns UNSUPPORTED with warning
                meas_result.status = "FAILED"
                meas_result.warnings.append(f"Measurement failed: {str(e)}")

            # Build Feature
            db_feature = Feature(
                file_id=db_file.id,
                feature_index=idx,
                geometry_type=geom_type,
                geometry=geom_json or {},
                crs=parse_result.crs_str,
                properties=props,
                measurement_status=meas_result.status,
                area_m2=meas_result.area_m2,
                length_m=meas_result.length_m,
                measurement_crs=meas_result.measurement_crs,
                geodesic_area_m2=meas_result.geodesic_area_m2,
                geodesic_length_m=meas_result.geodesic_length_m,
                warnings=meas_result.warnings,
            )
            feature_objects.append(db_feature)

        # 4. Bulk Insert Features
        db.bulk_save_objects(feature_objects)
        db_file.status = "COMPLETED"
        db.commit()

    except Exception as e:
        logger.error(f"Failed processing file {file_id}: {e}", exc_info=True)
        db.rollback()
        # Fetch again because rollback clears it
        db_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        db_file.status = "FAILED"
        db_file.error_message = str(e)
        db.commit()

    return db_file
