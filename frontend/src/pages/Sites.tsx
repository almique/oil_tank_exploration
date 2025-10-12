import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  MapPinIcon,
  BuildingOfficeIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';

import { apiService, Site } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const Sites: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCountry, setSelectedCountry] = useState('');

  const {
    data: sites,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['sites'],
    queryFn: () => apiService.getSites(),
  });

  // Filter sites based on search and country
  const filteredSites = React.useMemo(() => {
    if (!sites) return [];
    
    return sites.filter((site) => {
      const matchesSearch = site.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          site.country.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCountry = !selectedCountry || site.country === selectedCountry;
      
      return matchesSearch && matchesCountry;
    });
  }, [sites, searchTerm, selectedCountry]);

  // Get unique countries for filter
  const countries = React.useMemo(() => {
    if (!sites) return [];
    return [...new Set(sites.map(site => site.country))].sort();
  }, [sites]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorMessage
        title="Failed to load sites"
        message="Please try refreshing the page or check your connection."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Storage Sites</h1>
          <p className="mt-1 text-gray-600">
            Manage and monitor oil storage sites worldwide
          </p>
        </div>
        <button className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Site
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search sites..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input pl-10"
              />
            </div>
          </div>
          <div className="sm:w-48">
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="input"
            >
              <option value="">All Countries</option>
              {countries.map((country) => (
                <option key={country} value={country}>
                  {country}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Sites Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredSites.map((site, index) => (
          <motion.div
            key={site.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Link to={`/sites/${site.id}`}>
              <div className="card hover:shadow-md transition-shadow duration-200 cursor-pointer">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-1">
                      {site.name}
                    </h3>
                    <div className="flex items-center text-sm text-gray-500">
                      <MapPinIcon className="w-4 h-4 mr-1" />
                      {site.country}
                      {site.region && `, ${site.region}`}
                    </div>
                  </div>
                  <div className={`w-3 h-3 rounded-full ${site.is_active ? 'bg-success-500' : 'bg-gray-400'}`} />
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Coordinates</span>
                    <span className="font-medium">
                      {site.center_lat.toFixed(3)}, {site.center_lon.toFixed(3)}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Timezone</span>
                    <span className="font-medium">{site.timezone}</span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Created</span>
                    <span className="font-medium">{formatDate(site.created_at)}</span>
                  </div>
                </div>

                {site.description && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {site.description}
                    </p>
                  </div>
                )}

                <div className="mt-4 flex items-center justify-between">
                  <div className="flex items-center space-x-4 text-xs text-gray-500">
                    <div className="flex items-center">
                      <BuildingOfficeIcon className="w-4 h-4 mr-1" />
                      <span>Tanks</span>
                    </div>
                    <div className="flex items-center">
                      <ChartBarIcon className="w-4 h-4 mr-1" />
                      <span>Analytics</span>
                    </div>
                  </div>
                  <span className="text-xs text-primary-600 font-medium">
                    View Details →
                  </span>
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Empty State */}
      {filteredSites.length === 0 && (
        <div className="text-center py-12">
          <MapPinIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No sites found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchTerm || selectedCountry
              ? 'Try adjusting your search criteria.'
              : 'Get started by adding your first storage site.'}
          </p>
          {!searchTerm && !selectedCountry && (
            <div className="mt-6">
              <button className="btn btn-primary">
                <PlusIcon className="w-5 h-5 mr-2" />
                Add Site
              </button>
            </div>
          )}
        </div>
      )}

      {/* Summary */}
      {sites && sites.length > 0 && (
        <div className="card bg-gray-50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">
                Showing {filteredSites.length} of {sites.length} sites
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {sites.filter(s => s.is_active).length} active sites
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-gray-900">
                {countries.length} Countries
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Global coverage
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sites;
