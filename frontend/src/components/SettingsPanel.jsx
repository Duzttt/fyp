import { useState, useEffect } from 'react';
import { Settings, Save, Check, XCircle, Loader2, X } from 'lucide-react';
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
        className="fixed bottom-6 right-6 w-12 h-12 bg-primary text-white rounded-lg shadow-lg hover:bg-primary/90 transition-colors flex items-center justify-center cursor-pointer z-40"
        title="Settings"
      >
        <Settings className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-surface rounded-lg shadow-xl w-full max-w-md">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="font-heading font-semibold text-lg text-text">Settings</h2>
          <button onClick={() => setIsOpen(false)} className="text-muted hover:text-text cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="p-8 flex justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : (
          <div className="p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-text mb-2">Provider</label>
              <div className="grid grid-cols-2 gap-2">
                {LLM_PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => handleProviderChange(p.id)}
                    className={`
                      py-2 px-3 rounded border text-sm font-medium transition-colors cursor-pointer
                      ${provider === p.id 
                        ? 'border-primary bg-primary text-white' 
                        : 'border-slate-200 text-text hover:border-primary'
                      }
                    `}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-2">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 rounded border border-slate-200 text-sm focus:border-primary focus:outline-none"
              >
                {selectedProvider?.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-2">
                API Key
                {apiKey && <span className="text-green-600 ml-2 text-xs">saved</span>}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter API key"
                className="w-full px-3 py-2 rounded border border-slate-200 text-sm focus:border-primary focus:outline-none"
              />
              <p className="text-xs text-muted mt-1">
                {provider === 'gemini' ? 'Get from aistudio.google.com/app/apikey' : 'Get from openrouter.ai/settings'}
              </p>
            </div>

            {saveStatus && (
              <div className={`p-2 rounded text-sm flex items-center gap-2 ${saveStatus === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                {saveStatus === 'success' ? <Check className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                <span>{saveStatus === 'success' ? 'Saved!' : 'Failed to save'}</span>
              </div>
            )}

            <button
              onClick={handleSave}
              disabled={isSaving}
              className="w-full py-2 bg-primary text-white rounded hover:bg-primary/90 disabled:opacity-50 transition-colors font-medium text-sm flex items-center justify-center gap-2 cursor-pointer"
            >
              {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
