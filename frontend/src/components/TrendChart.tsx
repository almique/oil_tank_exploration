import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { format, subDays } from 'date-fns';

interface Site {
  site: {
    id: number;
    name: string;
    country: string;
  };
  latest_aggregate: {
    total_volume_bbl: number;
    average_fill_fraction: number;
    trend_direction: string;
  } | null;
  volume_change_7d_pct: number | null;
}

interface TrendChartProps {
  sites: Site[];
}

const TrendChart: React.FC<TrendChartProps> = ({ sites }) => {
  const chartData = useMemo(() => {
    // Generate mock historical data for demonstration
    // In a real app, this would come from the API
    const days = 30;
    const data = [];
    
    for (let i = days; i >= 0; i--) {
      const date = subDays(new Date(), i);
      
      // Calculate total volume for this date (mock data)
      const totalVolume = sites.reduce((sum, site) => {
        if (!site.latest_aggregate?.total_volume_bbl) return sum;
        
        // Add some random variation to simulate historical data
        const variation = (Math.random() - 0.5) * 0.1; // ±5% variation
        const baseVolume = site.latest_aggregate.total_volume_bbl;
        const historicalVolume = baseVolume * (1 + variation * (i / days));
        
        return sum + historicalVolume;
      }, 0);
      
      data.push({
        date: format(date, 'MMM dd'),
        fullDate: date,
        totalVolume: totalVolume / 1000000, // Convert to millions
        activeSites: sites.filter(s => s.latest_aggregate).length,
      });
    }
    
    return data;
  }, [sites]);

  const formatTooltipValue = (value: number, name: string) => {
    if (name === 'totalVolume') {
      return [`${value.toFixed(1)}M bbl`, 'Total Volume'];
    }
    if (name === 'activeSites') {
      return [value, 'Active Sites'];
    }
    return [value, name];
  };

  const formatYAxisTick = (value: number) => {
    return `${value.toFixed(0)}M`;
  };

  if (!sites.length || !sites.some(s => s.latest_aggregate)) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        <p>No data available</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart
        data={chartData}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="date"
          stroke="#6b7280"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="#6b7280"
          fontSize={12}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatYAxisTick}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          }}
          formatter={formatTooltipValue}
          labelFormatter={(label, payload) => {
            if (payload && payload[0]) {
              return format(payload[0].payload.fullDate, 'MMM dd, yyyy');
            }
            return label;
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="totalVolume"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, stroke: '#3b82f6', strokeWidth: 2, fill: '#fff' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default TrendChart;
