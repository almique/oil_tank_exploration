import React, { useMemo } from 'react';
import Map, { Marker, Popup } from 'react-map-gl';
import { useState } from 'react';

interface Site {
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

interface GlobalMapProps {
  sites: Site[];
}

const GlobalMap: React.FC<GlobalMapProps> = ({ sites }) => {
  const [selectedSite, setSelectedSite] = useState<Site | null>(null);
  const [viewState, setViewState] = useState({
    longitude: 0,
    latitude: 20,
    zoom: 2,
  });

  const getMarkerColor = (trend: string | null | undefined) => {
    switch (trend) {
      case 'increasing':
        return '#22c55e'; // green
      case 'decreasing':
        return '#ef4444'; // red
      default:
        return '#6b7280'; // gray
    }
  };

  const getMarkerSize = (tankCount: number) => {
    if (tankCount > 50) return 12;
    if (tankCount > 20) return 10;
    if (tankCount > 10) return 8;
    return 6;
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

  return (
    <div className="w-full h-full rounded-lg overflow-hidden">
      <Map
        {...viewState}
        onMove={(evt) => setViewState(evt.viewState)}
        mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
        style={{ width: '100%', height: '100%' }}
      >
        {sites.map((site) => (
          <Marker
            key={site.site.id}
            longitude={site.site.center_lon}
            latitude={site.site.center_lat}
            anchor="center"
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              setSelectedSite(site);
            }}
          >
            <div
              className="cursor-pointer transition-transform hover:scale-110"
              style={{
                width: getMarkerSize(site.tank_count),
                height: getMarkerSize(site.tank_count),
                backgroundColor: getMarkerColor(site.trend_7d),
                borderRadius: '50%',
                border: '2px solid white',
                boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
              }}
            />
          </Marker>
        ))}

        {selectedSite && (
          <Popup
            longitude={selectedSite.site.center_lon}
            latitude={selectedSite.site.center_lat}
            anchor="bottom"
            onClose={() => setSelectedSite(null)}
            closeButton={true}
            closeOnClick={false}
            className="min-w-64"
          >
            <div className="p-3">
              <h3 className="font-semibold text-gray-900 mb-2">
                {selectedSite.site.name}
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Country:</span>
                  <span className="font-medium">{selectedSite.site.country}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Tanks:</span>
                  <span className="font-medium">
                    {selectedSite.active_tank_count}/{selectedSite.tank_count}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Volume:</span>
                  <span className="font-medium">
                    {formatVolume(selectedSite.latest_aggregate?.total_volume_bbl)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">7d Change:</span>
                  <span
                    className={`font-medium ${
                      selectedSite.volume_change_7d_pct && selectedSite.volume_change_7d_pct > 0
                        ? 'text-success-600'
                        : selectedSite.volume_change_7d_pct && selectedSite.volume_change_7d_pct < 0
                        ? 'text-danger-600'
                        : 'text-gray-600'
                    }`}
                  >
                    {formatPercentage(selectedSite.volume_change_7d_pct)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Trend:</span>
                  <span
                    className={`font-medium capitalize ${
                      selectedSite.trend_7d === 'increasing'
                        ? 'text-success-600'
                        : selectedSite.trend_7d === 'decreasing'
                        ? 'text-danger-600'
                        : 'text-gray-600'
                    }`}
                  >
                    {selectedSite.trend_7d || 'Stable'}
                  </span>
                </div>
              </div>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
};

export default GlobalMap;
