import shapely
from shapely.geometry.base import BaseGeometry
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection
from shapely.ops import transform
from pyproj import Geod
from .crs import get_transformer, determine_utm_crs
from ..schemas_internal import MeasurementResult

geod = Geod(ellps="WGS84")

def measure_feature(geom_4326: BaseGeometry) -> MeasurementResult:
    warnings = []
    
    if geom_4326 is None or geom_4326.is_empty:
        warnings.append("empty geometry")
        return MeasurementResult(status="UNSUPPORTED", warnings=warnings)

    # 1. Drop Z coordinates if present
    geom_4326 = shapely.force_2d(geom_4326)

    # 2. Make valid if self-intersecting
    if not geom_4326.is_valid:
        warnings.append("geometry was invalid and repaired")
        geom_4326 = shapely.make_valid(geom_4326)

        # If it's a polygon that became a geometry collection, we should try to keep polygonal parts
        if isinstance(geom_4326, GeometryCollection):
            polygons = [g for g in geom_4326.geoms if isinstance(g, (Polygon, MultiPolygon))]
            if polygons:
                geom_4326 = MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
            else:
                lines = [g for g in geom_4326.geoms if isinstance(g, (LineString, MultiLineString))]
                if lines:
                    geom_4326 = MultiLineString(lines) if len(lines) > 1 else lines[0]
                else:
                    return MeasurementResult(status="UNSUPPORTED", warnings=warnings)

    geom_type = geom_4326.geom_type

    if geom_type in ("Point", "MultiPoint"):
        return MeasurementResult(status="NOT_REQUIRED", warnings=warnings)
    
    if geom_type not in ("Polygon", "MultiPolygon", "LineString", "MultiLineString"):
        return MeasurementResult(status="UNSUPPORTED", warnings=warnings)

    # 3. Determine representative point for CRS selection
    rep_point = geom_4326.representative_point()
    lon, lat = rep_point.x, rep_point.y
    
    projected_crs = determine_utm_crs(lon, lat)
    if projected_crs == "EPSG:6933":
        warnings.append("feature is beyond UTM limits, using equal-area fallback (EPSG:6933)")

    # 4. Transform to projected CRS
    transformer = get_transformer("EPSG:4326", projected_crs)
    geom_proj = transform(transformer.transform, geom_4326)

    # 5. Measure & Geodesic cross-check
    area_m2 = None
    length_m = None
    geodesic_area_m2 = None
    geodesic_length_m = None

    if geom_type in ("Polygon", "MultiPolygon"):
        area_m2 = geom_proj.area
        geodesic_area_m2, _ = geod.geometry_area_perimeter(geom_4326)
        geodesic_area_m2 = abs(geodesic_area_m2) # Area can be negative depending on winding order
    elif geom_type in ("LineString", "MultiLineString"):
        length_m = geom_proj.length
        geodesic_length_m = geod.geometry_length(geom_4326)

    return MeasurementResult(
        status="MEASURED",
        area_m2=area_m2,
        length_m=length_m,
        measurement_crs=projected_crs,
        geodesic_area_m2=geodesic_area_m2,
        geodesic_length_m=geodesic_length_m,
        warnings=warnings
    )
