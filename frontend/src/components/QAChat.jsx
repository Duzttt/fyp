import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, FileText, Loader2, AlertCircle, MessageCircle } from 'lucide-react';
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
    <div className="w-full h-full flex flex-col">
      <div className="flex-1 bg-white rounded-2xl shadow-card overflow-hidden flex flex-col min-h-[400px]">
        <div className="p-4 border-b border-purple-50 bg-gradient-to-r from-purple-50/50 to-white">
          <h2 className="font-heading font-semibold text-text flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            Ask About Your Notes
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <div className="w-16 h-16 bg-gradient-to-br from-primary/10 to-secondary/10 rounded-2xl flex items-center justify-center mb-4">
                <MessageCircle className="w-8 h-8 text-primary" />
              </div>
              <p className="font-heading text-lg text-text mb-2">Ready to Learn!</p>
              <p className="text-sm text-secondary max-w-xs">
                Upload a PDF first, then ask me anything about your lecture notes
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div className={`
                  w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm
                  ${msg.role === 'user' 
                    ? 'bg-gradient-to-br from-primary to-secondary text-white' 
                    : 'bg-gradient-to-br from-cta to-primary text-white'
                  }
                `}>
                  {msg.role === 'user' ? (
                    <User className="w-4 h-4" />
                  ) : (
                    <Bot className="w-4 h-4" />
                  )}
                </div>
                <div className={`
                  max-w-[80%] rounded-2xl p-4 shadow-sm
                  ${msg.role === 'user' 
                    ? 'bg-gradient-to-br from-primary to-secondary text-white' 
                    : 'bg-white border border-purple-100 text-text'
                  }
                `}>
                  {msg.role === 'user' ? (
                    <p className="text-sm leading-relaxed">{msg.content}</p>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.answer}</p>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="pt-3 border-t border-purple-100">
                          <p className="text-xs font-medium text-secondary mb-2 flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            Source References
                          </p>
                          <div className="space-y-2 max-h-32 overflow-y-auto">
                            {msg.sources.map((source, sIdx) => (
                              <div 
                                key={sIdx}
                                className="text-xs bg-purple-50/50 rounded-lg p-2 text-secondary/80 line-clamp-2"
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
            <div className="flex gap-3 animate-in fade-in">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cta to-primary text-white flex items-center justify-center shadow-sm">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-white border border-purple-100 rounded-2xl p-4 shadow-sm">
                <div className="flex items-center gap-2 text-secondary">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-100 text-red-700 rounded-xl text-sm animate-in fade-in slide-in-from-bottom-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="p-4 border-t border-purple-50 bg-white">
          <div className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question..."
              className="flex-1 px-4 py-3 rounded-xl border border-purple-100 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-all duration-200 text-sm bg-purple-50/30"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!question.trim() || isLoading}
              className="px-5 py-3 bg-gradient-to-r from-primary to-secondary text-white rounded-xl hover:shadow-lg hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 transition-all duration-200 flex items-center gap-2 font-heading font-semibold text-sm cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
