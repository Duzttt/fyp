import { useState, useEffect } from 'react';
import { Settings, Save, Check, XCircle, Loader2, X, ShieldCheck, Key, Cpu, Sliders, AlertTriangle, Trash2 } from 'lucide-react';
import { getSettings, updateSettings, getRagConfig, updateRagConfig, resetFaissIndex } from '../services/api';

const LLM_PROVIDERS = [
  { id: 'gemini', name: 'Google Gemini', models: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'] },
  { id: 'openrouter', name: 'OpenRouter', models: ['anthropic/claude-3-haiku', 'anthropic/claude-3-sonnet', 'openai/gpt-4o-mini'] },
];

const LOCAL_QWEN_MODELS = [
  { id: 'qwen2.5:0.5b', name: 'Qwen 2.5 0.5B (Fast)' },
  { id: 'qwen2.5:1.5b', name: 'Qwen 2.5 1.5B (Balanced)' },
  { id: 'qwen2.5:3b', name: 'Qwen 2.5 3B (Recommended)' },
  { id: 'qwen2.5:7b', name: 'Qwen 2.5 7B (Smart)' },
  { id: 'qwen2.5:14b', name: 'Qwen 2.5 14B (Powerful)' },
];

const RAG_TABS = {
  MODEL: 'model',
  RAG: 'rag',
  DANGER: 'danger',
};

export default function SettingsPanel({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState(RAG_TABS.MODEL);
  
  const [provider, setProvider] = useState('gemini');
  const [model, setModel] = useState('gemini-1.5-flash');
  const [apiKey, setApiKey] = useState('');
  
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
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    setIsLoading(true);
    try {
      const [settings, ragConfig] = await Promise.all([
        getSettings(),
        getRagConfig(),
      ]);
      
      setProvider(settings.provider || 'gemini');
      setModel(settings.model || 'gemini-1.5-flash');
      
      setLlmModel(ragConfig.llm_model || 'qwen2.5:3b');
      setTopK(ragConfig.top_k || 3);
      setTemperature(ragConfig.temperature || 0.7);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider);
    const providerConfig = LLM_PROVIDERS.find(p => p.id === newProvider);
    setModel(providerConfig.models[0]);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      await Promise.all([
        updateSettings({ provider, model, api_key: apiKey || undefined }),
        updateRagConfig({ llm_model: llmModel, top_k: topK, temperature }),
      ]);
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
    } catch (error) {
      setResetStatus('error');
    } finally {
      setIsResetting(false);
    }
  };

  const selectedProvider = LLM_PROVIDERS.find(p => p.id === provider);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[100] p-4 animate-in fade-in duration-200">
      <div className="bg-[#020617] border border-gray-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between bg-gradient-to-r from-gray-900/50 to-transparent">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-gray-100">System Configuration</h2>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors cursor-pointer p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="border-b border-gray-800">
          <div className="flex px-2">
            {[
              { id: RAG_TABS.MODEL, label: 'AI Model', icon: Cpu },
              { id: RAG_TABS.RAG, label: 'RAG Settings', icon: Sliders },
              { id: RAG_TABS.DANGER, label: 'Danger Zone', icon: AlertTriangle },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2.5 px-3 text-[11px] font-medium flex items-center justify-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-gray-500 hover:text-gray-300'
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            <p className="text-xs text-gray-500">Retrieving configuration...</p>
          </div>
        ) : (
          <div className="p-5 space-y-5 max-h-[60vh] overflow-y-auto">
            {activeTab === RAG_TABS.MODEL && (
              <>
                <div className="space-y-3">
                  <label className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Provider</label>
                  <div className="grid grid-cols-2 gap-2">
                    {LLM_PROVIDERS.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => handleProviderChange(p.id)}
                        className={`
                          py-2.5 px-3 rounded-xl border text-[13px] font-medium transition-all cursor-pointer flex items-center justify-center gap-2
                          ${provider === p.id 
                            ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.1)]' 
                            : 'border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-300'
                          }
                        `}
                      >
                        {provider === p.id && <ShieldCheck className="w-3.5 h-3.5" />}
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Model Selection</label>
                  <div className="relative">
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full h-10 px-3 pr-8 rounded-xl bg-[#020617] border border-gray-800 text-[13px] text-gray-200 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 outline-none transition-all appearance-none cursor-pointer"
                    >
                      {selectedProvider?.models.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-[11px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                    <span>API Key</span>
                    {apiKey && <span className="text-emerald-500 text-[9px] flex items-center gap-1"><Check className="w-2.5 h-2.5" /> SAVED</span>}
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="••••••••••••••••"
                      className="w-full h-10 pl-9 pr-3 rounded-xl bg-[#020617] border border-gray-800 text-[13px] text-gray-200 placeholder:text-gray-700 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 outline-none transition-all"
                    />
                    <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600" />
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed italic">
                    {provider === 'gemini' 
                      ? 'Obtain from aistudio.google.com' 
                      : 'Obtain from openrouter.ai/settings'}
                  </p>
                </div>
              </>
            )}

            {activeTab === RAG_TABS.RAG && (
              <>
                <div className="space-y-3">
                  <label className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Local Model (Ollama)</label>
                  <div className="relative">
                    <select
                      value={llmModel}
                      onChange={(e) => setLlmModel(e.target.value)}
                      className="w-full h-10 px-3 pr-8 rounded-xl bg-[#020617] border border-gray-800 text-[13px] text-gray-200 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 outline-none transition-all appearance-none cursor-pointer"
                    >
                      {LOCAL_QWEN_MODELS.map((m) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-relaxed">
                    Choose a local model running via Ollama. Larger models need more RAM.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Top-K Retrieval</label>
                      <span className="text-[12px] font-mono text-indigo-400">{topK}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={topK}
                      onChange={(e) => setTopK(parseInt(e.target.value))}
                      className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    />
                    <div className="flex justify-between text-[9px] text-gray-600">
                      <span>1 (focused)</span>
                      <span>10 (diverse)</span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Temperature</label>
                      <span className="text-[12px] font-mono text-indigo-400">{temperature.toFixed(1)}</span>
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
                    <div className="flex justify-between text-[9px] text-gray-600">
                      <span>0 (precise)</span>
                      <span>2 (creative)</span>
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === RAG_TABS.DANGER && (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-red-950/30 border border-red-900/50">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                    <span className="text-[13px] font-semibold text-red-400">Wipe FAISS Index</span>
                  </div>
                  <p className="text-[11px] text-gray-400 leading-relaxed mb-3">
                    This will permanently delete all indexed document embeddings. You will need to re-upload your PDFs to restore search functionality.
                  </p>
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={resetConfirm}
                      onChange={(e) => setResetConfirm(e.target.value)}
                      placeholder='Type "reset" to confirm'
                      className="w-full h-9 px-3 rounded-lg bg-[#020617] border border-red-900/50 text-[12px] text-gray-200 placeholder:text-gray-600 focus:border-red-500/50 outline-none transition-all"
                    />
                    <button
                      onClick={handleResetIndex}
                      disabled={resetConfirm.toLowerCase() !== 'reset' || isResetting}
                      className="w-full py-2 rounded-lg bg-red-600/20 text-red-400 text-[12px] font-medium border border-red-500/30 hover:bg-red-600/30 transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2 cursor-pointer"
                    >
                      {isResetting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                      {isResetting ? 'Resetting...' : 'Delete All Indexed Data'}
                    </button>
                    {resetStatus === 'success' && (
                      <p className="text-[11px] text-emerald-400 flex items-center gap-1">
                        <Check className="w-3 h-3" /> Index has been reset successfully
                      </p>
                    )}
                    {resetStatus === 'error' && (
                      <p className="text-[11px] text-red-400">Failed to reset index. Please try again.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {!isLoading && activeTab !== RAG_TABS.DANGER && (
          <div className="p-5 border-t border-gray-800 bg-gray-900/30">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className={`
                w-full py-2.5 rounded-xl text-[13px] font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer
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
        )}
      </div>
    </div>
  );
}
