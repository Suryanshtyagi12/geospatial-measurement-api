import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from .database import Base

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False) # 'kml' or 'shapefile'
    status = Column(String, nullable=False) # 'PROCESSING', 'COMPLETED', 'FAILED'
    feature_count = Column(Integer, default=0)
    crs = Column(String, nullable=True)
    crs_assumed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    features = relationship("Feature", back_populates="file", cascade="all, delete-orphan")


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False)
    feature_index = Column(Integer, nullable=False)
    geometry_type = Column(String, nullable=False)
    geometry = Column(JSON, nullable=False) # GeoJSON geometry
    crs = Column(String, nullable=False) # source CRS of the file
    properties = Column(JSON, nullable=False) # attributes
    
    measurement_status = Column(String, nullable=False) # 'MEASURED', 'NOT_REQUIRED', 'UNSUPPORTED', 'FAILED'
    area_m2 = Column(Float, nullable=True)
    length_m = Column(Float, nullable=True)
    measurement_crs = Column(String, nullable=True)
    geodesic_area_m2 = Column(Float, nullable=True)
    geodesic_length_m = Column(Float, nullable=True)
    warnings = Column(JSON, nullable=False, default=list) # JSON list[str]

    file = relationship("UploadedFile", back_populates="features")

    __table_args__ = (
        Index('idx_file_feature', 'file_id', 'feature_index'),
    )
