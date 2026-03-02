import { useState } from 'react';
import { Send, Bot, User, FileText, Loader2, AlertCircle } from 'lucide-react';
import { askQuestion } from '../services/api';

export default function QAChat() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

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
        { 
          role: 'assistant', 
          answer: result.answer,
          sources: result.sources 
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-100 bg-slate-50/50">
          <h2 className="font-semibold text-text flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
            Ask Questions About Your Lecture Notes
          </h2>
        </div>

        <div className="h-96 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400">
              <Bot className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm">Upload a PDF first, then ask questions</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                  ${msg.role === 'user' ? 'bg-primary text-white' : 'bg-secondary text-white'}
                `}>
                  {msg.role === 'user' ? (
                    <User className="w-4 h-4" />
                  ) : (
                    <Bot className="w-4 h-4" />
                  )}
                </div>
                <div className={`
                  max-w-[80%] rounded-xl p-4
                  ${msg.role === 'user' 
                    ? 'bg-primary text-white' 
                    : 'bg-slate-100 text-text'
                  }
                `}>
                  {msg.role === 'user' ? (
                    <p className="text-sm">{msg.content}</p>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm whitespace-pre-wrap">{msg.answer}</p>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="pt-3 border-t border-slate-200">
                          <p className="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            Source Chunks
                          </p>
                          <div className="space-y-2">
                            {msg.sources.map((source, sIdx) => (
                              <div 
                                key={sIdx}
                                className="text-xs bg-white/50 rounded p-2 text-slate-600 line-clamp-2"
                              >
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
              <div className="w-8 h-8 rounded-full bg-secondary text-white flex items-center justify-center">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-slate-100 rounded-xl p-4">
                <div className="flex items-center gap-2 text-slate-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="p-4 border-t border-slate-100">
          <div className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your lecture notes..."
              className="flex-1 px-4 py-3 rounded-lg border border-slate-200 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all duration-200 text-sm"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!question.trim() || isLoading}
              className="px-5 py-3 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 font-medium text-sm cursor-pointer"
            >
              <Send className="w-4 h-4" />
              <span>Send</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
