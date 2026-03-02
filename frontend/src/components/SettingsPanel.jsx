import { useState, useEffect } from 'react';
import { Settings, Save, Check, AlertCircle, Loader2 } from 'lucide-react';
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
    } catch (error) {
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
        className="fixed bottom-4 right-4 w-12 h-12 bg-primary text-white rounded-full shadow-lg hover:bg-primary/90 transition-all duration-200 flex items-center justify-center cursor-pointer z-40"
        title="Settings"
      >
        <Settings className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="bg-gradient-to-r from-primary to-secondary p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                <Settings className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-white font-bold text-lg">Settings</h2>
                <p className="text-white/80 text-xs">Configure LLM Provider</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white/80 hover:text-white text-2xl leading-none cursor-pointer"
            >
              &times;
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="p-12 flex justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : (
          <div className="p-6 space-y-5">
            <div>
              <label className="block text-sm font-medium text-text mb-2">
                LLM Provider
              </label>
              <div className="grid grid-cols-2 gap-2">
                {LLM_PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => handleProviderChange(p.id)}
                    className={`
                      p-3 rounded-lg border-2 transition-all duration-200 text-sm font-medium cursor-pointer
                      ${provider === p.id 
                        ? 'border-primary bg-primary/5 text-primary' 
                        : 'border-slate-200 hover:border-slate-300 text-slate-600'
                      }
                    `}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-2">
                Model
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all duration-200 text-sm bg-white"
              >
                {selectedProvider?.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-2">
                API Key {apiKey && <span className="text-green-500">(saved)</span>}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider === 'gemini' ? 'Enter Google AI Studio API Key' : 'Enter OpenRouter API Key'}
                className="w-full px-4 py-3 rounded-lg border border-slate-200 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all duration-200 text-sm"
              />
              <p className="text-xs text-slate-400 mt-1">
                {provider === 'gemini' 
                  ? 'Get key from https://aistudio.google.com/app/apikey' 
                  : 'Get key from https://openrouter.ai/settings'
                }
              </p>
            </div>

            {saveStatus && (
              <div className={`
                p-3 rounded-lg flex items-center gap-2 text-sm
                ${saveStatus === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}
              `}>
                {saveStatus === 'success' ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
                <span>{saveStatus === 'success' ? 'Settings saved!' : 'Failed to save settings'}</span>
              </div>
            )}

            <button
              onClick={handleSave}
              disabled={isSaving}
              className="w-full py-3 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-all duration-200 font-medium flex items-center justify-center gap-2 cursor-pointer"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>Save Settings</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
