import overpy
import requests
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class TankLocation:
    lat: float
    lon: float
    diameter_m: Optional[float] = None
    operator: Optional[str] = None
    tank_type: Optional[str] = None
    source: str = "osm"

class OSMService:
    """Service for fetching oil storage tank locations from OpenStreetMap"""
    
    def __init__(self):
        self.api = overpy.Overpass()
        
    def get_tanks_in_bbox(self, 
                         north: float, 
                         south: float, 
                         east: float, 
                         west: float) -> List[TankLocation]:
        """
        Fetch oil storage tanks within a bounding box from OpenStreetMap
        
        Args:
            north, south, east, west: Bounding box coordinates
            
        Returns:
            List of TankLocation objects
        """
        
        query = f"""
        [out:json][timeout:120];
        (
          nwr["man_made"="storage_tank"]({south},{west},{north},{east});
          nwr["man_made"="tank"]["content"~"oil|fuel|petroleum"]({south},{west},{north},{east});
          nwr["industrial"="oil"]({south},{west},{north},{east});
        );
        out center meta;
        """
        
        try:
            result = self.api.query(query)
            tanks = []
            
            # Process nodes
            for node in result.nodes:
                tank = self._extract_tank_info(node, node.lat, node.lon)
                if tank:
                    tanks.append(tank)
            
            # Process ways (get center point)
            for way in result.ways:
                if hasattr(way, 'center_lat') and hasattr(way, 'center_lon'):
                    tank = self._extract_tank_info(way, way.center_lat, way.center_lon)
                    if tank:
                        tanks.append(tank)
            
            # Process relations
            for relation in result.relations:
                if hasattr(relation, 'center_lat') and hasattr(relation, 'center_lon'):
                    tank = self._extract_tank_info(relation, relation.center_lat, relation.center_lon)
                    if tank:
                        tanks.append(tank)
            
            logger.info(f"Found {len(tanks)} tanks in bbox ({south},{west},{north},{east})")
            return tanks
            
        except Exception as e:
            logger.error(f"Error querying OSM: {e}")
            return []
    
    def get_tanks_near_point(self, 
                           lat: float, 
                           lon: float, 
                           radius_km: float = 10.0) -> List[TankLocation]:
        """
        Fetch oil storage tanks near a point
        
        Args:
            lat, lon: Center point coordinates
            radius_km: Search radius in kilometers
            
        Returns:
            List of TankLocation objects
        """
        
        # Convert radius to degrees (rough approximation)
        radius_deg = radius_km / 111.0  # 1 degree ≈ 111 km
        
        north = lat + radius_deg
        south = lat - radius_deg
        east = lon + radius_deg
        west = lon - radius_deg
        
        return self.get_tanks_in_bbox(north, south, east, west)
    
    def get_tanks_for_major_hubs(self) -> Dict[str, List[TankLocation]]:
        """
        Get tanks for major oil storage hubs worldwide
        
        Returns:
            Dictionary mapping hub names to tank locations
        """
        
        major_hubs = {
            "Cushing_OK": (35.98, -96.77, 5.0),  # lat, lon, radius_km
            "Houston_TX": (29.72, -95.23, 15.0),
            "Rotterdam_NL": (51.95, 4.13, 10.0),
            "Fujairah_UAE": (25.12, 56.33, 8.0),
            "Singapore": (1.29, 103.69, 12.0),
            "Zhoushan_China": (29.94, 122.20, 10.0),
            "Ras_Tanura_SA": (26.64, 50.16, 8.0),
            "Corpus_Christi_TX": (27.80, -97.40, 10.0),
            "Galveston_TX": (29.30, -94.80, 8.0),
            "Antwerp_BE": (51.22, 4.40, 8.0)
        }
        
        hub_tanks = {}
        
        for hub_name, (lat, lon, radius) in major_hubs.items():
            logger.info(f"Fetching tanks for {hub_name}")
            tanks = self.get_tanks_near_point(lat, lon, radius)
            hub_tanks[hub_name] = tanks
            
        return hub_tanks
    
    def _extract_tank_info(self, osm_element, lat: float, lon: float) -> Optional[TankLocation]:
        """Extract tank information from OSM element"""
        
        tags = osm_element.tags
        
        # Check if this is likely an oil storage tank
        if not self._is_oil_tank(tags):
            return None
        
        # Extract diameter if available
        diameter_m = None
        if 'diameter' in tags:
            try:
                diameter_m = float(tags['diameter'])
            except ValueError:
                pass
        
        # Extract operator
        operator = tags.get('operator', tags.get('owner'))
        
        # Extract tank type
        tank_type = tags.get('content', tags.get('substance'))
        
        return TankLocation(
            lat=lat,
            lon=lon,
            diameter_m=diameter_m,
            operator=operator,
            tank_type=tank_type,
            source="osm"
        )
    
    def _is_oil_tank(self, tags: Dict[str, str]) -> bool:
        """Determine if OSM element represents an oil storage tank"""
        
        # Check man_made tag
        if tags.get('man_made') == 'storage_tank':
            content = tags.get('content', '').lower()
            substance = tags.get('substance', '').lower()
            
            oil_keywords = ['oil', 'crude', 'petroleum', 'fuel', 'gasoline', 'diesel']
            
            if any(keyword in content for keyword in oil_keywords):
                return True
            if any(keyword in substance for keyword in oil_keywords):
                return True
            
            # If no content specified but it's a storage tank, include it
            if not content and not substance:
                return True
        
        # Check industrial tag
        if tags.get('industrial') == 'oil':
            return True
        
        # Check landuse
        if tags.get('landuse') == 'industrial' and 'oil' in tags.get('name', '').lower():
            return True
        
        return False

