from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class RoofType(str, Enum):
    FLOATING = "floating"
    FIXED = "fixed"
    UNKNOWN = "unknown"

class SatelliteType(str, Enum):
    SENTINEL_1 = "sentinel-1"
    SENTINEL_2 = "sentinel-2"
    LANDSAT_8 = "landsat-8"
    LANDSAT_9 = "landsat-9"

class AnalysisMethod(str, Enum):
    SHADOW_OPTICAL = "shadow_optical"
    SAR_BACKSCATTER = "sar_backscatter"
    ML_DETECTION = "ml_detection"

# Site schemas
class SiteBase(BaseModel):
    name: str
    country: str
    region: Optional[str] = None
    timezone: str = "UTC"
    center_lat: float
    center_lon: float
    source: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True

class SiteCreate(SiteBase):
    pass

class SiteUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class Site(SiteBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Tank schemas
class TankBase(BaseModel):
    site_id: int
    estimated_diameter_m: Optional[float] = None
    wall_height_m: Optional[float] = None
    roof_type: RoofType = RoofType.FLOATING
    tank_number: Optional[str] = None
    operator: Optional[str] = None
    capacity_bbl: Optional[float] = None
    source: Optional[str] = None
    confidence: float = 0.5
    is_active: bool = True

class TankCreate(TankBase):
    lat: float
    lon: float

class TankUpdate(BaseModel):
    estimated_diameter_m: Optional[float] = None
    wall_height_m: Optional[float] = None
    roof_type: Optional[RoofType] = None
    tank_number: Optional[str] = None
    operator: Optional[str] = None
    capacity_bbl: Optional[float] = None
    confidence: Optional[float] = None
    is_active: Optional[bool] = None

class Tank(TankBase):
    id: int
    lat: float
    lon: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Scene schemas
class SceneBase(BaseModel):
    site_id: int
    satellite: str
    sensor: Optional[str] = None
    scene_id: str
    acquisition_time: datetime
    sun_elevation: Optional[float] = None
    sun_azimuth: Optional[float] = None
    cloud_coverage: Optional[float] = None
    raw_data_url: Optional[str] = None
    processed_data_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    quality_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class SceneCreate(SceneBase):
    pass

class Scene(SceneBase):
    id: int
    processed_time: datetime
    is_processed: bool = False
    processing_error: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Measurement schemas
class MeasurementBase(BaseModel):
    tank_id: int
    scene_id: int
    method: AnalysisMethod
    roof_height_m: Optional[float] = None
    fill_fraction: Optional[float] = None
    volume_bbl: Optional[float] = None
    confidence: float = 0.5
    shadow_length_px: Optional[float] = None
    shadow_angle_deg: Optional[float] = None
    processing_time_ms: Optional[int] = None
    algorithm_version: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_outlier: bool = False
    quality_flags: Optional[Dict[str, Any]] = None

class MeasurementCreate(MeasurementBase):
    pass

class Measurement(MeasurementBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Aggregate schemas
class AggregateBase(BaseModel):
    site_id: int
    date: datetime
    aggregation_period: str = "daily"
    total_volume_bbl: Optional[float] = None
    average_fill_fraction: Optional[float] = None
    tank_count: Optional[int] = None
    active_tank_count: Optional[int] = None
    overall_confidence: Optional[float] = None
    measurement_count: Optional[int] = None
    outlier_count: Optional[int] = None
    volume_change_bbl: Optional[float] = None
    volume_change_pct: Optional[float] = None
    trend_direction: Optional[str] = None
    eia_volume_bbl: Optional[float] = None
    validation_error_pct: Optional[float] = None

class AggregateCreate(AggregateBase):
    pass

class Aggregate(AggregateBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Alert schemas
class AlertBase(BaseModel):
    site_id: Optional[int] = None
    tank_id: Optional[int] = None
    alert_type: str
    severity: str = "medium"
    title: str
    description: Optional[str] = None
    trigger_value: Optional[float] = None
    threshold_value: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True

class AlertCreate(AlertBase):
    pass

class Alert(AlertBase):
    id: int
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Response schemas
class SiteWithTanks(Site):
    tanks: List[Tank] = []

class TankWithMeasurements(Tank):
    measurements: List[Measurement] = []

class SiteAnalysis(BaseModel):
    site: Site
    latest_aggregate: Optional[Aggregate] = None
    tank_count: int
    active_tank_count: int
    latest_measurement_time: Optional[datetime] = None
    trend_7d: Optional[str] = None
    volume_change_7d_pct: Optional[float] = None

class GlobalSummary(BaseModel):
    total_sites: int
    total_tanks: int
    active_sites: int
    latest_global_volume_bbl: Optional[float] = None
    global_trend_7d: Optional[str] = None
    last_updated: datetime
    regional_breakdown: Dict[str, Any] = {}

# Processing schemas
class ProcessingRequest(BaseModel):
    site_id: Optional[int] = None
    scene_id: Optional[int] = None
    force_reprocess: bool = False
    analysis_methods: List[AnalysisMethod] = [AnalysisMethod.SHADOW_OPTICAL]

class ProcessingStatus(BaseModel):
    status: str  # queued, processing, completed, failed
    progress: float = 0.0
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
