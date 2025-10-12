from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from database import Base
import enum

class RoofType(enum.Enum):
    FLOATING = "floating"
    FIXED = "fixed"
    UNKNOWN = "unknown"

class SatelliteType(enum.Enum):
    SENTINEL_1 = "sentinel-1"
    SENTINEL_2 = "sentinel-2"
    LANDSAT_8 = "landsat-8"
    LANDSAT_9 = "landsat-9"

class AnalysisMethod(enum.Enum):
    SHADOW_OPTICAL = "shadow_optical"
    SAR_BACKSCATTER = "sar_backscatter"
    ML_DETECTION = "ml_detection"

class Site(Base):
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False)
    region = Column(String)
    timezone = Column(String, default="UTC")
    
    # Bounding box for satellite imagery
    bbox_geom = Column(Geometry('POLYGON', srid=4326))
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    
    # Metadata
    source = Column(String)  # OSM, manual, etc.
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tanks = relationship("Tank", back_populates="site")
    scenes = relationship("Scene", back_populates="site")

class Tank(Base):
    __tablename__ = "tanks"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    
    # Tank geometry and properties
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    estimated_diameter_m = Column(Float)
    wall_height_m = Column(Float)
    roof_type = Column(String, default=RoofType.FLOATING.value)
    
    # Tank identification
    tank_number = Column(String)
    operator = Column(String)
    capacity_bbl = Column(Float)  # barrels
    
    # Metadata
    source = Column(String)  # OSM, manual, satellite detection
    confidence = Column(Float, default=0.5)  # 0-1 confidence in detection
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    site = relationship("Site", back_populates="tanks")
    measurements = relationship("Measurement", back_populates="tank")

    @property
    def lat(self):
        if self.geom:
            point = to_shape(self.geom)
            return point.y
        return None

    @property
    def lon(self):
        if self.geom:
            point = to_shape(self.geom)
            return point.x
        return None

class Scene(Base):
    __tablename__ = "scenes"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    
    # Satellite metadata
    satellite = Column(String, nullable=False)  # sentinel-1, sentinel-2, etc.
    sensor = Column(String)  # MSI, SAR, etc.
    scene_id = Column(String, nullable=False, unique=True)
    
    # Temporal info
    acquisition_time = Column(DateTime(timezone=True), nullable=False)
    processed_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # Geometric info
    sun_elevation = Column(Float)  # degrees, for optical imagery
    sun_azimuth = Column(Float)   # degrees, for optical imagery
    cloud_coverage = Column(Float)  # percentage
    
    # File paths and URLs
    raw_data_url = Column(String)
    processed_data_path = Column(String)
    thumbnail_path = Column(String)
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    processing_error = Column(Text)
    
    # Quality metrics
    quality_score = Column(Float)  # 0-1 overall quality
    extra_metadata = Column(JSON)  # Additional metadata
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    site = relationship("Site", back_populates="scenes")
    measurements = relationship("Measurement", back_populates="scene")

class Measurement(Base):
    __tablename__ = "measurements"
    
    id = Column(Integer, primary_key=True, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id"), nullable=False)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    
    # Analysis method and results
    method = Column(String, nullable=False)  # shadow_optical, sar_backscatter, etc.
    roof_height_m = Column(Float)  # estimated roof height above tank bottom
    fill_fraction = Column(Float)  # 0-1 estimated fill level
    volume_bbl = Column(Float)     # estimated volume in barrels
    
    # Quality and confidence
    confidence = Column(Float, default=0.5)  # 0-1 confidence in measurement
    shadow_length_px = Column(Float)  # for optical shadow method
    shadow_angle_deg = Column(Float)  # for optical shadow method
    
    # Processing metadata
    processing_time_ms = Column(Integer)
    algorithm_version = Column(String)
    parameters = Column(JSON)  # algorithm parameters used
    
    # Quality flags
    is_outlier = Column(Boolean, default=False)
    quality_flags = Column(JSON)  # various quality indicators
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    tank = relationship("Tank", back_populates="measurements")
    scene = relationship("Scene", back_populates="measurements")

class Aggregate(Base):
    __tablename__ = "aggregates"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    
    # Temporal aggregation
    date = Column(DateTime(timezone=True), nullable=False)
    aggregation_period = Column(String, default="daily")  # daily, weekly, monthly
    
    # Aggregated measurements
    total_volume_bbl = Column(Float)
    average_fill_fraction = Column(Float)
    tank_count = Column(Integer)  # number of tanks measured
    active_tank_count = Column(Integer)  # tanks with recent measurements
    
    # Quality metrics
    overall_confidence = Column(Float)
    measurement_count = Column(Integer)
    outlier_count = Column(Integer)
    
    # Trend indicators
    volume_change_bbl = Column(Float)  # change from previous period
    volume_change_pct = Column(Float)  # percentage change
    trend_direction = Column(String)   # increasing, decreasing, stable
    
    # Validation against external data
    eia_volume_bbl = Column(Float)     # EIA reported volume (if available)
    validation_error_pct = Column(Float)  # error vs EIA data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    site = relationship("Site")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"))
    tank_id = Column(Integer, ForeignKey("tanks.id"))
    
    # Alert details
    alert_type = Column(String, nullable=False)  # volume_spike, tank_offline, etc.
    severity = Column(String, default="medium")  # low, medium, high, critical
    title = Column(String, nullable=False)
    description = Column(Text)
    
    # Alert data
    trigger_value = Column(Float)
    threshold_value = Column(Float)
    extra_metadata = Column(JSON)
    
    # Status
    is_active = Column(Boolean, default=True)
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    site = relationship("Site")
    tank = relationship("Tank")
