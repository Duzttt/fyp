import { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  CheckSquare,
  Headphones,
  Play,
  Sparkles,
  Square,
  Plus,
  Search,
  Globe,
  Zap,
  Layout,
  GraduationCap,
  Table as TableIcon,
} from 'lucide-react';
import Header from './components/Header';
import PDFUpload from './components/PDFUpload';
import QAChat from './components/QAChat';
import SettingsPanel from './components/SettingsPanel';
import { generatePodcast, listFiles, summarizeDoc } from './services/api';

function App() {
  const [files, setFiles] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [focusedFile, setFocusedFile] = useState(null);
  const [summary, setSummary] = useState(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [podcastUrl, setPodcastUrl] = useState(null);
  const [isGeneratingPodcast, setIsGeneratingPodcast] = useState(false);

  const hasDocument = files.length > 0;

  const refreshFiles = async () => {
    try {
      const payload = await listFiles();
      const availableFiles = Array.isArray(payload.files) ? payload.files : [];
      setFiles(availableFiles);
      setSelectedSources((prev) =>
        prev.filter((name) => availableFiles.some((file) => file.name === name))
      );
      setFocusedFile((prev) => {
        if (prev && availableFiles.some((file) => file.name === prev)) {
          return prev;
        }
        return availableFiles.length > 0 ? availableFiles[0].name : null;
      });
    } catch (error) {
      console.error('Failed to fetch files:', error);
    }
  };

  useEffect(() => {
    refreshFiles();
    const timer = setInterval(refreshFiles, 10000);
    return () => clearInterval(timer);
  }, []);

  const runAutoSummary = async (filename) => {
    if (!filename) {
      return;
    }
    setFocusedFile(filename);
    setSummary(null);
    setIsSummarizing(true);
    try {
      const result = await summarizeDoc(filename);
      setSummary(result.summary || '');
    } catch (error) {
      console.error('Summary failed:', error);
      setSummary('自动摘要失败，请稍后重试。');
    } finally {
      setIsSummarizing(false);
    }
  };

  const handleUploadAccepted = async (result) => {
    await refreshFiles();
    if (result?.filename) {
      setFocusedFile(result.filename);
      setSelectedSources((prev) =>
        prev.includes(result.filename) ? prev : [...prev, result.filename]
      );
    }
  };

  const handleUploadSuccess = async (result) => {
    await refreshFiles();
    if (result?.filename) {
      setFocusedFile(result.filename);
      setSelectedSources((prev) =>
        prev.includes(result.filename) ? prev : [...prev, result.filename]
      );
      await runAutoSummary(result.filename);
    }
  };

  const toggleSource = (filename) => {
    setSelectedSources((prev) =>
      prev.includes(filename)
        ? prev.filter((item) => item !== filename)
        : [...prev, filename]
    );
  };

  const selectAllSources = () => {
    setSelectedSources(files.map((file) => file.name));
  };

  const clearSelectedSources = () => {
    setSelectedSources([]);
  };

  const selectedCount = selectedSources.length;
  const focusedDisplayName = useMemo(() => {
    if (!focusedFile) {
      return null;
    }
    const parts = focusedFile.split('_');
    return parts.length > 1 ? parts.slice(1).join('_') : focusedFile;
  }, [focusedFile]);

  const handleGeneratePodcast = async () => {
    if (!focusedFile) {
      return;
    }
    setIsGeneratingPodcast(true);
    try {
      const result = await generatePodcast(focusedFile);
      setPodcastUrl(result.audio_url || null);
    } catch (error) {
      console.error('Podcast generation failed:', error);
    } finally {
      setIsGeneratingPodcast(false);
    }
  };

  return (
    <div className="w-full h-screen bg-[#020617] flex flex-col overflow-hidden">
      {/* 顶栏 */}
      <Header />

      {/* 主体区域：左中右三栏 */}
      <main className="flex-1 grid grid-cols-1 md:grid-cols-[260px_1fr_270px] gap-2 p-2 bg-[radial-gradient(circle_at_top,#020617_0,#020617_45%,#000_90%)] overflow-hidden">
        
        {/* 左侧 Sources 栏 */}
        <aside className="bg-[#020617] rounded-[14px] border border-[#1f2937] flex flex-col overflow-hidden">
          <div className="p-3 border-b border-gray-800/90 flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-gray-200">Sources</span>
              <span className="text-[11px] text-[#9ca3af]">Add PDFs, links, notes…</span>
            </div>
            <PDFUpload
              onUploadAccepted={handleUploadAccepted}
              onUploadSuccess={handleUploadSuccess}
            />
          </div>
          
          <div className="p-3 flex flex-col gap-2 overflow-y-auto">
            <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-full bg-[#020617] border border-gray-800/80">
              <Search className="w-3.5 h-3.5 text-[#9ca3af]" />
              <input 
                placeholder="Search sources" 
                className="flex-1 bg-transparent border-none outline-none text-xs text-gray-200 placeholder:text-gray-500"
              />
            </div>
            
            <div className="flex gap-1.5 flex-wrap">
              <div className="px-2 py-0.5 rounded-full bg-[#1f2937] border border-gray-700/90 text-[11px] text-[#9ca3af] flex items-center gap-1">
                <Globe className="w-3 h-3" />
                <span>Web</span>
              </div>
              <div className="px-2 py-0.5 rounded-full bg-[#1f2937] border border-gray-700/90 text-[11px] text-[#9ca3af] flex items-center gap-1">
                <Zap className="w-3 h-3" />
                <span>Research</span>
              </div>
            </div>

            <div className="mt-2 space-y-2">
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
                  Documents ({files.length})
                </span>
                <div className="flex items-center gap-2">
                  <button onClick={selectAllSources} className="text-[10px] text-indigo-400 hover:text-indigo-300">All</button>
                  <button onClick={clearSelectedSources} className="text-[10px] text-gray-500 hover:text-gray-400">Clear</button>
                </div>
              </div>

              {!hasDocument ? (
                <div className="p-2 border border-dashed border-gray-800 rounded-xl bg-gray-900/40 text-[11px] text-[#9ca3af] text-center">
                  Saved sources will appear here. Click “+” to upload PDFs.
                </div>
              ) : (
                files.map((file) => {
                  const checked = selectedSources.includes(file.name);
                  const label = file.name.split('_').slice(1).join('_') || file.name;
                  return (
                    <div
                      key={file.name}
                      onClick={() => toggleSource(file.name)}
                      className={`group relative p-2.5 rounded-xl border transition-all cursor-pointer ${
                        focusedFile === file.name
                          ? 'border-indigo-500/50 bg-indigo-500/5'
                          : 'border-gray-800 bg-[#020617] hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                          checked ? 'bg-indigo-600 border-indigo-600' : 'border-gray-600 group-hover:border-gray-500'
                        }`}>
                          {checked && <CheckSquare className="w-3 h-3 text-white" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[12px] font-medium text-gray-200 truncate">{label}</p>
                          <p className="text-[10px] text-gray-500">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </aside>

        {/* 中间 Chat 区 */}
        <section className="bg-[#020617] rounded-[14px] border border-[#1f2937] flex flex-col overflow-hidden relative">
          <QAChat selectedSources={selectedSources} />
        </section>

        {/* 右侧 Studio 栏 */}
        <aside className="bg-[#020617] rounded-[14px] border border-[#1f2937] flex flex-col overflow-hidden">
          <div className="p-3 border-b border-gray-800/90">
            <span className="text-xs font-semibold text-gray-200">Studio</span>
          </div>
          
          <div className="p-3 flex flex-col gap-3 overflow-y-auto">
            <div className="grid grid-cols-2 gap-2">
              <div 
                onClick={handleGeneratePodcast}
                className={`p-2.5 rounded-xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                  isGeneratingPodcast ? 'border-indigo-500/50 bg-indigo-500/10' : 'border-gray-800 bg-[#020617] hover:border-gray-700'
                }`}
              >
                <div className="w-7 h-7 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                  <Headphones className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-gray-200">Audio Overview</p>
                  <p className="text-[9px] text-gray-500 leading-tight">Generate spoken summary</p>
                </div>
              </div>

              <div className="p-2.5 rounded-xl border border-gray-800 bg-[#020617] hover:border-gray-700 transition-all cursor-pointer flex flex-col gap-1.5 opacity-60">
                <div className="w-7 h-7 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400">
                  <Layout className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-gray-200">Slide Deck</p>
                  <p className="text-[9px] text-gray-500 leading-tight">Turn notes into slides</p>
                </div>
              </div>

              <div className="p-2.5 rounded-xl border border-gray-800 bg-[#020617] hover:border-gray-700 transition-all cursor-pointer flex flex-col gap-1.5 opacity-60">
                <div className="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                  <GraduationCap className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-gray-200">Study Guide</p>
                  <p className="text-[9px] text-gray-500 leading-tight">Key concepts & Qs</p>
                </div>
              </div>

              <div className="p-2.5 rounded-xl border border-gray-800 bg-[#020617] hover:border-gray-700 transition-all cursor-pointer flex flex-col gap-1.5 opacity-60">
                <div className="w-7 h-7 rounded-lg bg-orange-500/10 flex items-center justify-center text-orange-400">
                  <TableIcon className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-gray-200">Data Table</p>
                  <p className="text-[9px] text-gray-500 leading-tight">Structure info</p>
                </div>
              </div>
            </div>

            {podcastUrl && (
              <div className="mt-2 p-2.5 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
                <p className="text-[10px] font-medium text-indigo-400 mb-2 flex items-center gap-1.5">
                  <Play className="w-3 h-3" />
                  Generated Audio
                </p>
                <audio src={podcastUrl} controls className="w-full h-8" />
              </div>
            )}

            <div className="mt-2 space-y-3">
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3 h-3 text-indigo-400" />
                  Auto Summary
                </span>
                <span className="text-[10px] text-gray-500 truncate max-w-[120px]">
                  {focusedDisplayName || 'None'}
                </span>
              </div>
              
              <div className="p-3 rounded-xl border border-gray-800 bg-gray-900/30 min-h-[100px]">
                {isSummarizing ? (
                  <div className="space-y-2 animate-pulse">
                    <div className="h-2.5 bg-gray-800 rounded w-4/5" />
                    <div className="h-2.5 bg-gray-800 rounded w-full" />
                    <div className="h-2.5 bg-gray-800 rounded w-3/4" />
                  </div>
                ) : (
                  <p className="text-[12px] text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {summary || 'Upload a PDF to see auto-generated highlights here.'}
                  </p>
                )}
              </div>
            </div>

            <div className="mt-auto p-2.5 rounded-xl border border-dashed border-gray-800 bg-gray-900/20 text-[10px] text-gray-500">
              Studio output will appear here. After adding sources, click a tool to generate overviews or study material.
            </div>
          </div>
        </aside>
      </main>

      {/* 底部设置面板 (浮动) */}
      <SettingsPanel />
    </div>
  );
}

export default App;
