from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn

from database import get_db, engine
from models import Base
import schemas
import crud
from config import settings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Oil Tank Monitor API",
    description="API for monitoring global oil storage tank levels using satellite imagery",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Sites endpoints
@app.get("/api/sites", response_model=List[schemas.Site])
async def get_sites(
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """Get all monitored sites"""
    return crud.get_sites(db, skip=skip, limit=limit, country=country, is_active=is_active)

@app.get("/api/sites/{site_id}", response_model=schemas.SiteWithTanks)
async def get_site(site_id: int, db: Session = Depends(get_db)):
    """Get a specific site with its tanks"""
    site = crud.get_site(db, site_id=site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site

@app.post("/api/sites", response_model=schemas.Site)
async def create_site(site: schemas.SiteCreate, db: Session = Depends(get_db)):
    """Create a new monitoring site"""
    return crud.create_site(db, site=site)

@app.put("/api/sites/{site_id}", response_model=schemas.Site)
async def update_site(
    site_id: int,
    site_update: schemas.SiteUpdate,
    db: Session = Depends(get_db)
):
    """Update a site"""
    site = crud.update_site(db, site_id=site_id, site_update=site_update)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site

@app.delete("/api/sites/{site_id}")
async def delete_site(site_id: int, db: Session = Depends(get_db)):
    """Delete a site"""
    success = crud.delete_site(db, site_id=site_id)
    if not success:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"message": "Site deleted successfully"}

# Tanks endpoints
@app.get("/api/tanks", response_model=List[schemas.Tank])
async def get_tanks(
    site_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """Get tanks, optionally filtered by site"""
    return crud.get_tanks(db, site_id=site_id, skip=skip, limit=limit, is_active=is_active)

@app.get("/api/tanks/{tank_id}", response_model=schemas.TankWithMeasurements)
async def get_tank(tank_id: int, db: Session = Depends(get_db)):
    """Get a specific tank with its measurements"""
    tank = crud.get_tank(db, tank_id=tank_id)
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    return tank

@app.post("/api/tanks", response_model=schemas.Tank)
async def create_tank(tank: schemas.TankCreate, db: Session = Depends(get_db)):
    """Create a new tank"""
    return crud.create_tank(db, tank=tank)

@app.put("/api/tanks/{tank_id}", response_model=schemas.Tank)
async def update_tank(
    tank_id: int,
    tank_update: schemas.TankUpdate,
    db: Session = Depends(get_db)
):
    """Update a tank"""
    tank = crud.update_tank(db, tank_id=tank_id, tank_update=tank_update)
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    return tank

# Scenes endpoints
@app.get("/api/scenes", response_model=List[schemas.Scene])
async def get_scenes(
    site_id: Optional[int] = None,
    satellite: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get satellite scenes"""
    return crud.get_scenes(db, site_id=site_id, satellite=satellite, skip=skip, limit=limit)

@app.get("/api/scenes/{scene_id}", response_model=schemas.Scene)
async def get_scene(scene_id: int, db: Session = Depends(get_db)):
    """Get a specific scene"""
    scene = crud.get_scene(db, scene_id=scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene

@app.post("/api/scenes", response_model=schemas.Scene)
async def create_scene(scene: schemas.SceneCreate, db: Session = Depends(get_db)):
    """Create a new scene record"""
    return crud.create_scene(db, scene=scene)

# Measurements endpoints
@app.get("/api/measurements", response_model=List[schemas.Measurement])
async def get_measurements(
    tank_id: Optional[int] = None,
    scene_id: Optional[int] = None,
    method: Optional[schemas.AnalysisMethod] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get measurements"""
    return crud.get_measurements(
        db, tank_id=tank_id, scene_id=scene_id, method=method, skip=skip, limit=limit
    )

@app.post("/api/measurements", response_model=schemas.Measurement)
async def create_measurement(measurement: schemas.MeasurementCreate, db: Session = Depends(get_db)):
    """Create a new measurement"""
    return crud.create_measurement(db, measurement=measurement)

# Aggregates endpoints
@app.get("/api/aggregates", response_model=List[schemas.Aggregate])
async def get_aggregates(
    site_id: Optional[int] = None,
    period: str = "daily",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get aggregated data"""
    return crud.get_aggregates(db, site_id=site_id, period=period, skip=skip, limit=limit)

@app.get("/api/sites/{site_id}/analysis", response_model=schemas.SiteAnalysis)
async def get_site_analysis(site_id: int, db: Session = Depends(get_db)):
    """Get comprehensive analysis for a site"""
    analysis = crud.get_site_analysis(db, site_id=site_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Site not found")
    return analysis

@app.get("/api/global-summary", response_model=schemas.GlobalSummary)
async def get_global_summary(db: Session = Depends(get_db)):
    """Get global summary statistics"""
    return crud.get_global_summary(db)

# Alerts endpoints
@app.get("/api/alerts", response_model=List[schemas.Alert])
async def get_alerts(
    site_id: Optional[int] = None,
    is_active: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get alerts"""
    return crud.get_alerts(db, site_id=site_id, is_active=is_active, skip=skip, limit=limit)

@app.post("/api/alerts", response_model=schemas.Alert)
async def create_alert(alert: schemas.AlertCreate, db: Session = Depends(get_db)):
    """Create a new alert"""
    return crud.create_alert(db, alert=alert)

@app.put("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Acknowledge an alert"""
    success = crud.acknowledge_alert(db, alert_id=alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert acknowledged"}

# Processing endpoints
@app.post("/api/process/satellite-data")
async def process_satellite_data(
    request: schemas.ProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger satellite data processing"""
    from tasks import process_satellite_imagery
    
    # Add processing task to background queue
    background_tasks.add_task(
        process_satellite_imagery,
        site_id=request.site_id,
        scene_id=request.scene_id,
        force_reprocess=request.force_reprocess,
        analysis_methods=request.analysis_methods
    )
    
    return {"message": "Processing started", "status": "queued"}

@app.post("/api/process/fetch-imagery")
async def fetch_satellite_imagery(
    site_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Fetch latest satellite imagery for sites"""
    from tasks import fetch_latest_imagery
    
    background_tasks.add_task(fetch_latest_imagery, site_id=site_id)
    
    return {"message": "Imagery fetch started", "status": "queued"}

@app.post("/api/process/detect-tanks")
async def detect_tanks_from_osm(
    site_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Detect tanks from OpenStreetMap data"""
    from tasks import detect_tanks_osm
    
    site = crud.get_site(db, site_id=site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    background_tasks.add_task(detect_tanks_osm, site_id=site_id)
    
    return {"message": "Tank detection started", "status": "queued"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
