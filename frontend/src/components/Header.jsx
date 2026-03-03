import { BookOpen, Wifi, WifiOff, Settings, Share2, BarChart3, Plus } from 'lucide-react';
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
    <header className="h-[56px] px-4 sm:px-5 flex items-center justify-between border-b border-gray-800/80 bg-gradient-to-br from-[#020617] to-[#111827]">
      <div className="flex items-center gap-3">
        <div className="w-[26px] h-[26px] rounded-[10px] bg-[radial-gradient(circle_at_30%_20%,#a855f7,#6366f1)] flex items-center justify-center shadow-[0_0_0_1px_rgba(129,140,248,0.35)]">
          <span className="w-3 h-3 rounded-[4px] bg-[#0f172a]/95"></span>
        </div>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-sm font-semibold text-gray-200">Untitled notebook</h1>
          <div className="flex items-center gap-2">
            <p className="text-[11px] text-[#9ca3af]">0 sources</p>
            {isConnected ? (
              <span className="flex items-center gap-1 text-[10px] text-green-500">
                <Wifi className="w-2.5 h-2.5" />
                Live
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[10px] text-red-500">
                <WifiOff className="w-2.5 h-2.5" />
                Offline
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="hidden md:flex items-center gap-2">
        <button className="h-8 px-3.5 rounded-full bg-gradient-to-br from-[#6366f1] to-[#a855f7] border border-indigo-400/90 text-white text-xs font-medium flex items-center gap-1.5 hover:opacity-90 transition-opacity">
          <Plus className="w-3.5 h-3.5" />
          Create notebook
        </button>
        <button className="h-8 px-3.5 rounded-full bg-[radial-gradient(circle_at_top_left,#020617,#111827)] border border-gray-700/90 text-gray-200 text-xs font-medium hover:bg-gray-800 transition-colors flex items-center gap-1.5">
          <BarChart3 className="w-3.5 h-3.5" />
          Analytics
        </button>
        <button className="h-8 px-3.5 rounded-full bg-[radial-gradient(circle_at_top_left,#020617,#111827)] border border-gray-700/90 text-gray-200 text-xs font-medium hover:bg-gray-800 transition-colors flex items-center gap-1.5">
          <Share2 className="w-3.5 h-3.5" />
          Share
        </button>
      </div>

      <div className="flex items-center gap-2.5">
        <button className="w-[26px] h-[26px] rounded-full border border-gray-700/90 bg-[#0f172a]/95 text-[#9ca3af] flex items-center justify-center hover:text-white transition-colors">
          <Settings className="w-3.5 h-3.5" />
        </button>
        <div className="w-7 h-7 rounded-full border-2 border-[#4ade80] bg-gradient-to-br from-[#06b6d4] to-[#a855f7] cursor-pointer"></div>
      </div>
    </header>
  );
}
