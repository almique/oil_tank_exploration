from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/oil_tank_monitor"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # NASA Earthdata credentials
    nasa_username: Optional[str] = None
    nasa_password: Optional[str] = None
    
    # ESA Copernicus credentials
    copernicus_username: Optional[str] = None
    copernicus_password: Optional[str] = None
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # External APIs
    ais_api_key: Optional[str] = None
    weather_api_key: Optional[str] = None
    
    # Application
    debug: bool = True
    log_level: str = "INFO"
    max_workers: int = 4
    
    # Data directories
    data_dir: str = "./data"
    satellite_data_dir: str = "./data/satellite"
    processed_data_dir: str = "./data/processed"

    # Imagery search tuning
    imagery_search_buffer_deg: float = 0.15
    imagery_search_days: int = 21
    imagery_crop_buffer_km: float = 2.0
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
