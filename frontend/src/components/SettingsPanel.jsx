import { useState, useEffect } from 'react';
import { Settings, Save, Check, AlertCircle, Loader2, X, Sparkles } from 'lucide-react';
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
        className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-br from-primary to-secondary text-white rounded-2xl shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 flex items-center justify-center cursor-pointer z-40"
        title="Settings"
      >
        <Settings className="w-6 h-6" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-300">
        <div className="bg-gradient-to-r from-primary via-primary to-secondary p-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
          <div className="absolute bottom-0 left-0 w-20 h-20 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2"></div>
          
          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-white font-heading font-bold text-xl">AI Settings</h2>
                <p className="text-white/80 text-xs">Configure your LLM provider</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center text-white hover:bg-white/30 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
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
              <label className="block text-sm font-medium text-text mb-3">
                AI Provider
              </label>
              <div className="grid grid-cols-2 gap-3">
                {LLM_PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => handleProviderChange(p.id)}
                    className={`
                      p-4 rounded-xl border-2 transition-all duration-200 font-heading font-medium cursor-pointer
                      ${provider === p.id 
                        ? 'border-primary bg-primary/5 text-primary shadow-sm' 
                        : 'border-purple-100 hover:border-primary/30 text-text'
                      }
                    `}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-3">
                Model
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-purple-100 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all duration-200 text-sm bg-purple-50/30 font-medium"
              >
                {selectedProvider?.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-3">
                API Key
                {apiKey && <span className="text-green-600 ml-2 text-xs">• Saved</span>}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider === 'gemini' ? 'Enter Google AI Studio API Key' : 'Enter OpenRouter API Key'}
                className="w-full px-4 py-3 rounded-xl border border-purple-100 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all duration-200 text-sm bg-purple-50/30"
              />
              <p className="text-xs text-secondary mt-2">
                {provider === 'gemini' 
                  ? 'Get key from aistudio.google.com/app/apikey' 
                  : 'Get key from openrouter.ai/settings'
                }
              </p>
            </div>

            {saveStatus && (
              <div className={`
                p-3 rounded-xl flex items-center gap-2 text-sm font-medium
                ${saveStatus === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}
              `}>
                {saveStatus === 'success' ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
                <span>{saveStatus === 'success' ? 'Settings saved successfully!' : 'Failed to save settings'}</span>
              </div>
            )}

            <button
              onClick={handleSave}
              disabled={isSaving}
              className="w-full py-3.5 bg-gradient-to-r from-primary to-secondary text-white rounded-xl hover:shadow-lg hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-heading font-semibold flex items-center justify-center gap-2 cursor-pointer"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>Save Configuration</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
