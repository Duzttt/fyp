import { useState } from 'react';
import Header from './components/Header';
import PDFUpload from './components/PDFUpload';
import QAChat from './components/QAChat';

function App() {
  const [hasDocument, setHasDocument] = useState(false);

  const handleUploadSuccess = () => {
    setHasDocument(true);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-text mb-2">
            Upload Lecture Notes & Ask Questions
          </h2>
          <p className="text-slate-500">
            Powered by Retrieval-Augmented Generation (RAG)
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="font-semibold text-text mb-4 flex items-center gap-2">
              <span className="w-7 h-7 bg-primary/10 rounded-lg flex items-center justify-center text-primary text-sm font-bold">1</span>
              Upload PDF
            </h3>
            <PDFUpload onUploadSuccess={handleUploadSuccess} />
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="font-semibold text-text mb-4 flex items-center gap-2">
              <span className="w-7 h-7 bg-secondary/20 rounded-lg flex items-center justify-center text-secondary text-sm font-bold">2</span>
              Ask Questions
            </h3>
            <QAChat />
          </div>
        </div>

        <div className="text-center text-xs text-slate-400">
          <p>Upload a PDF document first, then ask questions about its content.</p>
          <p className="mt-1">The system uses semantic search to find relevant passages and generates answers using AI.</p>
        </div>
      </main>
    </div>
  );
}

export default App;
