import { BookOpen, Wifi, WifiOff } from 'lucide-react';
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
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
            <BookOpen className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-text">Lecture Note Q&A</h1>
            <p className="text-xs text-slate-500">AI-Powered RAG System</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isConnected ? (
            <span className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-3 py-1.5 rounded-full">
              <Wifi className="w-3.5 h-3.5" />
              <span>Connected</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 px-3 py-1.5 rounded-full">
              <WifiOff className="w-3.5 h-3.5" />
              <span>Disconnected</span>
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
