import { useState, useEffect } from 'react';
import { Settings, Save, Check, XCircle, Loader2, X, ShieldCheck, Key } from 'lucide-react';
import { getSettings, updateSettings } from '../services/api';

const LLM_PROVIDERS = [
  { id: 'gemini', name: 'Google Gemini', models: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'] },
  { id: 'openrouter', name: 'OpenRouter', models: ['anthropic/claude-3-haiku', 'anthropic/claude-3-sonnet', 'openai/gpt-4o-mini'] },
];

export default function SettingsPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [provider, setProvider] = useState('gemini');
  const [model, setModel] = useState('gemini-1.5-flash');
  const [apiKey, setApiKey] = useState('');
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
      const settings = await getSettings();
      setProvider(settings.provider || 'gemini');
      setModel(settings.model || 'gemini-1.5-flash');
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
      await updateSettings({ provider, model, api_key: apiKey || undefined });
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch {
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  const selectedProvider = LLM_PROVIDERS.find(p => p.id === provider);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-10 h-10 bg-[#1f2937] border border-gray-700/50 text-gray-400 rounded-full shadow-2xl hover:text-white hover:border-indigo-500/50 transition-all flex items-center justify-center cursor-pointer z-40 group"
        title="Settings"
      >
        <Settings className="w-4 h-4 group-hover:rotate-45 transition-transform duration-300" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[100] p-4 animate-in fade-in duration-200">
      <div className="bg-[#020617] border border-gray-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between bg-gradient-to-r from-gray-900/50 to-transparent">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-gray-100">AI Configuration</h2>
          </div>
          <button onClick={() => setIsOpen(false)} className="text-gray-500 hover:text-white transition-colors cursor-pointer p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
            <p className="text-xs text-gray-500">Retrieving configuration...</p>
          </div>
        ) : (
          <div className="p-5 space-y-6">
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

            <div className="pt-2">
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
                {isSaving ? 'Updating...' : saveStatus === 'success' ? 'Settings Saved' : 'Update Configuration'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
