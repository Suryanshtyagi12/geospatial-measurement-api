from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MeasurementResult:
    status: str
    area_m2: Optional[float] = None
    length_m: Optional[float] = None
    measurement_crs: Optional[str] = None
    geodesic_area_m2: Optional[float] = None
    geodesic_length_m: Optional[float] = None
    warnings: Optional[List[str]] = None
