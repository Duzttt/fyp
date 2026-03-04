import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Save, Check, Loader2, ArrowLeft, Cpu, Sliders, AlertTriangle, Trash2 } from 'lucide-react';
import { getRagConfig, updateRagConfig, resetFaissIndex } from '../services/api';

const LOCAL_QWEN_MODELS = [
  { id: 'qwen2.5:0.5b', name: 'Qwen 2.5 0.5B (Fast)' },
  { id: 'qwen2.5:1.5b', name: 'Qwen 2.5 1.5B (Balanced)' },
  { id: 'qwen2.5:3b', name: 'Qwen 2.5 3B (Recommended)' },
  { id: 'qwen2.5:7b', name: 'Qwen 2.5 7B (Smart)' },
  { id: 'qwen2.5:14b', name: 'Qwen 2.5 14B (Powerful)' },
];

export default function ConfigPage() {
  const navigate = useNavigate();
  
  const [llmModel, setLlmModel] = useState('qwen2.5:3b');
  const [topK, setTopK] = useState(3);
  const [temperature, setTemperature] = useState(0.7);
  
  const [resetConfirm, setResetConfirm] = useState('');
  const [isResetting, setIsResetting] = useState(false);
  const [resetStatus, setResetStatus] = useState(null);
  
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const config = await getRagConfig();
      setLlmModel(config.llm_model || 'qwen2.5:3b');
      setTopK(config.top_k || 3);
      setTemperature(config.temperature || 0.7);
    } catch (error) {
      console.error('Failed to load config:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      await updateRagConfig({ llm_model: llmModel, top_k: topK, temperature });
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch {
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetIndex = async () => {
    if (resetConfirm.toLowerCase() !== 'reset') return;
    
    setIsResetting(true);
    setResetStatus(null);
    try {
      await resetFaissIndex(resetConfirm);
      setResetStatus('success');
      setResetConfirm('');
      setTimeout(() => setResetStatus(null), 3000);
    } catch {
      setResetStatus('error');
    } finally {
      setIsResetting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#020617] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#020617] text-gray-200">
      <header className="h-[56px] px-4 border-b border-gray-800/80 bg-gradient-to-br from-[#020617] to-[#111827] flex items-center">
        <button 
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Chat
        </button>
      </header>

      <main className="max-w-2xl mx-auto p-6 space-y-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-2">System Configuration</h1>
          <p className="text-gray-400">Configure your RAG settings and manage the index</p>
        </div>

        <div className="space-y-6">
          <div className="bg-[#020617] border border-gray-800 rounded-2xl p-6 space-y-6">
            <div className="flex items-center gap-2 text-indigo-400">
              <Cpu className="w-5 h-5" />
              <h2 className="text-lg font-semibold">Model Settings</h2>
            </div>

            <div className="space-y-3">
              <label className="text-[13px] font-medium text-gray-400 uppercase tracking-wider">Local Model (Ollama)</label>
              <select
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="w-full h-11 px-4 rounded-xl bg-[#020617] border border-gray-800 text-sm text-gray-200 focus:border-indigo-500/50 outline-none transition-all cursor-pointer"
              >
                {LOCAL_QWEN_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
              <p className="text-[12px] text-gray-500">
                Choose a local model running via Ollama. Larger models need more RAM.
              </p>
            </div>
          </div>

          <div className="bg-[#020617] border border-gray-800 rounded-2xl p-6 space-y-6">
            <div className="flex items-center gap-2 text-indigo-400">
              <Sliders className="w-5 h-5" />
              <h2 className="text-lg font-semibold">RAG Hyperparameters</h2>
            </div>

            <div className="space-y-5">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[13px] font-medium text-gray-400 uppercase">Top-K Retrieval</label>
                  <span className="text-[14px] font-mono text-indigo-400">{topK}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value))}
                  className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <div className="flex justify-between text-[11px] text-gray-600">
                  <span>1 (focused)</span>
                  <span>10 (diverse)</span>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[13px] font-medium text-gray-400 uppercase">Temperature</label>
                  <span className="text-[14px] font-mono text-indigo-400">{temperature.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <div className="flex justify-between text-[11px] text-gray-600">
                  <span>0 (precise)</span>
                  <span>2 (creative)</span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-[#020617] border border-gray-800 rounded-2xl p-6">
            <div className="flex items-center gap-2 text-red-400 mb-4">
              <AlertTriangle className="w-5 h-5" />
              <h2 className="text-lg font-semibold">Danger Zone</h2>
            </div>
            <p className="text-[13px] text-gray-400 mb-4">
              This will permanently delete all indexed document embeddings. You will need to re-upload your PDFs.
            </p>
            <div className="space-y-3">
              <input
                type="text"
                value={resetConfirm}
                onChange={(e) => setResetConfirm(e.target.value)}
                placeholder='Type "reset" to confirm'
                className="w-full h-10 px-4 rounded-lg bg-[#020617] border border-red-900/50 text-sm text-gray-200 placeholder:text-gray-600 focus:border-red-500/50 outline-none transition-all"
              />
              <button
                onClick={handleResetIndex}
                disabled={resetConfirm.toLowerCase() !== 'reset' || isResetting}
                className="w-full py-2.5 rounded-lg bg-red-600/20 text-red-400 text-sm font-medium border border-red-500/30 hover:bg-red-600/30 transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2 cursor-pointer"
              >
                {isResetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {isResetting ? 'Resetting...' : 'Delete All Indexed Data'}
              </button>
              {resetStatus === 'success' && (
                <p className="text-[12px] text-emerald-400 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Index has been reset successfully
                </p>
              )}
              {resetStatus === 'error' && (
                <p className="text-[12px] text-red-400">Failed to reset index. Please try again.</p>
              )}
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={isSaving}
            className={`
              w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer
              ${saveStatus === 'success' 
                ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30' 
                : 'bg-indigo-600 text-white hover:bg-indigo-500 active:scale-[0.98] border border-indigo-400/20'
              }
              disabled:opacity-50 disabled:grayscale
            `}
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : saveStatus === 'success' ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {isSaving ? 'Saving...' : saveStatus === 'success' ? 'Settings Saved' : 'Save Configuration'}
          </button>
        </div>
      </main>
    </div>
  );
}
