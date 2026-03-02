import { Sparkles, Wifi, WifiOff } from 'lucide-react';
import { useState, useEffect } from 'react';
import { checkHealth } from '../services/api';

export default function Header() {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const checkConnection = async () => {
      const healthy = await checkHealth();
      setIsConnected(healthy);
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-purple-100 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center shadow-card">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-lg text-text">Lecture Note Q&A</h1>
            <p className="text-xs text-secondary">AI-Powered Learning Assistant</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isConnected ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-green-600 bg-green-50 px-3 py-1.5 rounded-full">
              <Wifi className="w-3.5 h-3.5" />
              <span>Online</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs font-medium text-red-500 bg-red-50 px-3 py-1.5 rounded-full">
              <WifiOff className="w-3.5 h-3.5" />
              <span>Offline</span>
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
