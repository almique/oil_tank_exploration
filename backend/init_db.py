#!/usr/bin/env python3
"""
Initialize the database with sample data
"""

import asyncio
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base
import crud
import schemas
from services.osm_service import TankDetectionService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    """Create all database tables"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

def create_sample_sites(db: Session):
    """Create sample oil storage sites"""
    logger.info("Creating sample sites...")
    
    detection_service = TankDetectionService()
    predefined_sites = detection_service.get_predefined_sites()
    
    created_sites = []
    
    for site_data in predefined_sites:
        try:
            # Check if site already exists
            existing_sites = crud.get_sites(db, limit=1000)
            if any(s.name == site_data["name"] for s in existing_sites):
                logger.info(f"Site {site_data['name']} already exists, skipping...")
                continue
            
            site_create = schemas.SiteCreate(**site_data)
            site = crud.create_site(db, site_create)
            created_sites.append(site)
            logger.info(f"Created site: {site.name}")
            
        except Exception as e:
            logger.error(f"Error creating site {site_data['name']}: {e}")
    
    db.commit()
    logger.info(f"Created {len(created_sites)} sample sites")
    return created_sites

def detect_tanks_for_sites(db: Session, sites):
    """Detect tanks for sample sites using OSM data"""
    logger.info("Detecting tanks from OpenStreetMap...")
    
    detection_service = TankDetectionService()
    
    for site in sites:
        try:
            logger.info(f"Detecting tanks for {site.name}...")
            
            tank_locations = detection_service.detect_tanks_for_site(
                site.name,
                site.center_lat,
                site.center_lon,
                radius_km=5.0
            )
            
            tanks_created = 0
            for tank_location in tank_locations:
                try:
                    tank_create = schemas.TankCreate(
                        site_id=site.id,
                        lat=tank_location.lat,
                        lon=tank_location.lon,
                        estimated_diameter_m=tank_location.diameter_m,
                        operator=tank_location.operator,
                        source="osm",
                        confidence=0.8
                    )
                    
                    crud.create_tank(db, tank_create)
                    tanks_created += 1
                    
                except Exception as e:
                    logger.error(f"Error creating tank: {e}")
            
            logger.info(f"Created {tanks_created} tanks for {site.name}")
            
        except Exception as e:
            logger.error(f"Error detecting tanks for {site.name}: {e}")
    
    db.commit()
    logger.info("Tank detection completed")

def create_sample_data():
    """Create sample data for demonstration"""
    logger.info("Initializing database with sample data...")
    
    # Create tables
    create_tables()
    
    # Create sample sites and tanks
    db = SessionLocal()
    try:
        sites = create_sample_sites(db)
        if sites:
            detect_tanks_for_sites(db, sites)
        
        logger.info("Database initialization completed successfully!")
        
        # Print summary
        total_sites = len(crud.get_sites(db))
        total_tanks = len(crud.get_tanks(db))
        
        logger.info(f"Database summary:")
        logger.info(f"  - Sites: {total_sites}")
        logger.info(f"  - Tanks: {total_tanks}")
        
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()