class TankDetectionService:
    """Service for detecting tanks using multiple methods"""
    
    def __init__(self):
        self.osm_service = OSMService()
    
    def detect_tanks_for_site(self, 
                            site_name: str,
                            center_lat: float, 
                            center_lon: float,
                            radius_km: float = 5.0) -> List[TankLocation]:
        """
        Detect tanks for a site using OSM data
        
        Args:
            site_name: Name of the site
            center_lat, center_lon: Site center coordinates
            radius_km: Search radius
            
        Returns:
            List of detected tank locations
        """
        
        logger.info(f"Detecting tanks for {site_name} at ({center_lat}, {center_lon})")
        
        # Get tanks from OSM
        osm_tanks = self.osm_service.get_tanks_near_point(center_lat, center_lon, radius_km)
        
        # TODO: Add satellite-based tank detection here
        # satellite_tanks = self._detect_tanks_from_satellite(center_lat, center_lon, radius_km)
        
        # For now, return OSM tanks
        return osm_tanks
    
    def get_predefined_sites(self) -> List[Dict]:
        """Get predefined major oil storage sites"""
        
        sites = [
            {
                "name": "Cushing Oil Hub",
                "country": "USA",
                "region": "Oklahoma",
                "center_lat": 35.98,
                "center_lon": -96.77,
                "timezone": "America/Chicago",
                "description": "Major WTI crude oil storage and trading hub"
            },
            {
                "name": "Houston Ship Channel",
                "country": "USA", 
                "region": "Texas",
                "center_lat": 29.72,
                "center_lon": -95.23,
                "timezone": "America/Chicago",
                "description": "Major Gulf Coast refining and storage complex"
            },
            {
                "name": "Rotterdam Port",
                "country": "Netherlands",
                "region": "South Holland",
                "center_lat": 51.95,
                "center_lon": 4.13,
                "timezone": "Europe/Amsterdam",
                "description": "Europe's largest oil storage and trading hub"
            },
            {
                "name": "Fujairah Oil Terminal",
                "country": "UAE",
                "region": "Fujairah",
                "center_lat": 25.12,
                "center_lon": 56.33,
                "timezone": "Asia/Dubai",
                "description": "Major Middle East oil storage and bunkering hub"
            },
            {
                "name": "Singapore Jurong Island",
                "country": "Singapore",
                "region": "Singapore",
                "center_lat": 1.29,
                "center_lon": 103.69,
                "timezone": "Asia/Singapore",
                "description": "Major Asian oil refining and storage complex"
            },
            {
                "name": "Zhoushan Oil Terminal",
                "country": "China",
                "region": "Zhejiang",
                "center_lat": 29.94,
                "center_lon": 122.20,
                "timezone": "Asia/Shanghai",
                "description": "Major Chinese oil storage and trading hub"
            },
            {
                "name": "Ras Tanura Oil Terminal",
                "country": "Saudi Arabia",
                "region": "Eastern Province",
                "center_lat": 26.7041,
                "center_lon": 50.0606,
                "timezone": "Asia/Riyadh",
                "description": "Largest offshore oil loading facility in the world"
            },
            {
                "name": "Ras Laffan Industrial City",
                "country": "Qatar",
                "region": "Al Khor",
                "center_lat": 25.9092,
                "center_lon": 51.5670,
                "timezone": "Asia/Qatar",
                "description": "Major LNG and condensate export hub"
            },
            {
                "name": "Port of Antwerp",
                "country": "Belgium",
                "region": "Flanders",
                "center_lat": 51.2637,
                "center_lon": 4.4147,
                "timezone": "Europe/Brussels",
                "description": "Key Northwest Europe storage and petrochemical complex"
            },
            {
                "name": "Corpus Christi Oil Terminals",
                "country": "USA",
                "region": "Texas",
                "center_lat": 27.8000,
                "center_lon": -97.4000,
                "timezone": "America/Chicago",
                "description": "Gulf Coast export hub for crude and refined products"
            },
            {
                "name": "Yanbu Industrial City",
                "country": "Saudi Arabia",
                "region": "Medina",
                "center_lat": 23.9911,
                "center_lon": 38.1890,
                "timezone": "Asia/Riyadh",
                "description": "Red Sea refining and petrochemical center"
            },
            {
                "name": "Port of Ulsan",
                "country": "South Korea",
                "region": "Ulsan",
                "center_lat": 35.4676,
                "center_lon": 129.3890,
                "timezone": "Asia/Seoul",
                "description": "Asia Pacific petroleum and petrochemical hub"
            },
            {
                "name": "Saldanha Bay Oil Storage",
                "country": "South Africa",
                "region": "Western Cape",
                "center_lat": -33.0211,
                "center_lon": 17.9440,
                "timezone": "Africa/Johannesburg",
                "description": "Strategic crude storage on South African west coast"
            },
            {
                "name": "Novorossiysk Oil Terminal",
                "country": "Russia",
                "region": "Krasnodar Krai",
                "center_lat": 44.7125,
                "center_lon": 37.7693,
                "timezone": "Europe/Moscow",
                "description": "Black Sea export terminal for Caspian crude"
            },
            {
                "name": "Port of Montreal",
                "country": "Canada",
                "region": "Quebec",
                "center_lat": 45.5845,
                "center_lon": -73.5140,
                "timezone": "America/Toronto",
                "description": "Eastern Canadian petroleum import/export hub"
            },
            {
                "name": "Freeport Oil Terminal",
                "country": "Bahamas",
                "region": "Grand Bahama",
                "center_lat": 26.5143,
                "center_lon": -78.7750,
                "timezone": "America/Nassau",
                "description": "Caribbean strategic crude and products storage"
            },
            {
                "name": "Port of Rotterdam",
                "country": "Netherlands",
                "region": "South Holland",
                "center_lat": 51.9239,
                "center_lon": 4.4739,
                "timezone": "Europe/Amsterdam",
                "description": "Major European oil storage and refining hub"
            },
            {
                "name": "Port of Le Havre",
                "country": "France",
                "region": "Normandy",
                "center_lat": 49.4900,
                "center_lon": 0.1333,
                "timezone": "Europe/Paris",
                "description": "Northwest Europe oil storage and refining center"
            },
            {
                "name": "Port of Marseille",
                "country": "France",
                "region": "Provence-Alpes-Côte d'Azur",
                "center_lat": 43.2964,
                "center_lon": 5.3696,
                "timezone": "Europe/Paris",
                "description": "Mediterranean oil storage and refining hub"
            },
            {
                "name": "Port of Genoa",
                "country": "Italy",
                "region": "Liguria",
                "center_lat": 44.4039,
                "center_lon": 8.9333,
                "timezone": "Europe/Rome",
                "description": "Mediterranean oil storage and refining hub"
            },
            {
                "name": "Port of Trieste",
                "country": "Italy",
                "region": "Friuli-Venezia Giulia",
                "center_lat": 45.6497,
                "center_lon": 13.7639,
                "timezone": "Europe/Rome",
                "description": "Adriatic oil storage and refining hub"
            },
            {
                "name": "Port of Istanbul",
                "country": "Turkey",
                "region": "Istanbul",
                "center_lat": 41.0082,
                "center_lon": 28.9744,
                "timezone": "Europe/Istanbul",
                "description": "Bosphorus Strait oil storage and refining hub"
            },
            {
                "name": "Port of Odessa",
                "country": "Ukraine",
                "region": "Odessa Oblast",
                "center_lat": 46.4833,
                "center_lon": 30.7239,
                "timezone": "Europe/Kiev",
                "description": "Black Sea oil storage and refining hub"
            },
            {
                "name": "Port of Constanta",
                "country": "Romania",
                "region": "Constanța",
                "center_lat": 44.1750,
                "center_lon": 28.6539,
                "timezone": "Europe/Bucharest",
                "description": "Black Sea oil storage and refining hub"
            }
        ]

        return sites
