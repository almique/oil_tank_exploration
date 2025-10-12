import React from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface ErrorMessageProps {
  title?: string;
  message: string;
  className?: string;
  onRetry?: () => void;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = 'Error',
  message,
  className = '',
  onRetry,
}) => {
  return (
    <div className={`rounded-md bg-danger-50 p-4 ${className}`}>
      <div className="flex">
        <div className="flex-shrink-0">
          <ExclamationTriangleIcon className="h-5 w-5 text-danger-400" />
        </div>
        <div className="ml-3">
          <h3 className="text-sm font-medium text-danger-800">{title}</h3>
          <div className="mt-2 text-sm text-danger-700">
            <p>{message}</p>
          </div>
          {onRetry && (
            <div className="mt-4">
              <button
                onClick={onRetry}
                className="btn btn-sm bg-danger-100 text-danger-800 hover:bg-danger-200"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ErrorMessage;
