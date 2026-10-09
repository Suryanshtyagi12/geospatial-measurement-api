from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

# Common
class ErrorResponse(BaseModel):
    detail: str
    file_id: Optional[str] = None

# File Responses
class UploadedFileResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: Optional[str]
    status: str
    # Fields returned on GET
    crs_assumed: Optional[bool] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Measurement Responses
class MeasurementData(BaseModel):
    area_m2: Optional[float] = None
    length_m: Optional[float] = None
    measurement_crs: Optional[str] = None
    geodesic_area_m2: Optional[float] = None
    geodesic_length_m: Optional[float] = None

class FeatureResponse(BaseModel):
    index: int
    geometry_type: str
    geometry: Dict[str, Any]
    crs: str
    geometry_crs: str
    properties: Dict[str, Any]
    measurement_status: str
    measurements: Optional[MeasurementData] = None
    warnings: List[str]

class FileMeasurementsResponse(BaseModel):
    file_id: str
    total: int
    limit: int
    offset: int
    features: List[FeatureResponse]
