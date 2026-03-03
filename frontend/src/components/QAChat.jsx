import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  FileText,
  MessageCircle,
  Send,
  User,
  X,
  XCircle,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { askQuestion } from '../services/api';

const CHAT_STORAGE_KEY = 'lecture_qa_chat_history';

function createMessageId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random()}`;
}

function loadPersistedMessages() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normalizeSnippets(message) {
  if (Array.isArray(message.sourceSnippets) && message.sourceSnippets.length > 0) {
    return message.sourceSnippets;
  }
  if (Array.isArray(message.sources)) {
    return message.sources.map((item) => {
      if (typeof item === 'string') return { source: item, page: null, text: '' };
      if (item && typeof item === 'object') {
        return {
          source: item.source || 'unknown',
          page: item.page ?? null,
          text: item.text || '',
          distance: item.distance,
        };
      }
      return { source: 'unknown', page: null, text: '' };
    });
  }
  return [];
}

export default function QAChat({ selectedSources = [] }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState(() => loadPersistedMessages());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeSnippet, setActiveSnippet] = useState(null);
  const messagesEndRef = useRef(null);

  const selectedCount = useMemo(() => selectedSources.length, [selectedSources]);

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    } catch {}
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!question.trim() || isLoading) return;

    const userQuestion = question.trim();
    setQuestion('');
    setError(null);

    const pendingId = createMessageId();
    setMessages((prev) => [
      ...prev,
      { id: createMessageId(), role: 'user', content: userQuestion },
      {
        id: pendingId,
        role: 'assistant',
        answer: '',
        isPending: true,
        sources: [],
        sourceSnippets: [],
      },
    ]);
    setIsLoading(true);

    try {
      const result = await askQuestion(
        userQuestion,
        selectedSources.length > 0 ? selectedSources : null
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                ...m,
                answer: result.answer,
                sources: result.sources || [],
                sourceSnippets: result.source_snippets || [],
                isPending: false,
              }
            : m
        )
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? { ...m, answer: 'Failed to get answer. Please try again.', isPending: false }
            : m
        )
      );
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#020617]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800/90 flex items-center justify-between">
        <div className="flex flex-col">
          <span className="text-xs font-semibold text-gray-200">Chat</span>
          <span className="text-[11px] text-[#9ca3af]">Ask questions about your notebook</span>
        </div>
        <div className="flex items-center gap-2">
          {selectedCount > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
              {selectedCount} sources selected
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full max-w-[260px] mx-auto text-center animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="w-[40px] h-[40px] rounded-[16px] bg-[radial-gradient(circle_at_20%_0,#a855f7,#22c55e)] flex items-center justify-center text-gray-950 text-xl mb-4 shadow-lg">
              💬
            </div>
            <h3 className="text-sm font-semibold text-gray-100 mb-1.5">Untitled notebook</h3>
            <p className="text-[12px] text-[#9ca3af] leading-relaxed">
              Start chatting about your sources. Add PDFs or links on the left to get more grounded answers.
            </p>
          </div>
        ) : (
          messages.map((message) => {
            const isUser = message.role === 'user';
            const snippets = normalizeSnippets(message);
            
            return (
              <div key={message.id} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} gap-2`}>
                <div className={`flex gap-3 max-w-[90%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                  <div className={`w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center ${
                    isUser ? 'bg-indigo-600/20 text-indigo-400' : 'bg-emerald-600/20 text-emerald-400'
                  }`}>
                    {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>
                  <div className={`p-3 rounded-2xl text-[13px] leading-relaxed shadow-sm ${
                    isUser 
                      ? 'bg-indigo-600 text-white rounded-tr-none' 
                      : 'bg-gray-800/80 text-gray-100 rounded-tl-none border border-gray-700/50'
                  }`}>
                    {message.isPending ? (
                      <div className="flex items-center gap-2 text-[#9ca3af]">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Thinking...</span>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{isUser ? message.content : message.answer}</div>
                    )}
                  </div>
                </div>

                {!isUser && !message.isPending && snippets.length > 0 && (
                  <div className="ml-10 flex flex-wrap gap-1.5">
                    {snippets.map((snippet, i) => (
                      <button
                        key={i}
                        onClick={() => setActiveSnippet(snippet)}
                        className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#1f2937] border border-gray-700/50 text-[10px] text-[#9ca3af] hover:border-indigo-500/50 hover:text-gray-200 transition-all"
                      >
                        <FileText className="w-2.5 h-2.5" />
                        <span className="truncate max-w-[100px]">{snippet.source}</span>
                        {snippet.page && <span>· p.{snippet.page}</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-gray-800/90 bg-[#020617]/80 backdrop-blur-md">
        <div className="relative flex items-center">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Start typing..."
            disabled={isLoading}
            className="w-full h-10 pl-4 pr-12 rounded-full bg-[#020617] border border-gray-800 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 text-[13px] text-gray-200 placeholder:text-gray-500 outline-none transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!question.trim() || isLoading}
            className="absolute right-1.5 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white hover:opacity-90 transition-all disabled:opacity-30 disabled:grayscale"
          >
            {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          </button>
        </div>
      </form>

      {/* Snippet Modal */}
      {activeSnippet && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-xl bg-[#020617] border border-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-3 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-200">
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
                <span className="truncate max-w-[300px]">{activeSnippet.source}</span>
                {activeSnippet.page && <span className="text-[#9ca3af]">· Page {activeSnippet.page}</span>}
              </div>
              <button onClick={() => setActiveSnippet(null)} className="p-1 text-gray-500 hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              <p className="text-[13px] text-gray-300 leading-relaxed whitespace-pre-wrap">
                {activeSnippet.text || 'No text content available for this snippet.'}
              </p>
            </div>
            <div className="p-3 bg-gray-900/50 border-t border-gray-800 flex justify-between items-center">
              <span className="text-[10px] text-gray-500">
                {activeSnippet.distance !== undefined && `Relevance: ${activeSnippet.distance.toFixed(4)}`}
              </span>
              <button
                onClick={() => setActiveSnippet(null)}
                className="px-3 py-1 text-[11px] font-medium text-indigo-400 hover:text-indigo-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
