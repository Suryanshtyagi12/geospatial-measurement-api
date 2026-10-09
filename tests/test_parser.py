import os
import zipfile
import tempfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
import pytest
from fastapi import HTTPException
from app.utils.zip_safety import extract_shapefile_safe
from app.services.parser import parse_geospatial_file

def create_dummy_shapefile(temp_dir: str, crs="EPSG:4326", basename="test"):
    # Create a small square polygon
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame([{'name': 'square'}], geometry=[poly], crs=crs)
    shp_path = os.path.join(temp_dir, f"{basename}.shp")
    # Write to shapefile
    gdf.to_file(shp_path, driver="ESRI Shapefile")
    return shp_path

def test_extract_shapefile_safe():
    with tempfile.TemporaryDirectory() as td_source, tempfile.TemporaryDirectory() as td_dest:
        # 1. Create a dummy shapefile
        shp_path = create_dummy_shapefile(td_source)
        base = Path(shp_path).stem
        
        # 2. Zip it
        zip_path = os.path.join(td_source, "archive.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                fpath = os.path.join(td_source, f"{base}{ext}")
                if os.path.exists(fpath):
                    zf.write(fpath, arcname=f"{base}{ext}")

        # 3. Test extraction
        extracted = extract_shapefile_safe(zip_path, td_dest)
        assert extracted.endswith("uploaded_shapefile.shp")
        assert os.path.exists(extracted)

def test_parse_missing_crs():
    with tempfile.TemporaryDirectory() as td:
        shp_path = create_dummy_shapefile(td, crs=None) # No CRS
        result = parse_geospatial_file(shp_path, "shapefile")
        assert result.crs_assumed is True
        assert result.crs_str == "EPSG:4326"

def test_parse_projected_crs():
    with tempfile.TemporaryDirectory() as td:
        shp_path = create_dummy_shapefile(td, crs="EPSG:32643")
        result = parse_geospatial_file(shp_path, "shapefile")
        assert result.crs_assumed is False
        assert result.crs_str == "EPSG:32643"

def test_multiple_shapefiles_rejection():
    with tempfile.TemporaryDirectory() as td_source, tempfile.TemporaryDirectory() as td_dest:
        # Create two different shapefiles
        create_dummy_shapefile(td_source, basename="test1")
        create_dummy_shapefile(td_source, basename="test2")
        
        zip_path = os.path.join(td_source, "archive.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for base in ["test1", "test2"]:
                for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                    fpath = os.path.join(td_source, f"{base}{ext}")
                    if os.path.exists(fpath):
                        zf.write(fpath, arcname=f"{base}{ext}")

        with pytest.raises(HTTPException) as excinfo:
            extract_shapefile_safe(zip_path, td_dest)
        assert excinfo.value.status_code == 422
        assert "Multiple shapefiles found" in str(excinfo.value.detail)
