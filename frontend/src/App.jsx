import { useState } from 'react';
import { BookOpen, Sparkles, UploadCloud } from 'lucide-react';
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
    <div className="min-h-screen bg-background text-text flex">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-72 bg-slate-900/80 border-r border-slate-800 flex-col justify-between px-6 py-8">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-heading text-sm tracking-[0.18em] uppercase text-muted">
                Lunaris
              </p>
              <p className="font-heading font-semibold text-lg text-white">
                Lecture Q&A
              </p>
            </div>
          </div>

          <p className="text-sm text-muted">
            Upload lecture PDFs and ask follow-up questions with answers grounded
            in your notes.
          </p>

          <div className="mt-6 space-y-3">
            <div className="text-xs uppercase tracking-[0.2em] text-muted">
              Session
            </div>
            <div className="rounded-xl bg-slate-800/80 border border-slate-700 px-4 py-3 space-y-1">
              <p className="text-xs text-muted">Document status</p>
              <p className="text-sm font-medium text-white flex items-center gap-2">
                <span
                  className={`inline-flex h-2 w-2 rounded-full ${
                    hasDocument ? 'bg-emerald-400' : 'bg-slate-500'
                  }`}
                />
                {hasDocument ? 'Lecture loaded' : 'Waiting for upload'}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted">
          <Sparkles className="w-4 h-4" />
          <span>RAG-powered answers</span>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col">
        <Header />

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
          {/* Page header */}
          <section className="mb-8 space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-[0.2em] uppercase text-muted">
                  Dashboard
                </p>
                <h2 className="font-heading text-2xl sm:text-3xl font-semibold text-text">
                  AI Lecture Q&amp;A
                </h2>
                <p className="text-sm text-muted max-w-xl">
                  Ask natural language questions about your lectures. Answers are
                  synthesized and grounded in retrieved chunks from your PDFs.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <div className="relative flex-1 min-w-[220px]">
                  <input
                    type="search"
                    placeholder="Search within current lecture..."
                    className="w-full rounded-full border border-slate-700 bg-slate-900/60 px-4 py-2.5 pr-10 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
                  />
                  <UploadCloud className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-slate-500" />
                </div>
                <button
                  type="button"
                  className="inline-flex items-center justify-center rounded-full px-4 py-2.5 bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors cursor-pointer"
                >
                  New question
                </button>
              </div>
            </div>
          </section>

          {/* Main layout */}
          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] items-start">
            <div className="space-y-6">
              <div className="bg-surface/80 border border-slate-800 rounded-2xl p-5">
                <h3 className="font-heading font-medium text-sm text-slate-100 mb-3 flex items-center gap-2">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-[10px] text-primary">
                    1
                  </span>
                  Upload lecture notes
                </h3>
                <PDFUpload onUploadSuccess={handleUploadSuccess} />
              </div>

              <QAChat />
            </div>

            <div className="bg-surface/80 border border-slate-800 rounded-2xl p-5 space-y-4">
              <h3 className="font-heading font-medium text-sm text-slate-100 flex items-center gap-2">
                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-[10px]">
                  i
                </span>
                Answer context
              </h3>
              <p className="text-sm text-muted">
                After you ask a question, retrieved chunks from your PDFs are used
                to ground the answer. You can inspect sources in the chat panel
                under each response.
              </p>
              <ul className="space-y-2 text-xs text-slate-400">
                <li>• Upload a single PDF per session for best results.</li>
                <li>• Ask follow-up questions to stay in context.</li>
                <li>• Look for the “Sources” section under each answer.</li>
              </ul>
            </div>
          </section>
        </main>

        <SettingsPanel />
      </div>
    </div>
  );
}

export default App;
