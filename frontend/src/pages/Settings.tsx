import React from 'react';

const Settings: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-gray-600">
          Configure your oil tank monitoring system
        </p>
      </div>
      
      <div className="card">
        <div className="text-center py-12">
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Settings Panel Coming Soon
          </h3>
          <p className="text-gray-600">
            API configuration, alert settings, and system preferences will be available here.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Settings;
