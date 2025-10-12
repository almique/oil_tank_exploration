from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import models
import schemas
from sqlalchemy import func

# Site CRUD operations
def get_sites(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = None,
    is_active: bool = True
) -> List[models.Site]:
    query = db.query(models.Site)
    
    if country:
        query = query.filter(models.Site.country == country)
    if is_active is not None:
        query = query.filter(models.Site.is_active == is_active)
    
    return query.offset(skip).limit(limit).all()

def get_site(db: Session, site_id: int) -> Optional[models.Site]:
    return db.query(models.Site).filter(models.Site.id == site_id).first()

def create_site(db: Session, site: schemas.SiteCreate) -> models.Site:
    # Create bounding box geometry (simple 0.1 degree box around center)
    bbox_wkt = f"POLYGON(({site.center_lon - 0.05} {site.center_lat - 0.05}, {site.center_lon + 0.05} {site.center_lat - 0.05}, {site.center_lon + 0.05} {site.center_lat + 0.05}, {site.center_lon - 0.05} {site.center_lat + 0.05}, {site.center_lon - 0.05} {site.center_lat - 0.05}))"
    
    db_site = models.Site(
        **site.dict(),
        bbox_geom=func.ST_GeomFromText(bbox_wkt, 4326)
    )
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return db_site

def update_site(db: Session, site_id: int, site_update: schemas.SiteUpdate) -> Optional[models.Site]:
    db_site = get_site(db, site_id)
    if not db_site:
        return None
    
    update_data = site_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_site, field, value)
    
    # Update bounding box if center coordinates changed
    if 'center_lat' in update_data or 'center_lon' in update_data:
        bbox_wkt = f"POLYGON(({db_site.center_lon - 0.05} {db_site.center_lat - 0.05}, {db_site.center_lon + 0.05} {db_site.center_lat - 0.05}, {db_site.center_lon + 0.05} {db_site.center_lat + 0.05}, {db_site.center_lon - 0.05} {db_site.center_lat + 0.05}, {db_site.center_lon - 0.05} {db_site.center_lat - 0.05}))"
        db_site.bbox_geom = func.ST_GeomFromText(bbox_wkt, 4326)
    
    db.commit()
    db.refresh(db_site)
    return db_site

def delete_site(db: Session, site_id: int) -> bool:
    db_site = get_site(db, site_id)
    if not db_site:
        return False
    
    db.delete(db_site)
    db.commit()
    return True

# Tank CRUD operations
def get_tanks(
    db: Session,
    site_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    is_active: bool = True
) -> List[models.Tank]:
    query = db.query(models.Tank)
    
    if site_id:
        query = query.filter(models.Tank.site_id == site_id)
    if is_active is not None:
        query = query.filter(models.Tank.is_active == is_active)
    
    return query.offset(skip).limit(limit).all()

def get_tank(db: Session, tank_id: int) -> Optional[models.Tank]:
    return db.query(models.Tank).filter(models.Tank.id == tank_id).first()

def create_tank(db: Session, tank: schemas.TankCreate) -> models.Tank:
    tank_data = tank.dict()
    lat = tank_data.pop('lat')
    lon = tank_data.pop('lon')
    
    db_tank = models.Tank(
        **tank_data,
        geom=func.ST_Point(lon, lat, 4326)
    )
    db.add(db_tank)
    db.commit()
    db.refresh(db_tank)
    return db_tank

def update_tank(db: Session, tank_id: int, tank_update: schemas.TankUpdate) -> Optional[models.Tank]:
    db_tank = get_tank(db, tank_id)
    if not db_tank:
        return None
    
    update_data = tank_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_tank, field, value)
    
    db.commit()
    db.refresh(db_tank)
    return db_tank

# Scene CRUD operations
def get_scenes(
    db: Session,
    site_id: Optional[int] = None,
    satellite: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.Scene]:
    query = db.query(models.Scene).order_by(desc(models.Scene.acquisition_time))
    
    if site_id:
        query = query.filter(models.Scene.site_id == site_id)
    if satellite:
        query = query.filter(models.Scene.satellite == satellite)
    
    return query.offset(skip).limit(limit).all()

def get_scene(db: Session, scene_id: int) -> Optional[models.Scene]:
    return db.query(models.Scene).filter(models.Scene.id == scene_id).first()

def create_scene(db: Session, scene: schemas.SceneCreate) -> models.Scene:
    db_scene = models.Scene(**scene.dict())
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    return db_scene

# Measurement CRUD operations
def get_measurements(
    db: Session,
    tank_id: Optional[int] = None,
    scene_id: Optional[int] = None,
    method: Optional[schemas.AnalysisMethod] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.Measurement]:
    query = db.query(models.Measurement).order_by(desc(models.Measurement.created_at))
    
    if tank_id:
        query = query.filter(models.Measurement.tank_id == tank_id)
    if scene_id:
        query = query.filter(models.Measurement.scene_id == scene_id)
    if method:
        query = query.filter(models.Measurement.method == method.value)
    
    return query.offset(skip).limit(limit).all()

def create_measurement(db: Session, measurement: schemas.MeasurementCreate) -> models.Measurement:
    db_measurement = models.Measurement(**measurement.dict())
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
    return db_measurement

# Aggregate CRUD operations
def get_aggregates(
    db: Session,
    site_id: Optional[int] = None,
    period: str = "daily",
    skip: int = 0,
    limit: int = 100
) -> List[models.Aggregate]:
    query = db.query(models.Aggregate).order_by(desc(models.Aggregate.date))
    
    if site_id:
        query = query.filter(models.Aggregate.site_id == site_id)
    
    query = query.filter(models.Aggregate.aggregation_period == period)
    
    return query.offset(skip).limit(limit).all()

