import { useState } from 'react';
import { BookOpen } from 'lucide-react';
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

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary rounded-2xl mb-4">
            <BookOpen className="w-8 h-8 text-white" />
          </div>
          <h2 className="font-heading text-2xl font-semibold text-text mb-2">
            Lecture Note Q&A System
          </h2>
          <p className="text-muted max-w-md mx-auto">
            Upload your PDF lecture notes and ask questions. Get AI-powered answers instantly.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-surface rounded-lg border border-slate-200 p-6">
            <h3 className="font-heading font-semibold text-text mb-4 flex items-center gap-2">
              <span className="w-6 h-6 bg-primary/10 rounded text-primary text-xs flex items-center justify-center">1</span>
              Upload PDF
            </h3>
            <PDFUpload onUploadSuccess={handleUploadSuccess} />
          </div>

          <div className="bg-surface rounded-lg border border-slate-200 p-6">
            <h3 className="font-heading font-semibold text-text mb-4 flex items-center gap-2">
              <span className="w-6 h-6 bg-cta/10 rounded text-cta text-xs flex items-center justify-center">2</span>
              Ask Questions
            </h3>
            <QAChat />
          </div>
        </div>

        <div className="mt-8 flex justify-center gap-6 text-sm text-muted">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            PDF Upload
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-cta rounded-full"></span>
            Semantic Search
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-primary rounded-full"></span>
            AI Answers
          </span>
        </div>
      </main>

      <SettingsPanel />
    </div>
  );
}

export default App;
