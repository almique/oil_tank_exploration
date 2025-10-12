import cv2
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds
import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import logging
from pathlib import Path
import json

from sklearn.cluster import DBSCAN
from skimage import measure, morphology, filters
from skimage.feature import canny
from skimage.transform import hough_circle, hough_circle_peaks

from config import settings

logger = logging.getLogger(__name__)

@dataclass
class DetectedTank:
    center_x: float
    center_y: float
    radius_px: float
    confidence: float
    lat: float
    lon: float
    diameter_m: float
    method: str

@dataclass
class ShadowMeasurement:
    tank_center_x: float
    tank_center_y: float
    shadow_length_px: float
    shadow_angle_deg: float
    roof_height_m: float
    fill_fraction: float
    confidence: float
    sun_elevation: float
    sun_azimuth: float

class TankDetector:
    """Computer vision service for detecting oil storage tanks in satellite imagery"""
    
    def __init__(self):
        self.min_tank_radius_px = 5
        self.max_tank_radius_px = 100
        self.tank_confidence_threshold = 0.3
    
    def detect_tanks_hough(self, 
                          image: np.ndarray, 
                          pixel_size_m: float = 10.0) -> List[DetectedTank]:
        """
        Detect circular tanks using Hough Circle Transform
        
        Args:
            image: Input satellite image (RGB or grayscale)
            pixel_size_m: Size of one pixel in meters
            
        Returns:
            List of detected tanks
        """
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # Preprocessing
        gray = cv2.medianBlur(gray, 5)
        
        # Detect circles using HoughCircles
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=30,
            param1=50,
            param2=30,
            minRadius=self.min_tank_radius_px,
            maxRadius=self.max_tank_radius_px
        )
        
        detected_tanks = []
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            
            for (x, y, r) in circles:
                # Calculate confidence based on circularity and contrast
                confidence = self._calculate_tank_confidence(gray, x, y, r)
                
                if confidence > self.tank_confidence_threshold:
                    # Convert to geographic coordinates (placeholder - needs proper transformation)
                    lat, lon = self._pixel_to_geo(x, y, image.shape)
                    diameter_m = r * 2 * pixel_size_m
                    
                    tank = DetectedTank(
                        center_x=float(x),
                        center_y=float(y),
                        radius_px=float(r),
                        confidence=confidence,
                        lat=lat,
                        lon=lon,
                        diameter_m=diameter_m,
                        method="hough_circles"
                    )
                    detected_tanks.append(tank)
        
        logger.info(f"Detected {len(detected_tanks)} tanks using Hough circles")
        return detected_tanks
    
    def detect_tanks_contours(self, 
                            image: np.ndarray, 
                            pixel_size_m: float = 10.0) -> List[DetectedTank]:
        """
        Detect tanks using contour analysis
        
        Args:
            image: Input satellite image
            pixel_size_m: Size of one pixel in meters
            
        Returns:
            List of detected tanks
        """
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        
        # Threshold to find bright circular objects (tanks are often bright)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_tanks = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if area < 100 or area > 10000:
                continue
            
            # Check circularity
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * math.pi * area / (perimeter * perimeter)
            
            if circularity > 0.7:  # Circular enough
                # Get bounding circle
                (x, y), radius = cv2.minEnclosingCircle(contour)
                
                confidence = circularity * 0.8  # Base confidence on circularity
                
                if confidence > self.tank_confidence_threshold:
                    lat, lon = self._pixel_to_geo(int(x), int(y), image.shape)
                    diameter_m = radius * 2 * pixel_size_m
                    
                    tank = DetectedTank(
                        center_x=float(x),
                        center_y=float(y),
                        radius_px=float(radius),
                        confidence=confidence,
                        lat=lat,
                        lon=lon,
                        diameter_m=diameter_m,
                        method="contours"
                    )
                    detected_tanks.append(tank)
        
        logger.info(f"Detected {len(detected_tanks)} tanks using contours")
        return detected_tanks
    
    def detect_tanks_template_matching(self, 
                                     image: np.ndarray, 
                                     pixel_size_m: float = 10.0) -> List[DetectedTank]:
        """
        Detect tanks using template matching with circular templates
        
        Args:
            image: Input satellite image
            pixel_size_m: Size of one pixel in meters
            
        Returns:
            List of detected tanks
        """
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        detected_tanks = []
        
        # Try different template sizes
        for radius in range(self.min_tank_radius_px, self.max_tank_radius_px, 5):
            # Create circular template
            template = self._create_circular_template(radius)
            
            # Template matching
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            
            # Find peaks
            locations = np.where(result >= 0.6)
            
            for pt in zip(*locations[::-1]):
                x, y = pt[0] + radius, pt[1] + radius
                confidence = float(result[pt[1], pt[0]])
                
                # Check if this detection is too close to existing ones
                too_close = any(
                    math.sqrt((x - tank.center_x)**2 + (y - tank.center_y)**2) < radius
                    for tank in detected_tanks
                )
                
                if not too_close:
                    lat, lon = self._pixel_to_geo(x, y, image.shape)
                    diameter_m = radius * 2 * pixel_size_m
                    
                    tank = DetectedTank(
                        center_x=float(x),
                        center_y=float(y),
                        radius_px=float(radius),
                        confidence=confidence,
                        lat=lat,
                        lon=lon,
                        diameter_m=diameter_m,
                        method="template_matching"
                    )
                    detected_tanks.append(tank)
        
        logger.info(f"Detected {len(detected_tanks)} tanks using template matching")
        return detected_tanks
    
    def _calculate_tank_confidence(self, 
                                 image: np.ndarray, 
                                 x: int, 
                                 y: int, 
                                 radius: int) -> float:
        """Calculate confidence score for a potential tank detection"""
        
        # Create circular mask
        mask = np.zeros(image.shape, dtype=np.uint8)
        cv2.circle(mask, (x, y), radius, 255, -1)
        
        # Calculate mean intensity inside circle
        circle_mean = cv2.mean(image, mask=mask)[0]
        
        # Calculate mean intensity in surrounding ring
        outer_mask = np.zeros(image.shape, dtype=np.uint8)
        cv2.circle(outer_mask, (x, y), int(radius * 1.5), 255, -1)
        cv2.circle(outer_mask, (x, y), radius, 0, -1)
        
        ring_mean = cv2.mean(image, mask=outer_mask)[0]
        
        # Tanks are typically brighter than surroundings
        contrast = (circle_mean - ring_mean) / 255.0
        
        # Calculate circularity using edge detection
        roi = image[max(0, y-radius):y+radius, max(0, x-radius):x+radius]
        edges = cv2.Canny(roi, 50, 150)
        
        # Find contours in ROI
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        circularity = 0.0
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            perimeter = cv2.arcLength(largest_contour, True)
            
            if perimeter > 0:
                circularity = 4 * math.pi * area / (perimeter * perimeter)
        
        # Combine metrics
        confidence = (contrast * 0.4 + circularity * 0.6)
        return max(0.0, min(1.0, confidence))
    
    def _create_circular_template(self, radius: int) -> np.ndarray:
        """Create a circular template for template matching"""
        
        size = radius * 2 + 1
        template = np.zeros((size, size), dtype=np.uint8)
        cv2.circle(template, (radius, radius), radius, 255, -1)
        
        # Add some Gaussian blur to make it more realistic
        template = cv2.GaussianBlur(template, (5, 5), 1)
        
        return template
    
    def _pixel_to_geo(self, x: int, y: int, image_shape: Tuple[int, int]) -> Tuple[float, float]:
        """Convert pixel coordinates to geographic coordinates (placeholder)"""
        # This is a placeholder - in real implementation, you'd use the image's
        # geotransform information from rasterio or GDAL
        
        # For now, return dummy coordinates
        lat = 35.0 + (y / image_shape[0]) * 0.1
        lon = -96.0 + (x / image_shape[1]) * 0.1
        
        return lat, lon