def create_aggregate(db: Session, aggregate: schemas.AggregateCreate) -> models.Aggregate:
    db_aggregate = models.Aggregate(**aggregate.dict())
    db.add(db_aggregate)
    db.commit()
    db.refresh(db_aggregate)
    return db_aggregate

# Alert CRUD operations
def get_alerts(
    db: Session,
    site_id: Optional[int] = None,
    is_active: bool = True,
    skip: int = 0,
    limit: int = 100
) -> List[models.Alert]:
    query = db.query(models.Alert).order_by(desc(models.Alert.created_at))
    
    if site_id:
        query = query.filter(models.Alert.site_id == site_id)
    if is_active is not None:
        query = query.filter(models.Alert.is_active == is_active)
    
    return query.offset(skip).limit(limit).all()

def create_alert(db: Session, alert: schemas.AlertCreate) -> models.Alert:
    db_alert = models.Alert(**alert.dict())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert

def acknowledge_alert(db: Session, alert_id: int) -> bool:
    db_alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not db_alert:
        return False
    
    db_alert.acknowledged_at = datetime.utcnow()
    db.commit()
    return True

# Analysis functions
def get_site_analysis(db: Session, site_id: int) -> Optional[schemas.SiteAnalysis]:
    site = get_site(db, site_id)
    if not site:
        return None
    
    # Get latest aggregate
    latest_aggregate = db.query(models.Aggregate)\
        .filter(models.Aggregate.site_id == site_id)\
        .order_by(desc(models.Aggregate.date))\
        .first()
    
    # Count tanks
    tank_count = db.query(models.Tank)\
        .filter(models.Tank.site_id == site_id)\
        .count()
    
    active_tank_count = db.query(models.Tank)\
        .filter(and_(models.Tank.site_id == site_id, models.Tank.is_active == True))\
        .count()
    
    # Get latest measurement time
    latest_measurement = db.query(models.Measurement)\
        .join(models.Tank)\
        .filter(models.Tank.site_id == site_id)\
        .order_by(desc(models.Measurement.created_at))\
        .first()
    
    latest_measurement_time = latest_measurement.created_at if latest_measurement else None
    
    # Calculate 7-day trend
    week_ago = datetime.utcnow() - timedelta(days=7)
    old_aggregate = db.query(models.Aggregate)\
        .filter(and_(
            models.Aggregate.site_id == site_id,
            models.Aggregate.date >= week_ago
        ))\
        .order_by(models.Aggregate.date)\
        .first()
    
    trend_7d = None
    volume_change_7d_pct = None
    
    if latest_aggregate and old_aggregate and old_aggregate.total_volume_bbl:
        volume_change = latest_aggregate.total_volume_bbl - old_aggregate.total_volume_bbl
        volume_change_7d_pct = (volume_change / old_aggregate.total_volume_bbl) * 100
        
        if volume_change_7d_pct > 5:
            trend_7d = "increasing"
        elif volume_change_7d_pct < -5:
            trend_7d = "decreasing"
        else:
            trend_7d = "stable"
    
    return schemas.SiteAnalysis(
        site=site,
        latest_aggregate=latest_aggregate,
        tank_count=tank_count,
        active_tank_count=active_tank_count,
        latest_measurement_time=latest_measurement_time,
        trend_7d=trend_7d,
        volume_change_7d_pct=volume_change_7d_pct
    )

def get_global_summary(db: Session) -> schemas.GlobalSummary:
    # Count sites and tanks
    total_sites = db.query(models.Site).count()
    active_sites = db.query(models.Site).filter(models.Site.is_active == True).count()
    total_tanks = db.query(models.Tank).count()
    
    # Get latest global volume
    latest_date = db.query(func.max(models.Aggregate.date)).scalar()
    latest_global_volume = None
    
    if latest_date:
        daily_volumes = db.query(func.sum(models.Aggregate.total_volume_bbl))\
            .filter(models.Aggregate.date == latest_date)\
            .scalar()
        latest_global_volume = daily_volumes
    
    # Calculate global trend
    global_trend_7d = None
    if latest_date:
        week_ago = latest_date - timedelta(days=7)
        old_volumes = db.query(func.sum(models.Aggregate.total_volume_bbl))\
            .filter(models.Aggregate.date >= week_ago)\
            .filter(models.Aggregate.date < latest_date)\
            .scalar()
        
        if latest_global_volume and old_volumes:
            change_pct = ((latest_global_volume - old_volumes) / old_volumes) * 100
            if change_pct > 2:
                global_trend_7d = "increasing"
            elif change_pct < -2:
                global_trend_7d = "decreasing"
            else:
                global_trend_7d = "stable"
    
    # Regional breakdown
    regional_breakdown = {}
    regions = db.query(models.Site.country, func.count(models.Site.id))\
        .group_by(models.Site.country)\
        .all()
    
    for country, count in regions:
        regional_breakdown[country] = {"sites": count}
    
    return schemas.GlobalSummary(
        total_sites=total_sites,
        total_tanks=total_tanks,
        active_sites=active_sites,
        latest_global_volume_bbl=latest_global_volume,
        global_trend_7d=global_trend_7d,
        last_updated=datetime.utcnow(),
        regional_breakdown=regional_breakdown
    )
