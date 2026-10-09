import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import pyogrio
from fastapi import HTTPException


@dataclass
class ParseResult:
    gdf: gpd.GeoDataFrame
    crs_str: str
    crs_assumed: bool
    feature_count: int


def _sanitize_properties(df: gpd.GeoDataFrame) -> List[Dict]:
    """Sanitize GeoDataFrame properties for JSON serialization (e.g. NaN, dates to strings)."""
    # Drop geometry column for properties
    df_no_geom = df.drop(columns=["geometry"])
    # Replace NaN/NaT with None
    df_clean = df_no_geom.replace({float("nan"): None})
    records = df_clean.to_dict(orient="records")
    # Ensure types are JSON serializable
    for row in records:
        for k, v in row.items():
            if v is not None:
                if isinstance(v, (bytes, bytearray)):
                    row[k] = "<bytes>"
                elif not isinstance(v, (int, float, str, bool)):
                    row[k] = str(v)
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None
    return records


def parse_geospatial_file(file_path: str, file_type: str) -> ParseResult:
    """
    Reads a geospatial file (KML or Shapefile) into a GeoDataFrame using pyogrio.
    Handles CRS detection and layer concatenation (for KML).
    """
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    gdfs = []

    try:
        if file_type == "kml":
            # KML can have multiple layers (Folders). pyogrio can list layers.
            layers = pyogrio.list_layers(file_path)
            for layer_info in layers:
                layer_name = layer_info[0]
                try:
                    df = pyogrio.read_dataframe(file_path, layer=layer_name)
                    if not df.empty:
                        gdfs.append(df)
                except Exception:
                    # Some layers might be empty or unreadable; skip them safely.
                    pass
        elif file_type == "shapefile":
            df = pyogrio.read_dataframe(file_path)
            if not df.empty:
                gdfs.append(df)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type.")
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Failed to read file with pyogrio: {str(e)}"
        )

    if not gdfs:
        raise ValueError("File contains zero features or could not be parsed.")

    # Concatenate all layers (if KML) or just use the single one
    final_gdf = gpd.GeoDataFrame(gpd.pd.concat(gdfs, ignore_index=True))
    if final_gdf.empty:
        raise ValueError("File contains zero valid features.")

    # Determine CRS
    crs_assumed = False
    if final_gdf.crs is None:
        crs_assumed = True
        final_gdf.set_crs("EPSG:4326", inplace=True)
        crs_str = "EPSG:4326"
    else:
        # Use authority representation if available (e.g. EPSG:4326)
        authority = final_gdf.crs.to_authority()
        if authority:
            crs_str = f"{authority[0]}:{authority[1]}"
        else:
            crs_str = final_gdf.crs.to_string()

    # Pre-transform properties to JSON-safe dicts and attach back to df (or we can do this later)
    # To keep the returned structure simple, we'll let the service layer handle row-by-row iteration.

    return ParseResult(
        gdf=final_gdf,
        crs_str=crs_str,
        crs_assumed=crs_assumed,
        feature_count=len(final_gdf),
    )
