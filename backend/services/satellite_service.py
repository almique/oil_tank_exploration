import earthaccess
import requests
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
from pystac_client import Client
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os
import logging
from dataclasses import dataclass
import json
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

@dataclass
class SatelliteScene:
    scene_id: str
    satellite: str
    sensor: str
    acquisition_time: datetime
    cloud_coverage: Optional[float]
    sun_elevation: Optional[float]
    sun_azimuth: Optional[float]
    download_url: str
    bbox: Tuple[float, float, float, float]  # west, south, east, north
    metadata: Dict

class NASAEarthdataService:
    """Service for accessing NASA Earthdata (Landsat, MODIS, VIIRS)"""
    
    def __init__(self):
        self.auth = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with NASA Earthdata"""
        try:
            login_kwargs = {}
            if settings.nasa_username and settings.nasa_password:
                login_kwargs["strategy"] = "netrc"
                os.environ["EARTHDATA_USERNAME"] = settings.nasa_username
                os.environ["EARTHDATA_PASSWORD"] = settings.nasa_password
                logger.info("Using provided NASA Earthdata credentials")
            else:
                logger.warning("NASA credentials not provided, relying on stored credentials or anonymous access")
            self.auth = earthaccess.login(**login_kwargs)
            if self.auth:
                logger.info("Successfully authenticated with NASA Earthdata")
            else:
                logger.warning("NASA Earthdata authentication returned no session")
        except Exception as e:
            logger.error(f"Failed to authenticate with NASA Earthdata: {e}")
    
    def search_landsat_scenes(self, 
                            bbox: Tuple[float, float, float, float],
                            start_date: datetime,
                            end_date: datetime,
                            max_cloud_cover: float = 30.0) -> List[SatelliteScene]:
        """
        Search for Landsat scenes
        
        Args:
            bbox: Bounding box (west, south, east, north)
            start_date: Start date for search
            end_date: End date for search
            max_cloud_cover: Maximum cloud coverage percentage
            
        Returns:
            List of SatelliteScene objects
        """
        
        try:
            # Search for Landsat Collection 2 Level 2 data
            results = earthaccess.search_data(
                short_name='HLSL30',  # Harmonized Landsat Sentinel-2 (HLS) Landsat 30m
                bounding_box=bbox,
                temporal=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')),
                cloud_cover=(0, max_cloud_cover)
            )
            
            scenes = []
            for result in results:
                scene = self._parse_landsat_result(result)
                if scene:
                    scenes.append(scene)
            
            logger.info(f"Found {len(scenes)} Landsat scenes")
            return scenes
            
        except Exception as e:
            logger.error(f"Error searching Landsat scenes: {e}")
            return []
    
    def search_modis_scenes(self,
                          bbox: Tuple[float, float, float, float],
                          start_date: datetime,
                          end_date: datetime) -> List[SatelliteScene]:
        """Search for MODIS scenes"""
        
        try:
            results = earthaccess.search_data(
                short_name='MOD09GA',  # MODIS Terra Surface Reflectance Daily
                bounding_box=bbox,
                temporal=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            )
            
            scenes = []
            for result in results:
                scene = self._parse_modis_result(result)
                if scene:
                    scenes.append(scene)
            
            logger.info(f"Found {len(scenes)} MODIS scenes")
            return scenes
            
        except Exception as e:
            logger.error(f"Error searching MODIS scenes: {e}")
            return []
    
    def download_scene(self, scene: SatelliteScene, output_dir: str) -> Optional[str]:
        """Download a satellite scene"""
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # Use earthaccess to download
            files = earthaccess.download(
                [scene.metadata.get('granule_ur', scene.scene_id)],
                local_path=output_dir
            )
            
            if files:
                return files[0]
            return None
            
        except Exception as e:
            logger.error(f"Error downloading scene {scene.scene_id}: {e}")
            return None
    
    def _parse_landsat_result(self, result) -> Optional[SatelliteScene]:
        """Parse Landsat search result"""
        try:
            metadata = result.get('umm', {}).get('TemporalExtent', {})
            
            return SatelliteScene(
                scene_id=result.get('meta', {}).get('concept-id', ''),
                satellite='landsat-8',
                sensor='OLI',
                acquisition_time=datetime.fromisoformat(
                    metadata.get('RangeDateTime', {}).get('BeginningDateTime', '').replace('Z', '+00:00')
                ),
                cloud_coverage=None,  # Extract from metadata if available
                sun_elevation=None,
                sun_azimuth=None,
                download_url=result.get('links', [{}])[0].get('href', ''),
                bbox=(0, 0, 0, 0),  # Extract from spatial extent
                metadata=result
            )
        except Exception as e:
            logger.error(f"Error parsing Landsat result: {e}")
            return None
    
    def _parse_modis_result(self, result) -> Optional[SatelliteScene]:
        """Parse MODIS search result"""
        try:
            return SatelliteScene(
                scene_id=result.get('meta', {}).get('concept-id', ''),
                satellite='terra',
                sensor='MODIS',
                acquisition_time=datetime.now(),  # Extract from metadata
                cloud_coverage=None,
                sun_elevation=None,
                sun_azimuth=None,
                download_url=result.get('links', [{}])[0].get('href', ''),
                bbox=(0, 0, 0, 0),
                metadata=result
            )
        except Exception as e:
            logger.error(f"Error parsing MODIS result: {e}")
            return None

class AwsStacService:
    """Service for accessing Sentinel data published on AWS STAC"""

    SENTINEL_STAC = os.environ.get("AWS_SENTINEL_STAC_ENDPOINT", "https://earth-search.aws.element84.com/v1")
    LANDSAT_STAC = os.environ.get("AWS_LANDSAT_STAC_ENDPOINT", "https://landsatlook.usgs.gov/stac-server")

    def __init__(self):
        self._sentinel_client: Optional[Client] = None
        self._landsat_client: Optional[Client] = None
        self._init_clients()

    def _init_clients(self):
        try:
            self._sentinel_client = Client.open(self.SENTINEL_STAC)
            logger.info("Connected to AWS Sentinel STAC endpoint")
        except Exception as e:
            logger.error(f"Failed to initialize Sentinel STAC client: {e}")
            self._sentinel_client = None

        try:
            self._landsat_client = Client.open(self.LANDSAT_STAC)
            logger.info("Connected to Landsat STAC endpoint")
        except Exception as e:
            logger.error(f"Failed to initialize Landsat STAC client: {e}")
            self._landsat_client = None

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _sanitize_asset_href(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        if href.startswith("s3://"):
            return href.replace("s3://", "https://")
        return href

    def search_sentinel2(self,
                          bbox: Tuple[float, float, float, float],
                          start_date: datetime,
                          end_date: datetime,
                          max_cloud_cover: float = 30.0) -> List[SatelliteScene]:
        if not self._sentinel_client:
            logger.warning("Sentinel STAC client not available")
            return []

        datetime_range = f"{start_date.isoformat()}Z/{end_date.isoformat()}Z"

        try:
            search = self._sentinel_client.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime=datetime_range,
                query={"eo:cloud_cover": {"lt": max_cloud_cover}},
                max_items=20,
            )

            items = list(search.get_items())
            scenes: List[SatelliteScene] = []

            for item in items:
                props = item.properties
                acquisition = self._parse_datetime(props.get("datetime")) or datetime.utcnow()
                cloud = props.get("eo:cloud_cover")
                sun_elev = props.get("view:sun_elevation")
                sun_az = props.get("view:sun_azimuth")
                asset = (
                    item.assets.get("visual")
                    or item.assets.get("B04")
                    or item.assets.get("B08")
                    or next(iter(item.assets.values()), None)
                )
                download_url = self._sanitize_asset_href(asset.href) if asset else None

                scenes.append(
                    SatelliteScene(
                        scene_id=item.id,
                        satellite="sentinel-2",
                        sensor="MSI",
                        acquisition_time=acquisition,
                        cloud_coverage=cloud,
                        sun_elevation=sun_elev,
                        sun_azimuth=sun_az,
                        download_url=download_url or "",
                        bbox=bbox,
                        metadata=item.to_dict(),
                    )
                )

            logger.info(f"STAC: Found {len(scenes)} Sentinel-2 scenes")
            return scenes

        except Exception as e:
            logger.error(f"STAC error searching Sentinel-2 scenes: {e}")
            return []

    def search_sentinel1(self,
                          bbox: Tuple[float, float, float, float],
                          start_date: datetime,
                          end_date: datetime) -> List[SatelliteScene]:
        if not self._sentinel_client:
            logger.warning("Sentinel STAC client not available")
            return []

        datetime_range = f"{start_date.isoformat()}Z/{end_date.isoformat()}Z"

        try:
            search = self._sentinel_client.search(
                collections=["sentinel-1-rtc"],
                bbox=bbox,
                datetime=datetime_range,
                max_items=20,
            )

            items = list(search.get_items())
            scenes: List[SatelliteScene] = []

            for item in items:
                props = item.properties
                acquisition = self._parse_datetime(props.get("datetime")) or datetime.utcnow()
                asset = (
                    item.assets.get("vv")
                    or item.assets.get("vh")
                    or next(iter(item.assets.values()), None)
                )
                download_url = self._sanitize_asset_href(asset.href) if asset else None

                scenes.append(
                    SatelliteScene(
                        scene_id=item.id,
                        satellite="sentinel-1",
                        sensor=props.get("sar:instrument", "SAR"),
                        acquisition_time=acquisition,
                        cloud_coverage=0.0,
                        sun_elevation=None,
                        sun_azimuth=None,
                        download_url=download_url or "",
                        bbox=bbox,
                        metadata=item.to_dict(),
                    )
                )

            logger.info(f"STAC: Found {len(scenes)} Sentinel-1 scenes")
            return scenes

        except Exception as e:
            logger.error(f"STAC error searching Sentinel-1 scenes: {e}")
            return []

    def download_scene(self, scene: SatelliteScene, output_dir: str) -> Optional[str]:
        if not scene.download_url:
            logger.error(f"Scene {scene.scene_id} missing download URL")
            return None

        os.makedirs(output_dir, exist_ok=True)
        target_path = Path(output_dir) / f"{scene.scene_id}.tif"

        url = scene.download_url
        if url.startswith("s3://"):
            url = url.replace("s3://", "https://")

        try:
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with open(target_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            logger.info(f"Downloaded Sentinel scene to {target_path}")
            return str(target_path)

        except Exception as e:
            logger.error(f"Failed to download Sentinel scene {scene.scene_id}: {e}")
            if target_path.exists():
                target_path.unlink()
            return None

class SatelliteDataManager:
    """Main service for managing satellite data acquisition"""
    
    def __init__(self):
        self.nasa_service = NASAEarthdataService()
        self.aws_stac_service = AwsStacService()
        self.data_dir = Path(settings.satellite_data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def search_latest_scenes(self,
                           bbox: Tuple[float, float, float, float],
                           days_back: int = 7,
                           max_cloud_cover: float = 30.0) -> List[SatelliteScene]:
        """
        Search for latest satellite scenes from all sources
        
        Args:
            bbox: Bounding box (west, south, east, north)
            days_back: Number of days to look back
            max_cloud_cover: Maximum cloud coverage for optical imagery
            
        Returns:
            List of available scenes from all satellites
        """
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        all_scenes = []
        
        # Search Sentinel-2 (optical)
        s2_scenes = self.aws_stac_service.search_sentinel2(
            bbox, start_date, end_date, max_cloud_cover
        )
        all_scenes.extend(s2_scenes)
        
        # Search Sentinel-1 (SAR)
        s1_scenes = self.aws_stac_service.search_sentinel1(
            bbox, start_date, end_date
        )
        all_scenes.extend(s1_scenes)
        
        # Search Landsat
        landsat_scenes = self.nasa_service.search_landsat_scenes(
            bbox, start_date, end_date, max_cloud_cover
        )
        all_scenes.extend(landsat_scenes)
        
        # Sort by acquisition time (newest first)
        all_scenes.sort(key=lambda x: x.acquisition_time, reverse=True)
        
        logger.info(f"Found {len(all_scenes)} total scenes")
        return all_scenes
    
    def get_best_recent_scene(self,
                            bbox: Tuple[float, float, float, float],
                            prefer_optical: bool = True,
                            max_cloud_cover: float = 20.0) -> Optional[SatelliteScene]:
        """
        Get the best recent scene for analysis
        
        Args:
            bbox: Bounding box
            prefer_optical: Whether to prefer optical over SAR
            max_cloud_cover: Maximum cloud coverage for optical
            
        Returns:
            Best available scene or None
        """
        
        scenes = self.search_latest_scenes(bbox, days_back=14, max_cloud_cover=max_cloud_cover)
        
        if not scenes:
            return None
        
        if prefer_optical:
            # Look for good optical scenes first
            optical_scenes = [s for s in scenes if s.satellite in ['sentinel-2', 'landsat-8', 'landsat-9']]
            good_optical = [s for s in optical_scenes if s.cloud_coverage and s.cloud_coverage < max_cloud_cover]
            
            if good_optical:
                return good_optical[0]  # Most recent good optical scene
        
        # Return most recent scene (could be SAR)
        return scenes[0]
    
    def download_and_process_scene(self, scene: SatelliteScene) -> Optional[str]:
        """
        Download and prepare a scene for processing
        
        Args:
            scene: Scene to download
            
        Returns:
            Path to downloaded/processed data or None
        """
        
        scene_dir = self.data_dir / scene.satellite / scene.scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if already downloaded
        if (scene_dir / "processed").exists():
            logger.info(f"Scene {scene.scene_id} already processed")
            existing_files = list(scene_dir.glob("*.tif")) + list(scene_dir.glob("*.tiff"))
            if existing_files:
                return str(existing_files[0])
            # Fallback to any file in directory
            other_files = list(scene_dir.glob("*"))
            if other_files:
                return str(other_files[0])
            return str(scene_dir)
        
        # Download scene
        if scene.satellite.startswith('sentinel'):
            downloaded_path = self.aws_stac_service.download_scene(scene, str(scene_dir))
        else:
            downloaded_path = self.nasa_service.download_scene(scene, str(scene_dir))
        
        if downloaded_path:
            # Mark as processed
            (scene_dir / "processed").touch()
            logger.info(f"Successfully downloaded scene {scene.scene_id}")
            return downloaded_path

        return None

    def get_scene_for_site(
        self,
        site_lat: float,
        site_lon: float,
        buffer_km: float = 5.0
    ) -> Optional[SatelliteScene]:
        """Get the best available scene for a site
        
        Args:
            site_lat, site_lon: Site coordinates
            buffer_km: Buffer distance in kilometers (default: 5.0)
            
        Returns:
            Best available scene or None
        """
        
        # Convert buffer to degrees (rough approximation)
        buffer_deg = buffer_km / 111.0
        
        bbox = (
            site_lon - buffer_deg,  # west
            site_lat - buffer_deg,  # south
            site_lon + buffer_deg,  # east
            site_lat + buffer_deg   # north
        )
        
        return self.get_best_recent_scene(bbox)