class ShadowAnalyzer:
    """Analyze tank shadows to estimate fill levels"""
    
    def __init__(self):
        self.shadow_detection_threshold = 0.3
    
    def analyze_tank_shadow(self, 
                          image: np.ndarray,
                          tank: DetectedTank,
                          sun_elevation: float,
                          sun_azimuth: float,
                          pixel_size_m: float = 10.0,
                          tank_wall_height_m: float = 15.0) -> Optional[ShadowMeasurement]:
        """
        Analyze tank shadow to estimate fill level
        
        Args:
            image: Satellite image
            tank: Detected tank
            sun_elevation: Sun elevation angle in degrees
            sun_azimuth: Sun azimuth angle in degrees
            pixel_size_m: Size of one pixel in meters
            tank_wall_height_m: Estimated tank wall height
            
        Returns:
            Shadow measurement or None if analysis fails
        """
        
        if sun_elevation <= 0:
            logger.warning("Sun elevation <= 0, cannot analyze shadow")
            return None
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # Extract region around tank
        x, y, r = int(tank.center_x), int(tank.center_y), int(tank.radius_px)
        
        # Expand region to include potential shadow
        shadow_length_estimate = int(tank_wall_height_m / pixel_size_m / math.tan(math.radians(sun_elevation)))
        roi_size = max(r * 3, shadow_length_estimate + r)
        
        x1 = max(0, x - roi_size)
        y1 = max(0, y - roi_size)
        x2 = min(image.shape[1], x + roi_size)
        y2 = min(image.shape[0], y + roi_size)
        
        roi = gray[y1:y2, x1:x2]
        
        # Adjust tank center relative to ROI
        tank_x_roi = x - x1
        tank_y_roi = y - y1
        
        # Find shadow
        shadow_info = self._detect_tank_shadow(
            roi, tank_x_roi, tank_y_roi, r, sun_azimuth
        )
        
        if not shadow_info:
            return None
        
        shadow_length_px, shadow_angle = shadow_info
        
        # Calculate roof height from shadow geometry
        roof_height_m = shadow_length_px * pixel_size_m * math.tan(math.radians(sun_elevation))
        
        # Estimate fill fraction (assuming floating roof)
        # This is a simplified model - real tanks have more complex geometry
        fill_fraction = min(1.0, max(0.0, roof_height_m / tank_wall_height_m))
        
        # Calculate confidence based on shadow clarity and geometry consistency
        confidence = self._calculate_shadow_confidence(
            roi, tank_x_roi, tank_y_roi, r, shadow_length_px, shadow_angle, sun_azimuth
        )
        
        return ShadowMeasurement(
            tank_center_x=tank.center_x,
            tank_center_y=tank.center_y,
            shadow_length_px=shadow_length_px,
            shadow_angle_deg=shadow_angle,
            roof_height_m=roof_height_m,
            fill_fraction=fill_fraction,
            confidence=confidence,
            sun_elevation=sun_elevation,
            sun_azimuth=sun_azimuth
        )
    
    def _detect_tank_shadow(self, 
                          roi: np.ndarray,
                          tank_x: int,
                          tank_y: int,
                          tank_radius: int,
                          sun_azimuth: float) -> Optional[Tuple[float, float]]:
        """Detect shadow cast by tank"""
        
        # Calculate expected shadow direction (opposite to sun)
        shadow_direction = (sun_azimuth + 180) % 360
        
        # Create search sector for shadow
        search_angle_range = 30  # degrees
        
        # Apply threshold to find dark regions (shadows)
        _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Invert so shadows are white
        shadow_mask = cv2.bitwise_not(thresh)
        
        # Remove the tank itself from shadow mask
        cv2.circle(shadow_mask, (tank_x, tank_y), tank_radius + 2, 0, -1)
        
        # Find shadow contours
        contours, _ = cv2.findContours(shadow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_shadow = None
        best_score = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 50:  # Too small to be a tank shadow
                continue
            
            # Get contour centroid
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Calculate angle from tank center to shadow centroid
            angle_to_shadow = math.degrees(math.atan2(cy - tank_y, cx - tank_x))
            angle_to_shadow = (angle_to_shadow + 360) % 360
            
            # Check if shadow is in expected direction
            angle_diff = abs(angle_to_shadow - shadow_direction)
            angle_diff = min(angle_diff, 360 - angle_diff)
            
            if angle_diff < search_angle_range:
                # Calculate distance from tank edge to shadow centroid
                distance = math.sqrt((cx - tank_x)**2 + (cy - tank_y)**2) - tank_radius
                
                # Score based on direction alignment and reasonable distance
                direction_score = 1.0 - (angle_diff / search_angle_range)
                distance_score = 1.0 if 5 < distance < 100 else 0.5
                area_score = min(1.0, area / 1000)
                
                total_score = direction_score * distance_score * area_score
                
                if total_score > best_score:
                    best_score = total_score
                    best_shadow = (distance, angle_to_shadow)
        
        return best_shadow
    
    def _calculate_shadow_confidence(self, 
                                   roi: np.ndarray,
                                   tank_x: int,
                                   tank_y: int,
                                   tank_radius: int,
                                   shadow_length: float,
                                   shadow_angle: float,
                                   sun_azimuth: float) -> float:
        """Calculate confidence in shadow measurement"""
        
        # Check geometric consistency
        expected_shadow_direction = (sun_azimuth + 180) % 360
        angle_diff = abs(shadow_angle - expected_shadow_direction)
        angle_diff = min(angle_diff, 360 - angle_diff)
        
        geometric_score = 1.0 - (angle_diff / 30.0)  # 30 degree tolerance
        
        # Check shadow length reasonableness
        length_score = 1.0 if 5 < shadow_length < 50 else 0.5
        
        # Check image quality in shadow region
        shadow_end_x = int(tank_x + (shadow_length + tank_radius) * math.cos(math.radians(shadow_angle)))
        shadow_end_y = int(tank_y + (shadow_length + tank_radius) * math.sin(math.radians(shadow_angle)))
        
        quality_score = 1.0
        if (0 <= shadow_end_x < roi.shape[1] and 0 <= shadow_end_y < roi.shape[0]):
            # Check contrast between shadow and surrounding area
            shadow_intensity = roi[shadow_end_y, shadow_end_x]
            surrounding_mean = np.mean(roi)
            contrast = (surrounding_mean - shadow_intensity) / 255.0
            quality_score = min(1.0, max(0.0, contrast))
        
        # Combine scores
        confidence = geometric_score * 0.4 + length_score * 0.3 + quality_score * 0.3
        return max(0.0, min(1.0, confidence))

class VisionService:
    """Main computer vision service for tank detection and analysis"""
    
    def __init__(self):
        self.tank_detector = TankDetector()
        self.shadow_analyzer = ShadowAnalyzer()
        self.default_crop_buffer_km = settings.imagery_crop_buffer_km

    def crop_image_to_site(self,
                           image_path: str,
                           site_lat: float,
                           site_lon: float,
                           buffer_km: Optional[float] = None) -> Optional[str]:
        """Crop a larger satellite image to the vicinity of a site."""

        crop_buffer_km = buffer_km or self.default_crop_buffer_km
        if crop_buffer_km <= 0:
            return image_path

        buffer_deg = crop_buffer_km / 111.0
        min_lat = site_lat - buffer_deg
        max_lat = site_lat + buffer_deg
        min_lon = site_lon - buffer_deg
        max_lon = site_lon + buffer_deg

        src_path = Path(image_path)
        output_path = src_path.with_name(f"{src_path.stem}_crop{src_path.suffix}")

        try:
            with rasterio.open(image_path) as src:
                bounds_4326 = (min_lon, min_lat, max_lon, max_lat)

                if src.crs:
                    try:
                        left, bottom, right, top = transform_bounds(
                            "EPSG:4326",
                            src.crs,
                            *bounds_4326,
                            densify_pts=21
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to transform crop bounds for %s: %s", image_path, exc
                        )
                        left, bottom, right, top = bounds_4326
                else:
                    left, bottom, right, top = bounds_4326

                # Convert geographic bounds to pixel indices
                row_min, col_min = src.index(left, top)
                row_max, col_max = src.index(right, bottom)

                row_start, row_stop = sorted([row_min, row_max])
                col_start, col_stop = sorted([col_min, col_max])

                # Clamp to image bounds
                row_start = max(row_start, 0)
                col_start = max(col_start, 0)
                row_stop = min(row_stop, src.height)
                col_stop = min(col_stop, src.width)

                if row_stop <= row_start or col_stop <= col_start:
                    logger.warning("Crop window invalid for image %s", image_path)
                    return image_path

                window = Window.from_slices(
                    (row_start, row_stop), (col_start, col_stop)
                )

                out_meta = src.meta.copy()
                out_meta.update(
                    {
                        "height": int(window.height),
                        "width": int(window.width),
                        "transform": src.window_transform(window),
                    }
                )

                data = src.read(window=window)

            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(data)

            logger.info("Cropped %s to %s", image_path, output_path)
            return str(output_path)

        except Exception as exc:
            logger.error("Failed to crop image %s: %s", image_path, exc)
            return image_path

    def process_satellite_image(self, 
                              image_path: str,
                              sun_elevation: Optional[float] = None,
                              sun_azimuth: Optional[float] = None,
                              pixel_size_m: Optional[float] = None,
                              site_lat: Optional[float] = None,
                              site_lon: Optional[float] = None,
                              buffer_km: Optional[float] = None) -> Dict:
        """Process satellite image to detect tanks and analyze shadows."""

        try:
            target_path = image_path
            if site_lat is not None and site_lon is not None:
                target_path = self.crop_image_to_site(
                    image_path, site_lat, site_lon, buffer_km
                )

            # Load image
            with rasterio.open(target_path) as src:
                image = src.read([1, 2, 3])  # RGB bands
                image = np.transpose(image, (1, 2, 0))

                # Determine pixel size
                effective_pixel_size = pixel_size_m
                if effective_pixel_size is None:
                    res_x, res_y = src.res
                    if src.crs and src.crs.is_projected:
                        effective_pixel_size = float(max(abs(res_x), abs(res_y)))
                    else:
                        effective_pixel_size = float(max(abs(res_x), abs(res_y)) * 111_000)

                pixel_size = effective_pixel_size or 10.0

                # Get geospatial info
                transform = src.transform
                crs = src.crs

                # Resample image to improve resolution
                if pixel_size < 5.0:
                    scale_factor = 5.0 / pixel_size
                    image = cv2.resize(image, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
                    pixel_size = 5.0

            # Detect tanks using multiple methods
            tanks_hough = self.tank_detector.detect_tanks_hough(image, pixel_size)
            tanks_contours = self.tank_detector.detect_tanks_contours(image, pixel_size)
            
            # Combine and deduplicate detections
            all_tanks = self._merge_detections([tanks_hough, tanks_contours])

            shadow_measurements: List[ShadowMeasurement] = []
            if sun_elevation and sun_azimuth:
                for tank in all_tanks:
                    shadow = self.shadow_analyzer.analyze_tank_shadow(
                        image, tank, sun_elevation, sun_azimuth, pixel_size
                    )
                    if shadow:
                        shadow_measurements.append(shadow)

            results = {
                "tanks_detected": len(all_tanks),
                "tanks": [self._tank_to_dict(tank) for tank in all_tanks],
                "shadow_measurements": len(shadow_measurements),
                "shadows": [self._shadow_to_dict(shadow) for shadow in shadow_measurements],
                "processing_info": {
                    "image_path": image_path,
                    "processed_path": target_path,
                    "pixel_size_m": pixel_size,
                    "sun_elevation": sun_elevation,
                    "sun_azimuth": sun_azimuth,
                    "image_shape": image.shape
                }
            }

            logger.info(
                "Processed %s (cropped %s): %d tanks, %d shadow measurements",
                image_path,
                target_path,
                len(all_tanks),
                len(shadow_measurements),
            )
            return results
            
        except Exception as e:
            logger.error(f"Error processing image {target_path}: {e}")
            return {"error": str(e)}
    
    def _merge_detections(self, detection_lists: List[List[DetectedTank]]) -> List[DetectedTank]:
        """Merge and deduplicate tank detections from multiple methods"""
        
        all_detections = []
        for detections in detection_lists:
            all_detections.extend(detections)
        
        if not all_detections:
            return []
        
        # Use DBSCAN clustering to group nearby detections
        coordinates = np.array([[tank.center_x, tank.center_y] for tank in all_detections])
        
        clustering = DBSCAN(eps=20, min_samples=1).fit(coordinates)
        
        merged_tanks = []
        for cluster_id in set(clustering.labels_):
            cluster_tanks = [tank for i, tank in enumerate(all_detections) 
                           if clustering.labels_[i] == cluster_id]
            
            # Take the detection with highest confidence
            best_tank = max(cluster_tanks, key=lambda t: t.confidence)
            merged_tanks.append(best_tank)
        
        return merged_tanks
    
    def _tank_to_dict(self, tank: DetectedTank) -> Dict:
        """Convert DetectedTank to dictionary"""
        return {
            "center_x": tank.center_x,
            "center_y": tank.center_y,
            "radius_px": tank.radius_px,
            "confidence": tank.confidence,
            "lat": tank.lat,
            "lon": tank.lon,
            "diameter_m": tank.diameter_m,
            "method": tank.method
        }
    
    def _shadow_to_dict(self, shadow: ShadowMeasurement) -> Dict:
        """Convert ShadowMeasurement to dictionary"""
        return {
            "tank_center_x": shadow.tank_center_x,
            "tank_center_y": shadow.tank_center_y,
            "shadow_length_px": shadow.shadow_length_px,
            "shadow_angle_deg": shadow.shadow_angle_deg,
            "roof_height_m": shadow.roof_height_m,
            "fill_fraction": shadow.fill_fraction,
            "confidence": shadow.confidence,
            "sun_elevation": shadow.sun_elevation,
            "sun_azimuth": shadow.sun_azimuth
        }
