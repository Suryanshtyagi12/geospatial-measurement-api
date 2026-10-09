import functools
from pyproj import CRS, Transformer

@functools.lru_cache(maxsize=128)
def get_transformer(source_crs: str, target_crs: str) -> Transformer:
    """
    Returns a pyproj Transformer between two CRSs, safely handling axis orders.
    Always uses always_xy=True to avoid axis order bugs (lon/lat vs lat/lon).
    """
    return Transformer.from_crs(source_crs, target_crs, always_xy=True)

def determine_utm_crs(lon: float, lat: float) -> str:
    """
    Selects the appropriate UTM zone for a given longitude and latitude.
    Falls back to a global equal-area CRS (EPSG:6933) near the poles (|lat| > 84).
    """
    if abs(lat) > 84:
        return "EPSG:6933" # Equal-area fallback for polar regions
    
    zone_number = int((lon + 180) / 6) + 1
    if lat >= 0:
        return f"EPSG:326{zone_number:02d}"
    else:
        return f"EPSG:327{zone_number:02d}"
