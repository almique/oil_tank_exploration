import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  GlobeAltIcon,
  BuildingOfficeIcon,
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusIcon,
} from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';

import { api } from '../services/api';
import GlobalMap from '../components/GlobalMap';
import TrendChart from '../components/TrendChart';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

interface GlobalSummary {
  total_sites: number;
  total_tanks: number;
  active_sites: number;
  latest_global_volume_bbl: number | null;
  global_trend_7d: string | null;
  last_updated: string;
  regional_breakdown: Record<string, any>;
}

interface SiteAnalysis {
  site: {
    id: number;
    name: string;
    country: string;
    center_lat: number;
    center_lon: number;
  };
  latest_aggregate: {
    total_volume_bbl: number;
    average_fill_fraction: number;
    trend_direction: string;
  } | null;
  tank_count: number;
  active_tank_count: number;
  trend_7d: string | null;
  volume_change_7d_pct: number | null;
}

const Dashboard: React.FC = () => {
  const {
    data: globalSummary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useQuery<GlobalSummary>({
    queryKey: ['global-summary'],
    queryFn: () => api.get('/api/global-summary').then((res) => res.data),
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });

  const {
    data: sites,
    isLoading: sitesLoading,
    error: sitesError,
  } = useQuery<SiteAnalysis[]>({
    queryKey: ['sites-analysis'],
    queryFn: async () => {
      const sitesResponse = await api.get('/api/sites');
      const sites = sitesResponse.data;
      
      const analysisPromises = sites.map((site: any) =>
        api.get(`/api/sites/${site.id}/analysis`).then((res) => res.data)
      );
      
      return Promise.all(analysisPromises);
    },
    refetchInterval: 10 * 60 * 1000, // Refetch every 10 minutes
  });

  const getTrendIcon = (trend: string | null | undefined) => {
    switch (trend) {
      case 'increasing':
        return <ArrowTrendingUpIcon className="w-5 h-5 text-success-500" />;
      case 'decreasing':
        return <ArrowTrendingDownIcon className="w-5 h-5 text-danger-500" />;
      default:
        return <MinusIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  const getTrendColor = (trend: string | null | undefined) => {
    switch (trend) {
      case 'increasing':
        return 'text-success-600';
      case 'decreasing':
        return 'text-danger-600';
      default:
        return 'text-gray-500';
    }
  };

  const formatVolume = (volume: number | null | undefined) => {
    if (!volume) return 'N/A';
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(1)}M bbl`;
    }
    if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K bbl`;
    }
    return `${volume.toFixed(0)} bbl`;
  };

  const formatPercentage = (pct: number | null | undefined) => {
    if (!pct && pct !== 0) return 'N/A';
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(1)}%`;
  };

  if (summaryLoading || sitesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (summaryError || sitesError) {
    return (
      <ErrorMessage
        title="Failed to load dashboard data"
        message="Please try refreshing the page or check your connection."
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Global Oil Storage Monitor</h1>
        <p className="mt-2 text-gray-600">
          Real-time monitoring of oil storage tank levels worldwide using satellite imagery
        </p>
      </div>

      {/* Global Statistics */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="card"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <GlobeAltIcon className="w-8 h-8 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Sites</p>
              <p className="text-2xl font-semibold text-gray-900">
                {globalSummary?.total_sites || 0}
              </p>
              <p className="text-sm text-gray-500">
                {globalSummary?.active_sites || 0} active
              </p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="card"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <BuildingOfficeIcon className="w-8 h-8 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Tanks</p>
              <p className="text-2xl font-semibold text-gray-900">
                {globalSummary?.total_tanks || 0}
              </p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <ChartBarIcon className="w-8 h-8 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Global Volume</p>
              <p className="text-2xl font-semibold text-gray-900">
                {formatVolume(globalSummary?.latest_global_volume_bbl)}
              </p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="card"
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              {getTrendIcon(globalSummary?.global_trend_7d)}
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">7-Day Trend</p>
              <p className={`text-2xl font-semibold capitalize ${getTrendColor(globalSummary?.global_trend_7d)}`}>
                {globalSummary?.global_trend_7d || 'Stable'}
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Global Map */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="card"
      >
        <div className="card-header">
          <h3 className="text-lg font-medium text-gray-900">Global Storage Sites</h3>
          <p className="text-sm text-gray-500">
            Interactive map showing oil storage locations and current status
          </p>
        </div>
        <div className="h-96">
          <GlobalMap sites={sites || []} />
        </div>
      </motion.div>

      {/* Site Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="card"
        >
          <div className="card-header">
            <h3 className="text-lg font-medium text-gray-900">Recent Activity</h3>
          </div>
          <div className="space-y-4">
            {sites?.slice(0, 5).map((site, index) => (
              <div key={site.site.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">{site.site.name}</p>
                  <p className="text-sm text-gray-500">{site.site.country}</p>
                </div>
                <div className="text-right">
                  <div className="flex items-center">
                    {getTrendIcon(site.trend_7d)}
                    <span className={`ml-1 text-sm font-medium ${getTrendColor(site.trend_7d)}`}>
                      {formatPercentage(site.volume_change_7d_pct)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500">
                    {formatVolume(site.latest_aggregate?.total_volume_bbl)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Global Trend Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="card"
        >
          <div className="card-header">
            <h3 className="text-lg font-medium text-gray-900">Global Volume Trend</h3>
          </div>
          <div className="h-64">
            <TrendChart sites={sites || []} />
          </div>
        </motion.div>
      </div>

      {/* Regional Breakdown */}
      {globalSummary?.regional_breakdown && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="card"
        >
          <div className="card-header">
            <h3 className="text-lg font-medium text-gray-900">Regional Breakdown</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {Object.entries(globalSummary.regional_breakdown).map(([country, data]: [string, any]) => (
              <div key={country} className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">{data.sites}</p>
                <p className="text-sm text-gray-500">{country}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Last Updated */}
      <div className="text-center text-sm text-gray-500">
        Last updated: {globalSummary?.last_updated ? new Date(globalSummary.last_updated).toLocaleString() : 'N/A'}
      </div>
    </div>
  );
};

export default Dashboard;
