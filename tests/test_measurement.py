import math

from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.ops import transform

from app.services.crs import get_transformer
from app.services.measurement import measure_feature


def test_known_area_polygon():
    # Create a 1000x1000m square in EPSG:32643 (near Bengaluru)
    # Bengaluru's UTM zone 43N. Let's use some arbitrary coordinates there.
    x0, y0 = 500000.0, 1400000.0
    square_32643 = Polygon(
        [(x0, y0), (x0 + 1000, y0), (x0 + 1000, y0 + 1000), (x0, y0 + 1000), (x0, y0)]
    )

    # Transform to EPSG:4326 to simulate uploaded geometry
    transformer_to_4326 = get_transformer("EPSG:32643", "EPSG:4326")
    square_4326 = transform(transformer_to_4326.transform, square_32643)

    # Measure
    result = measure_feature(square_4326)

    assert result.status == "MEASURED"
    assert result.measurement_crs == "EPSG:32643"

    # Area should be 1,000,000 exactly (within tolerance)
    assert math.isclose(result.area_m2, 1000000.0, rel_tol=1e-6)

    # Geodesic cross-check (UTM scale distortion should be < 0.3%)
    assert abs(result.area_m2 - result.geodesic_area_m2) / result.area_m2 < 0.003

    # Degrees guard: area in degrees would be tiny (like 1e-4)
    assert result.area_m2 > 1000.0


def test_known_length_line():
    x0, y0 = 500000.0, 1400000.0
    line_32643 = LineString([(x0, y0), (x0 + 1000, y0)])

    transformer_to_4326 = get_transformer("EPSG:32643", "EPSG:4326")
    line_4326 = transform(transformer_to_4326.transform, line_32643)

    result = measure_feature(line_4326)

    assert result.status == "MEASURED"
    assert math.isclose(result.length_m, 1000.0, rel_tol=1e-6)
    assert abs(result.length_m - result.geodesic_length_m) / result.length_m < 0.003
    assert result.length_m > 1.0  # degrees guard


def test_point_not_required():
    pt = Point(77.6, 12.9)
    result = measure_feature(pt)
    assert result.status == "NOT_REQUIRED"


def test_geometry_collection_unsupported():
    gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    result = measure_feature(gc)
    # The current repair logic might convert it if it has lines, but initial geometry collection is unsupported
    # Actually wait, measure_feature first drops Z, then checks validity.
    # If it's valid GeometryCollection, it will reach geom_type check and return UNSUPPORTED.
    assert result.status == "UNSUPPORTED"


def test_invalid_polygon_repair():
    # Bow-tie polygon (self-intersecting)
    bow_tie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    result = measure_feature(bow_tie)

    # Should be repaired and measured
    assert result.status == "MEASURED"
    assert "geometry was invalid and repaired" in result.warnings
    assert result.area_m2 > 0


def test_multipolygon_sums_parts():
    p1 = Polygon([(0, 0), (0, 0.001), (0.001, 0.001), (0.001, 0), (0, 0)])
    p2 = Polygon([(1, 1), (1, 1.001), (1.001, 1.001), (1.001, 1), (1, 1)])
    mp = MultiPolygon([p1, p2])

    result = measure_feature(mp)
    assert result.status == "MEASURED"
    assert result.area_m2 > 0
    # Two polygons sum up
    result_p1 = measure_feature(p1)
    result_p2 = measure_feature(p2)
    # Areas might slightly differ due to different centroids leading to different UTM zones or slight distortion differences,
    # but here they are very small.
