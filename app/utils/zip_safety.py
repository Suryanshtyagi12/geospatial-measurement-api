import zipfile
import os
from pathlib import Path
from fastapi import HTTPException
from ..config import settings

ALLOWED_EXTENSIONS = {'.shp', '.shx', '.dbf', '.prj', '.cpg'}

def extract_shapefile_safe(zip_path: str, temp_dir: str) -> str:
    """
    Safely extracts a shapefile from a zip archive to a temporary directory.
    - Prevents zip-slip by ignoring original paths and writing to secure names.
    - Limits total uncompressed size.
    - Ensures exactly one .shp file exists; rejects if multiple or none.
    - Requires .shp, .shx, and .dbf to be present.
    Returns the path to the extracted .shp file.
    """
    temp_dir_path = Path(temp_dir)
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Check uncompressed size
        total_size = sum(info.file_size for info in zf.infolist())
        if total_size > max_size_bytes:
            raise HTTPException(status_code=413, detail="Uncompressed size exceeds limit.")

        # Identify shapefiles
        shp_members = [m for m in zf.infolist() if m.filename.lower().endswith('.shp')]
        if len(shp_members) == 0:
            raise HTTPException(status_code=422, detail="No .shp file found in the archive.")
        if len(shp_members) > 1:
            shp_names = [Path(m.filename).name for m in shp_members]
            raise HTTPException(status_code=422, detail=f"Multiple shapefiles found: {shp_names}. Please upload an archive with exactly one shapefile.")

        base_shp_name = Path(shp_members[0].filename).stem

        # Extract only allowed extensions matching the base shapefile name
        extracted_shp_path = None
        has_shx = False
        has_dbf = False

        for member in zf.infolist():
            file_path = Path(member.filename)
            ext = file_path.suffix.lower()
            
            if ext in ALLOWED_EXTENSIONS and file_path.stem == base_shp_name:
                # Write securely to temp_dir (ignore member's directory structure)
                safe_name = f"uploaded_shapefile{ext}"
                dest_path = temp_dir_path / safe_name
                
                with zf.open(member) as source, open(dest_path, "wb") as target:
                    target.write(source.read())
                
                if ext == '.shp':
                    extracted_shp_path = dest_path
                elif ext == '.shx':
                    has_shx = True
                elif ext == '.dbf':
                    has_dbf = True

        if not extracted_shp_path or not has_shx or not has_dbf:
            raise HTTPException(status_code=422, detail="Archive must contain matching .shp, .shx, and .dbf files.")

        return str(extracted_shp_path)
