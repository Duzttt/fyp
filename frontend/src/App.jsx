import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import Header from './components/Header';
import PDFUpload from './components/PDFUpload';
import QAChat from './components/QAChat';
import SettingsPanel from './components/SettingsPanel';

function App() {
  const [hasDocument, setHasDocument] = useState(false);

  const handleUploadSuccess = () => {
    setHasDocument(true);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 rounded-full mb-4">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-primary">AI-Powered Learning</span>
          </div>
          <h2 className="font-heading text-3xl font-bold text-text mb-3">
            Your Smart Study Assistant
          </h2>
          <p className="text-secondary max-w-lg mx-auto">
            Upload your lecture notes and ask questions. Get instant answers powered by AI.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          <div className="bg-white rounded-3xl shadow-card p-6 lg:p-8 hover:shadow-card-hover transition-shadow duration-300">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
                <span className="text-white font-heading font-bold">1</span>
              </div>
              <h3 className="font-heading font-semibold text-lg text-text">Upload Notes</h3>
            </div>
            <PDFUpload onUploadSuccess={handleUploadSuccess} />
          </div>

          <div className="bg-white rounded-3xl shadow-card p-6 lg:p-8 hover:shadow-card-hover transition-shadow duration-300">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-gradient-to-br from-cta to-primary rounded-xl flex items-center justify-center">
                <span className="text-white font-heading font-bold">2</span>
              </div>
              <h3 className="font-heading font-semibold text-lg text-text">Ask Questions</h3>
            </div>
            <QAChat />
          </div>
        </div>

        <div className="mt-10 text-center">
          <div className="inline-flex items-center gap-6 text-sm text-secondary">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span>PDF Upload</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-cta rounded-full"></div>
              <span>Semantic Search</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-primary rounded-full"></div>
              <span>AI Answers</span>
            </div>
          </div>
        </div>
      </main>

      <SettingsPanel />
    </div>
  );
}

export default App;
