import React from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  MapPinIcon,
  BuildingOfficeIcon,
  ChartBarIcon,
  CloudArrowDownIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';

import { apiService } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const SiteDetail: React.FC = () => {
  const { siteId } = useParams<{ siteId: string }>();
  const id = parseInt(siteId || '0');

  const {
    data: site,
    isLoading: siteLoading,
    error: siteError,
  } = useQuery({
    queryKey: ['site', id],
    queryFn: () => apiService.getSite(id),
    enabled: !!id,
  });

  const {
    data: analysis,
    isLoading: analysisLoading,
    error: analysisError,
  } = useQuery({
    queryKey: ['site-analysis', id],
    queryFn: () => apiService.getSiteAnalysis(id),
    enabled: !!id,
  });

  const {
    data: tanks,
    isLoading: tanksLoading,
    error: tanksError,
  } = useQuery({
    queryKey: ['tanks', id],
    queryFn: () => apiService.getTanks({ site_id: id }),
    enabled: !!id,
  });

  const fetchImageryMutation = useMutation({
    mutationFn: () => apiService.fetchImagery(id),
    onSuccess: (data) => {
      toast.success('Imagery fetch queued');
      if (data?.results?.length) {
        toast.success(`Fetched imagery for ${data.results.length} site(s)`);
      }
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error?.message || 'Failed to start imagery fetch';
      toast.error(message);
    },
  });

  const processDataMutation = useMutation({
    mutationFn: () =>
      apiService.processSatelliteData({
        site_id: id,
        force_reprocess: false,
        analysis_methods: ['shadow_optical'],
      }),
    onSuccess: () => {
      toast.success('Processing started');
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error?.message || 'Failed to start processing';
      toast.error(message);
    },
  });

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

  if (siteLoading || analysisLoading || tanksLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (siteError || analysisError || tanksError || !site) {
    return (
      <ErrorMessage
        title="Failed to load site details"
        message="Please try refreshing the page or check your connection."
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="card"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-3xl font-bold text-gray-900">{site.name}</h1>
              <div className={`w-3 h-3 rounded-full ${site.is_active ? 'bg-success-500' : 'bg-gray-400'}`} />
            </div>
            <div className="mt-2 flex items-center text-gray-600">
              <MapPinIcon className="w-5 h-5 mr-2" />
              <span>{site.country}</span>
              {site.region && <span>, {site.region}</span>}
              <span className="ml-4">
                {site.center_lat.toFixed(4)}, {site.center_lon.toFixed(4)}
              </span>
            </div>
            {site.description && (
              <p className="mt-3 text-gray-700">{site.description}</p>
            )}
          </div>
          <div className="flex space-x-2">
            <button
              className="btn btn-secondary"
              onClick={() => fetchImageryMutation.mutate()}
              disabled={fetchImageryMutation.isPending}
            >
              <CloudArrowDownIcon className="w-5 h-5 mr-2" />
              {fetchImageryMutation.isPending ? 'Queuing...' : 'Fetch Imagery'}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => processDataMutation.mutate()}
              disabled={processDataMutation.isPending}
            >
              <CpuChipIcon className="w-5 h-5 mr-2" />
              {processDataMutation.isPending ? 'Queuing...' : 'Process Data'}
            </button>
          </div>
        </div>
      </motion.div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="card"
        >
          <div className="flex items-center">
            <BuildingOfficeIcon className="w-8 h-8 text-primary-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Tanks</p>
              <p className="text-2xl font-semibold text-gray-900">
                {analysis?.tank_count || 0}
              </p>
              <p className="text-sm text-gray-500">
                {analysis?.active_tank_count || 0} active
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
            <ChartBarIcon className="w-8 h-8 text-primary-600" />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Volume</p>
              <p className="text-2xl font-semibold text-gray-900">
                {formatVolume(analysis?.latest_aggregate?.total_volume_bbl)}
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
            <div className="w-8 h-8 flex items-center justify-center">
              <div className="w-6 h-6 bg-primary-600 rounded-full flex items-center justify-center">
                <span className="text-white text-xs font-bold">%</span>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Avg Fill Level</p>
              <p className="text-2xl font-semibold text-gray-900">
                {analysis?.latest_aggregate?.average_fill_fraction
                  ? `${(analysis.latest_aggregate.average_fill_fraction * 100).toFixed(1)}%`
                  : 'N/A'}
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
            <div className="w-8 h-8 flex items-center justify-center">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                analysis?.trend_7d === 'increasing' ? 'bg-success-600' :
                analysis?.trend_7d === 'decreasing' ? 'bg-danger-600' : 'bg-gray-400'
              }`}>
                <span className="text-white text-xs">↗</span>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">7-Day Change</p>
              <p className={`text-2xl font-semibold ${getTrendColor(analysis?.trend_7d)}`}>
                {formatPercentage(analysis?.volume_change_7d_pct)}
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Tanks List */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="card"
      >
        <div className="card-header">
          <h3 className="text-lg font-medium text-gray-900">Storage Tanks</h3>
          <p className="text-sm text-gray-500">
            Individual tank monitoring and analysis
          </p>
        </div>

        {tanks && tanks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tank
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Location
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Diameter
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Capacity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Source
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {tanks.map((tank) => (
                  <tr key={tank.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {tank.tank_number || `Tank ${tank.id}`}
                      </div>
                      {tank.operator && (
                        <div className="text-sm text-gray-500">{tank.operator}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {tank.lat.toFixed(4)}, {tank.lon.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {tank.estimated_diameter_m ? `${tank.estimated_diameter_m.toFixed(1)}m` : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {tank.capacity_bbl ? formatVolume(tank.capacity_bbl) : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        tank.is_active
                          ? 'bg-success-100 text-success-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {tank.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-primary-100 text-primary-800">
                        {tank.source || 'Manual'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <BuildingOfficeIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No tanks found</h3>
            <p className="mt-1 text-sm text-gray-500">
              Start by detecting tanks from satellite imagery or adding them manually.
            </p>
            <div className="mt-6 flex justify-center space-x-3">
              <button className="btn btn-secondary">
                <CloudArrowDownIcon className="w-5 h-5 mr-2" />
                Detect from OSM
              </button>
              <button className="btn btn-primary">
                Add Tank Manually
              </button>
            </div>
          </div>
        )}
      </motion.div>

      {/* Site Information */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="card"
      >
        <div className="card-header">
          <h3 className="text-lg font-medium text-gray-900">Site Information</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Basic Details</h4>
            <dl className="space-y-2">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Name:</dt>
                <dd className="text-sm font-medium text-gray-900">{site.name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Country:</dt>
                <dd className="text-sm font-medium text-gray-900">{site.country}</dd>
              </div>
              {site.region && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Region:</dt>
                  <dd className="text-sm font-medium text-gray-900">{site.region}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Timezone:</dt>
                <dd className="text-sm font-medium text-gray-900">{site.timezone}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Status:</dt>
                <dd className={`text-sm font-medium ${site.is_active ? 'text-success-600' : 'text-gray-500'}`}>
                  {site.is_active ? 'Active' : 'Inactive'}
                </dd>
              </div>
            </dl>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Coordinates</h4>
            <dl className="space-y-2">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Latitude:</dt>
                <dd className="text-sm font-medium text-gray-900">{site.center_lat.toFixed(6)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Longitude:</dt>
                <dd className="text-sm font-medium text-gray-900">{site.center_lon.toFixed(6)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Created:</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {new Date(site.created_at).toLocaleDateString()}
                </dd>
              </div>
              {site.updated_at && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Updated:</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {new Date(site.updated_at).toLocaleDateString()}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SiteDetail;
