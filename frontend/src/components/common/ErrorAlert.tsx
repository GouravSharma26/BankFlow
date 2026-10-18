import { AlertCircle, RefreshCw, Terminal } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  statusCode?: number;
  onRetry?: () => void;
  className?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'API Connection Error',
  message,
  statusCode,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`bg-rose-50 border border-rose-200 rounded-xl p-5 text-rose-900 shadow-sm ${className}`}
      role="alert"
    >
      <div className="flex items-start space-x-3">
        <div className="p-2 bg-rose-100 rounded-lg text-rose-700 flex-shrink-0 mt-0.5">
          <AlertCircle className="w-5 h-5" />
        </div>

        <div className="flex-1 space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-sm text-rose-950 flex items-center gap-2">
              {title}
              {statusCode ? (
                <span className="text-xs bg-rose-200 text-rose-800 px-1.5 py-0.5 rounded font-mono">
                  HTTP {statusCode}
                </span>
              ) : null}
            </h4>
            {onRetry && (
              <button
                onClick={onRetry}
                className="inline-flex items-center text-xs font-medium text-rose-800 bg-rose-100 hover:bg-rose-200 px-2.5 py-1.5 rounded-md transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                Retry Request
              </button>
            )}
          </div>

          <p className="text-xs text-rose-800 leading-relaxed font-sans">{message}</p>

          <div className="mt-3 pt-3 border-t border-rose-200/60 text-xs text-rose-800 bg-rose-100/60 p-3 rounded-lg flex items-start space-x-2">
            <Terminal className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-rose-900">Local Backend Startup Command:</p>
              <code className="inline-block mt-1 font-mono text-[11px] bg-white px-2 py-0.5 rounded border border-rose-200 text-slate-800">
                python -m bankflow serve --host 127.0.0.1 --port 8000
              </code>
              <p className="mt-1 text-[11px] text-rose-700">
                Alternatively, switch to <strong>Demo Mode</strong> via the top header toggle to explore synthetic preview fixtures.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
