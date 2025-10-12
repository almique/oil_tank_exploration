import axios from 'axios';

// Create axios instance
export const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Unauthorized - clear token and redirect to login
      localStorage.removeItem('auth_token');
      // window.location.href = '/login';
    }
    
    return Promise.reject(error);
  }
);

// API endpoints
export const endpoints = {
  // Sites
  sites: '/api/sites',
  site: (id: number) => `/api/sites/${id}`,
  siteAnalysis: (id: number) => `/api/sites/${id}/analysis`,
  
  // Tanks
  tanks: '/api/tanks',
  tank: (id: number) => `/api/tanks/${id}`,
  
  // Scenes
  scenes: '/api/scenes',
  scene: (id: number) => `/api/scenes/${id}`,
  
  // Measurements
  measurements: '/api/measurements',
  measurement: (id: number) => `/api/measurements/${id}`,
  
  // Aggregates
  aggregates: '/api/aggregates',
  
  // Alerts
  alerts: '/api/alerts',
  alert: (id: number) => `/api/alerts/${id}`,
  acknowledgeAlert: (id: number) => `/api/alerts/${id}/acknowledge`,
  
  // Global
  globalSummary: '/api/global-summary',
  
  // Processing
  processSatelliteData: '/api/process/satellite-data',
  fetchImagery: '/api/process/fetch-imagery',
  detectTanks: '/api/process/detect-tanks',
};

// Type definitions
export interface Site {
  id: number;
  name: string;
  country: string;
  region?: string;
  center_lat: number;
  center_lon: number;
  timezone: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface Tank {
  id: number;
  site_id: number;
  lat: number;
  lon: number;
  estimated_diameter_m?: number;
  wall_height_m?: number;
  roof_type: 'floating' | 'fixed' | 'unknown';
  tank_number?: string;
  operator?: string;
  capacity_bbl?: number;
  source?: string;
  confidence: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface Scene {
  id: number;
  site_id: number;
  satellite: string;
  sensor?: string;
  scene_id: string;
  acquisition_time: string;
  processed_time: string;
  sun_elevation?: number;
  sun_azimuth?: number;
  cloud_coverage?: number;
  raw_data_url?: string;
  processed_data_path?: string;
  thumbnail_path?: string;
  is_processed: boolean;
  processing_error?: string;
  quality_score?: number;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface Measurement {
  id: number;
  tank_id: number;
  scene_id: number;
  method: 'shadow_optical' | 'sar_backscatter' | 'ml_detection';
  roof_height_m?: number;
  fill_fraction?: number;
  volume_bbl?: number;
  confidence: number;
  shadow_length_px?: number;
  shadow_angle_deg?: number;
  processing_time_ms?: number;
  algorithm_version?: string;
  parameters?: Record<string, any>;
  is_outlier: boolean;
  quality_flags?: Record<string, any>;
  created_at: string;
}

export interface Aggregate {
  id: number;
  site_id: number;
  date: string;
  aggregation_period: string;
  total_volume_bbl?: number;
  average_fill_fraction?: number;
  tank_count?: number;
  active_tank_count?: number;
  overall_confidence?: number;
  measurement_count?: number;
  outlier_count?: number;
  volume_change_bbl?: number;
  volume_change_pct?: number;
  trend_direction?: string;
  eia_volume_bbl?: number;
  validation_error_pct?: number;
  created_at: string;
}

export interface Alert {
  id: number;
  site_id?: number;
  tank_id?: number;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description?: string;
  trigger_value?: number;
  threshold_value?: number;
  metadata?: Record<string, any>;
  is_active: boolean;
  acknowledged_at?: string;
  resolved_at?: string;
  created_at: string;
}

export interface GlobalSummary {
  total_sites: number;
  total_tanks: number;
  active_sites: number;
  latest_global_volume_bbl?: number;
  global_trend_7d?: string;
  last_updated: string;
  regional_breakdown: Record<string, any>;
}

export interface SiteAnalysis {
  site: Site;
  latest_aggregate?: Aggregate;
  tank_count: number;
  active_tank_count: number;
  latest_measurement_time?: string;
  trend_7d?: string;
  volume_change_7d_pct?: number;
}

// API service functions
export const apiService = {
  // Sites
  async getSites(params?: { country?: string; is_active?: boolean }) {
    const response = await api.get<Site[]>(endpoints.sites, { params });
    return response.data;
  },

  async getSite(id: number) {
    const response = await api.get<Site & { tanks: Tank[] }>(endpoints.site(id));
    return response.data;
  },

  async getSiteAnalysis(id: number) {
    const response = await api.get<SiteAnalysis>(endpoints.siteAnalysis(id));
    return response.data;
  },

  async createSite(data: Omit<Site, 'id' | 'created_at' | 'updated_at'>) {
    const response = await api.post<Site>(endpoints.sites, data);
    return response.data;
  },

  async updateSite(id: number, data: Partial<Site>) {
    const response = await api.put<Site>(endpoints.site(id), data);
    return response.data;
  },

  async deleteSite(id: number) {
    await api.delete(endpoints.site(id));
  },

  // Tanks
  async getTanks(params?: { site_id?: number; is_active?: boolean }) {
    const response = await api.get<Tank[]>(endpoints.tanks, { params });
    return response.data;
  },

  async getTank(id: number) {
    const response = await api.get<Tank & { measurements: Measurement[] }>(endpoints.tank(id));
    return response.data;
  },

  async createTank(data: Omit<Tank, 'id' | 'created_at' | 'updated_at'>) {
    const response = await api.post<Tank>(endpoints.tanks, data);
    return response.data;
  },

  async updateTank(id: number, data: Partial<Tank>) {
    const response = await api.put<Tank>(endpoints.tank(id), data);
    return response.data;
  },

  // Measurements
  async getMeasurements(params?: { 
    tank_id?: number; 
    scene_id?: number; 
    method?: string;
    limit?: number;
  }) {
    const response = await api.get<Measurement[]>(endpoints.measurements, { params });
    return response.data;
  },

  // Aggregates
  async getAggregates(params?: { 
    site_id?: number; 
    period?: string;
    limit?: number;
  }) {
    const response = await api.get<Aggregate[]>(endpoints.aggregates, { params });
    return response.data;
  },

  // Global
  async getGlobalSummary() {
    const response = await api.get<GlobalSummary>(endpoints.globalSummary);
    return response.data;
  },

  // Alerts
  async getAlerts(params?: { site_id?: number; is_active?: boolean }) {
    const response = await api.get<Alert[]>(endpoints.alerts, { params });
    return response.data;
  },

  async acknowledgeAlert(id: number) {
    await api.put(endpoints.acknowledgeAlert(id));
  },

  // Processing
  async processSatelliteData(data: {
    site_id?: number;
    scene_id?: number;
    force_reprocess?: boolean;
    analysis_methods?: string[];
  }) {
    const response = await api.post(endpoints.processSatelliteData, data);
    return response.data;
  },

  async fetchImagery(site_id?: number) {
    const response = await api.post(endpoints.fetchImagery, { site_id });
    return response.data;
  },

  async detectTanks(site_id: number) {
    const response = await api.post(endpoints.detectTanks, { site_id });
    return response.data;
  },
};

export default api;
