import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, FileText, Loader2, XCircle, MessageCircle } from 'lucide-react';
import { askQuestion } from '../services/api';

export default function QAChat() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    const userQuestion = question.trim();
    setQuestion('');
    setError(null);

    setMessages((prev) => [...prev, { role: 'user', content: userQuestion }]);
    setIsLoading(true);

    try {
      const result = await askQuestion(userQuestion);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', answer: result.answer, sources: result.sources },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full h-full flex flex-col">
      <div className="bg-surface rounded-lg border border-slate-200 flex flex-col min-h-[450px]">
        <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
          <h2 className="font-heading font-semibold text-sm text-text flex items-center gap-2">
            <Bot className="w-4 h-4 text-primary" />
            Ask Questions
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-3">
                <MessageCircle className="w-6 h-6 text-primary" />
              </div>
              <p className="font-medium text-text mb-1">No messages yet</p>
              <p className="text-sm text-muted max-w-xs">
                Upload a PDF document first, then ask questions about its content
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`
                  w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
                  ${msg.role === 'user' ? 'bg-primary text-white' : 'bg-slate-100 text-primary'}
                `}>
                  {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>
                <div className={`
                  max-w-[80%] rounded-lg p-3
                  ${msg.role === 'user' ? 'bg-primary text-white' : 'bg-slate-100 text-text'}
                `}>
                  {msg.role === 'user' ? (
                    <p className="text-sm">{msg.content}</p>
                  ) : (
                    <div>
                      <p className="text-sm whitespace-pre-wrap">{msg.answer}</p>
                      {msg.sources?.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-200">
                          <p className="text-xs font-medium text-muted mb-1 flex items-center gap-1">
                            <FileText className="w-3 h-3" />Sources
                          </p>
                          <div className="space-y-1 max-h-24 overflow-y-auto">
                            {msg.sources.map((source, sIdx) => (
                              <div key={sIdx} className="text-xs text-muted bg-white/50 rounded p-1.5 line-clamp-2">
                                {source}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {isLoading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-lg bg-slate-100 text-primary flex items-center justify-center">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-slate-100 rounded-lg px-4 py-2">
                <div className="flex items-center gap-1.5 text-sm text-muted">
                  <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></span>
                  <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                  <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-2 bg-red-50 text-red-600 rounded text-sm">
              <XCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="p-3 border-t border-slate-100">
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Type your question..."
              className="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!question.trim() || isLoading}
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1 text-sm font-medium cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
