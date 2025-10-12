from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from config import settings
from database import SessionLocal
import crud
import schemas
from services.satellite_service import SatelliteDataManager
from services.osm_service import TankDetectionService
from services.vision_service import VisionService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery = Celery(
    "oil_tank_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks schedule
celery.conf.beat_schedule = {
    'fetch-daily-imagery': {
        'task': 'tasks.fetch_daily_imagery_all_sites',
        'schedule': crontab(hour=6, minute=0),  # 6 AM UTC daily
    },
    'process-pending-scenes': {
        'task': 'tasks.process_pending_scenes',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'generate-daily-aggregates': {
        'task': 'tasks.generate_daily_aggregates',
        'schedule': crontab(hour=8, minute=0),  # 8 AM UTC daily
    },
    'cleanup-old-data': {
        'task': 'tasks.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),  # Weekly on Monday 2 AM
    }
}

def get_db():
    """Get database session for tasks"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let task handle it

@celery.task(bind=True)
def fetch_latest_imagery(self, site_id: Optional[int] = None):
    """
    Fetch latest satellite imagery for sites
    
    Args:
        site_id: Specific site ID, or None for all sites
    """
    
    db = get_db()
    try:
        satellite_manager = SatelliteDataManager()
        
        # Get sites to process
        if site_id:
            sites = [crud.get_site(db, site_id)]
            if not sites[0]:
                logger.error(f"Site {site_id} not found")
                return {"error": f"Site {site_id} not found"}
        else:
            sites = crud.get_sites(db, is_active=True)
        
        results = []
        
        for site in sites:
            if not site:
                continue
                
            logger.info(f"Fetching imagery for site {site.name}")
            
            # Expand bounding box and lookback window for sparse imagery regions
            buffer = getattr(settings, "imagery_search_buffer_deg", 0.1)
            days_back = getattr(settings, "imagery_search_days", 14)

            bbox = (
                site.center_lon - buffer,  # west
                site.center_lat - buffer,  # south
                site.center_lon + buffer,  # east
                site.center_lat + buffer   # north
            )
            
            # Search for recent scenes
            scenes = satellite_manager.search_latest_scenes(bbox, days_back=days_back)
            
            scenes_added = 0
            for scene in scenes[:5]:  # Limit to 5 most recent
                # Check if scene already exists
                existing = db.query(crud.models.Scene).filter(
                    crud.models.Scene.scene_id == scene.scene_id
                ).first()
                
                if not existing:
                    # Create scene record
                    scene_data = schemas.SceneCreate(
                        site_id=site.id,
                        satellite=scene.satellite,
                        sensor=scene.sensor,
                        scene_id=scene.scene_id,
                        acquisition_time=scene.acquisition_time,
                        sun_elevation=scene.sun_elevation,
                        sun_azimuth=scene.sun_azimuth,
                        cloud_coverage=scene.cloud_coverage,
                        raw_data_url=scene.download_url,
                        quality_score=1.0 - (scene.cloud_coverage or 0) / 100.0,
                        metadata=scene.metadata
                    )
                    
                    crud.create_scene(db, scene_data)
                    scenes_added += 1
            
            results.append({
                "site_id": site.id,
                "site_name": site.name,
                "scenes_found": len(scenes),
                "scenes_added": scenes_added
            })
        
        db.commit()
        logger.info(f"Imagery fetch completed: {results}")
        return {"results": results}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error fetching imagery: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task(bind=True)
def process_satellite_imagery(self, 
                            site_id: Optional[int] = None,
                            scene_id: Optional[int] = None,
                            force_reprocess: bool = False,
                            analysis_methods: List[str] = None):
    """
    Process satellite imagery to detect tanks and analyze shadows
    
    Args:
        site_id: Process scenes for specific site
        scene_id: Process specific scene
        force_reprocess: Reprocess even if already processed
        analysis_methods: List of analysis methods to use
    """
    
    if analysis_methods is None:
        analysis_methods = ["shadow_optical"]
    
    db = get_db()
    try:
        vision_service = VisionService()
        satellite_manager = SatelliteDataManager()
        
        # Get scenes to process
        if scene_id:
            scenes = [crud.get_scene(db, scene_id)]
        elif site_id:
            scenes = crud.get_scenes(db, site_id=site_id, limit=10)
        else:
            # Get unprocessed scenes
            scenes = db.query(crud.models.Scene).filter(
                crud.models.Scene.is_processed == False
            ).limit(20).all()
        
        results = []
        
        for scene in scenes:
            if not scene:
                continue
            
            if scene.is_processed and not force_reprocess:
                continue
            
            logger.info(f"Processing scene {scene.scene_id}")

            site = scene.site or crud.get_site(db, scene.site_id)
            site_lat = site.center_lat if site else None
            site_lon = site.center_lon if site else None
            
            try:
                # Download scene if needed
                scene_path = satellite_manager.download_and_process_scene(
                    satellite_manager._scene_from_db(scene)
                )
                
                if not scene_path:
                    logger.error(f"Failed to download scene {scene.scene_id}")
                    continue
                
                # Process with computer vision
                processing_results = vision_service.process_satellite_image(
                    scene_path,
                    sun_elevation=scene.sun_elevation,
                    sun_azimuth=scene.sun_azimuth,
                    pixel_size_m=10.0,  # Sentinel-2 resolution baseline
                    site_lat=site_lat,
                    site_lon=site_lon,
                    buffer_km=settings.imagery_crop_buffer_km
                )
                
                if "error" in processing_results:
                    scene.processing_error = processing_results["error"]
                    scene.is_processed = False
                else:
                    # Save tank detections and measurements
                    tanks_created = 0
                    measurements_created = 0
                    
                    # Get existing tanks for this site
                    existing_tanks = crud.get_tanks(db, site_id=scene.site_id)
                    
                    for tank_data in processing_results.get("tanks", []):
                        # Check if tank already exists nearby
                        existing_tank = None
                        for existing in existing_tanks:
                            # Simple distance check (should use proper geographic distance)
                            if (abs(existing.lat - tank_data["lat"]) < 0.001 and 
                                abs(existing.lon - tank_data["lon"]) < 0.001):
                                existing_tank = existing
                                break
                        
                        if not existing_tank:
                            # Create new tank
                            tank_create = schemas.TankCreate(
                                site_id=scene.site_id,
                                lat=tank_data["lat"],
                                lon=tank_data["lon"],
                                estimated_diameter_m=tank_data["diameter_m"],
                                confidence=tank_data["confidence"],
                                source="satellite_detection"
                            )
                            existing_tank = crud.create_tank(db, tank_create)
                            tanks_created += 1
                        
                        # Create measurements from shadow analysis
                        for shadow_data in processing_results.get("shadows", []):
                            if (shadow_data["tank_center_x"] == tank_data["center_x"] and
                                shadow_data["tank_center_y"] == tank_data["center_y"]):
                                
                                measurement = schemas.MeasurementCreate(
                                    tank_id=existing_tank.id,
                                    scene_id=scene.id,
                                    method="shadow_optical",
                                    roof_height_m=shadow_data["roof_height_m"],
                                    fill_fraction=shadow_data["fill_fraction"],
                                    confidence=shadow_data["confidence"],
                                    shadow_length_px=shadow_data["shadow_length_px"],
                                    shadow_angle_deg=shadow_data["shadow_angle_deg"],
                                    algorithm_version="1.0",
                                    parameters={
                                        "sun_elevation": shadow_data["sun_elevation"],
                                        "sun_azimuth": shadow_data["sun_azimuth"]
                                    }
                                )
                                
                                crud.create_measurement(db, measurement)
                                measurements_created += 1
                    
                    scene.is_processed = True
                    scene.processed_time = datetime.utcnow()
                    
                    results.append({
                        "scene_id": scene.id,
                        "scene_name": scene.scene_id,
                        "tanks_detected": processing_results["tanks_detected"],
                        "tanks_created": tanks_created,
                        "measurements_created": measurements_created
                    })
                
            except Exception as e:
                logger.error(f"Error processing scene {scene.scene_id}: {e}")
                scene.processing_error = str(e)
                scene.is_processed = False
        
        db.commit()
        logger.info(f"Processing completed: {results}")
        return {"results": results}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in processing task: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task(bind=True)
def detect_tanks_osm(self, site_id: int):
    """
    Detect tanks for a site using OpenStreetMap data
    
    Args:
        site_id: Site ID to detect tanks for
    """
    
    db = get_db()
    try:
        detection_service = TankDetectionService()
        
        site = crud.get_site(db, site_id)
        if not site:
            return {"error": f"Site {site_id} not found"}
        
        logger.info(f"Detecting tanks from OSM for site {site.name}")
        
        # Detect tanks using OSM
        tank_locations = detection_service.detect_tanks_for_site(
            site.name,
            site.center_lat,
            site.center_lon,
            radius_km=5.0
        )
        
        tanks_created = 0
        
        for tank_location in tank_locations:
            # Check if tank already exists
            existing_tanks = crud.get_tanks(db, site_id=site_id)
            
            tank_exists = any(
                abs(existing.lat - tank_location.lat) < 0.0001 and
                abs(existing.lon - tank_location.lon) < 0.0001
                for existing in existing_tanks
            )
            
            if not tank_exists:
                tank_create = schemas.TankCreate(
                    site_id=site_id,
                    lat=tank_location.lat,
                    lon=tank_location.lon,
                    estimated_diameter_m=tank_location.diameter_m,
                    operator=tank_location.operator,
                    source="osm",
                    confidence=0.8
                )
                
                crud.create_tank(db, tank_create)
                tanks_created += 1
        
        db.commit()
        
        result = {
            "site_id": site_id,
            "site_name": site.name,
            "tanks_found": len(tank_locations),
            "tanks_created": tanks_created
        }
        
        logger.info(f"OSM tank detection completed: {result}")
        return result
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error detecting tanks from OSM: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task(bind=True)
def generate_daily_aggregates(self, date: Optional[str] = None):
    """
    Generate daily aggregate statistics for all sites
    
    Args:
        date: Date to generate aggregates for (YYYY-MM-DD), defaults to yesterday
    """
    
    db = get_db()
    try:
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        else:
            target_date = (datetime.utcnow() - timedelta(days=1)).date()
        
        logger.info(f"Generating daily aggregates for {target_date}")
        
        sites = crud.get_sites(db, is_active=True)
        results = []
        
        for site in sites:
            # Get measurements for the day
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = start_time + timedelta(days=1)
            
            measurements = db.query(crud.models.Measurement).join(
                crud.models.Tank
            ).filter(
                crud.models.Tank.site_id == site.id,
                crud.models.Measurement.created_at >= start_time,
                crud.models.Measurement.created_at < end_time,
                crud.models.Measurement.is_outlier == False
            ).all()
            
            if not measurements:
                continue
            
            # Calculate aggregates
            total_volume = sum(m.volume_bbl for m in measurements if m.volume_bbl)
            avg_fill_fraction = sum(m.fill_fraction for m in measurements if m.fill_fraction) / len(measurements)
            tank_count = len(set(m.tank_id for m in measurements))
            overall_confidence = sum(m.confidence for m in measurements) / len(measurements)
            
            # Get previous day's aggregate for trend calculation
            prev_date = target_date - timedelta(days=1)
            prev_aggregate = db.query(crud.models.Aggregate).filter(
                crud.models.Aggregate.site_id == site.id,
                crud.models.Aggregate.date >= datetime.combine(prev_date, datetime.min.time()),
                crud.models.Aggregate.date < datetime.combine(prev_date, datetime.min.time()) + timedelta(days=1)
            ).first()
            
            volume_change_bbl = None
            volume_change_pct = None
            trend_direction = "stable"
            
            if prev_aggregate and prev_aggregate.total_volume_bbl and total_volume:
                volume_change_bbl = total_volume - prev_aggregate.total_volume_bbl
                volume_change_pct = (volume_change_bbl / prev_aggregate.total_volume_bbl) * 100
                
                if volume_change_pct > 5:
                    trend_direction = "increasing"
                elif volume_change_pct < -5:
                    trend_direction = "decreasing"
            
            # Create or update aggregate
            existing_aggregate = db.query(crud.models.Aggregate).filter(
                crud.models.Aggregate.site_id == site.id,
                crud.models.Aggregate.date >= start_time,
                crud.models.Aggregate.date < end_time
            ).first()
            
            if existing_aggregate:
                # Update existing
                existing_aggregate.total_volume_bbl = total_volume
                existing_aggregate.average_fill_fraction = avg_fill_fraction
                existing_aggregate.tank_count = tank_count
                existing_aggregate.overall_confidence = overall_confidence
                existing_aggregate.measurement_count = len(measurements)
                existing_aggregate.volume_change_bbl = volume_change_bbl
                existing_aggregate.volume_change_pct = volume_change_pct
                existing_aggregate.trend_direction = trend_direction
            else:
                # Create new
                aggregate = schemas.AggregateCreate(
                    site_id=site.id,
                    date=start_time,
                    total_volume_bbl=total_volume,
                    average_fill_fraction=avg_fill_fraction,
                    tank_count=tank_count,
                    overall_confidence=overall_confidence,
                    measurement_count=len(measurements),
                    volume_change_bbl=volume_change_bbl,
                    volume_change_pct=volume_change_pct,
                    trend_direction=trend_direction
                )
                
                crud.create_aggregate(db, aggregate)
            
            results.append({
                "site_id": site.id,
                "site_name": site.name,
                "measurements": len(measurements),
                "total_volume_bbl": total_volume,
                "trend": trend_direction
            })
        
        db.commit()
        logger.info(f"Generated aggregates for {len(results)} sites")
        return {"date": str(target_date), "sites_processed": len(results), "results": results}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error generating aggregates: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery.task(bind=True)
def fetch_daily_imagery_all_sites(self):
    """Fetch daily imagery for all active sites"""
    return fetch_latest_imagery.delay()

@celery.task(bind=True)
def process_pending_scenes(self):
    """Process all pending scenes"""
    return process_satellite_imagery.delay()

@celery.task(bind=True)
def cleanup_old_data(self, days_to_keep: int = 90):
    """
    Clean up old data to save storage space
    
    Args:
        days_to_keep: Number of days of data to keep
    """
    
    db = get_db()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old scenes
        old_scenes = db.query(crud.models.Scene).filter(
            crud.models.Scene.acquisition_time < cutoff_date
        ).count()
        
        db.query(crud.models.Scene).filter(
            crud.models.Scene.acquisition_time < cutoff_date
        ).delete()
        
        # Delete old measurements (keep aggregates)
        old_measurements = db.query(crud.models.Measurement).filter(
            crud.models.Measurement.created_at < cutoff_date
        ).count()
        
        db.query(crud.models.Measurement).filter(
            crud.models.Measurement.created_at < cutoff_date
        ).delete()
        
        db.commit()
        
        result = {
            "cutoff_date": str(cutoff_date),
            "scenes_deleted": old_scenes,
            "measurements_deleted": old_measurements
        }
        
        logger.info(f"Cleanup completed: {result}")
        return result
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during cleanup: {e}")
        return {"error": str(e)}
    finally:
        db.close()

# Helper function to convert DB scene to SatelliteScene
def _scene_from_db(scene) -> 'SatelliteScene':
    """Convert database scene to SatelliteScene object"""
    from services.satellite_service import SatelliteScene
    
    return SatelliteScene(
        scene_id=scene.scene_id,
        satellite=scene.satellite,
        sensor=scene.sensor or "",
        acquisition_time=scene.acquisition_time,
        cloud_coverage=scene.cloud_coverage,
        sun_elevation=scene.sun_elevation,
        sun_azimuth=scene.sun_azimuth,
        download_url=scene.raw_data_url or "",
        bbox=(0, 0, 0, 0),  # Would need to calculate from site
        metadata=scene.metadata or {}
    )

# Add helper method to SatelliteDataManager
SatelliteDataManager._scene_from_db = staticmethod(_scene_from_db)
