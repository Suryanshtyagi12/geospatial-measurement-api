from app.services.crs import determine_utm_crs, get_transformer


def test_determine_utm_crs_bengaluru():
    # Bengaluru ~ 77.6E, 12.9N
    crs = determine_utm_crs(77.6, 12.9)
    assert crs == "EPSG:32643"


def test_determine_utm_crs_southern_hemisphere():
    # South of equator, same longitude
    crs = determine_utm_crs(77.6, -12.9)
    assert crs == "EPSG:32743"


def test_determine_utm_crs_polar():
    # Polar fallback
    crs = determine_utm_crs(0.0, 85.0)
    assert crs == "EPSG:6933"


def test_transformer_always_xy():
    # Check that the transformer honors always_xy=True
    transformer = get_transformer("EPSG:4326", "EPSG:32643")
    # For EPSG:32643, central meridian is 75E.
    # If we pass (lon=75, lat=0), X should be 500000, Y should be 0.
    x, y = transformer.transform(75.0, 0.0)
    assert abs(x - 500000.0) < 1e-6
    assert abs(y - 0.0) < 1e-6
