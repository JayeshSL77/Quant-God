import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { Send, Sparkles } from 'lucide-react';
import { useStreamingAPI } from './hooks/useStreamingAPI.js';
import type { ChatEvent } from './hooks/useStreamingAPI.js';

interface Message {
  id: string;
  type: 'user' | 'bot';
  content: string;
  thinking?: string;
  isComplete: boolean;
  metadata?: any;
}

export default function App() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const { streamQuery, isStreaming } = useStreamingAPI();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || isStreaming) return;

    const userQuery = query.trim();
    setQuery('');

    const messageId = Date.now().toString();
    const newUserMessage: Message = {
      id: messageId,
      type: 'user',
      content: userQuery,
      isComplete: true,
    };

    const newBotMessageId = (Date.now() + 1).toString();
    const newBotMessage: Message = {
      id: newBotMessageId,
      type: 'bot',
      content: '',
      thinking: 'Initializing analysis...',
      isComplete: false,
    };

    setMessages((prev) => [...prev, newUserMessage, newBotMessage]);

    await streamQuery(userQuery, (event: ChatEvent) => {
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.id === newBotMessageId) {
            if (event.status === 'thinking') {
              return { ...msg, thinking: event.message || 'Thinking...' };
            } else if (event.status === 'success') {
              return { ...msg, content: event.response || '', thinking: undefined, isComplete: true, metadata: event.data_used };
            } else if (event.status === 'error') {
              return { ...msg, content: event.response || 'Error occurred', thinking: undefined, isComplete: true };
            }
          }
          return msg;
        });
      });
    });
  };

  return (
    <div className="main-container">
      {/* Header / Intro */}
      <AnimatePresence>
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="intro-section"
          >
            <h1 className="title">Introducing Inwezt</h1>
            <p className="subtitle">AI Powered Investing Co-Pilot for Mass-Affluent Indian Investors</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chat History */}
      <div className="chat-history">
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, scale: 0.98, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className={`message-bubble ${msg.type}`}
          >
            {msg.type === 'user' ? (
              <div className="message-content user-text">{msg.content}</div>
            ) : (
              <div className="bot-response">
                {msg.thinking && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    key={msg.thinking}
                    className="thinking-container"
                  >
                    <Sparkles className="thinking-icon spinning vivid-blue" size={16} />
                    <span className="thinking-text">{msg.thinking}</span>
                  </motion.div>
                )}
                {msg.content && (
                  <div className="markdown-content">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                )}
                {msg.isComplete && <div className="source-tag">AI Generated. Not Investment Advice.</div>}
              </div>
            )}
          </motion.div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Section */}
      <div className="input-wrapper">
        <form onSubmit={handleSubmit} className="input-container">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Inwezt Anything..."
            autoFocus
            disabled={isStreaming}
          />
          <button type="submit" className="send-button" disabled={!query.trim() || isStreaming}>
            <Send size={20} className={isStreaming ? 'pulse' : ''} />
          </button>
        </form>
        {messages.length === 0 && (
          <div className="disclaimer-text">AI Generated. Not Investment Advice. Review Accuracy.</div>
        )}
      </div>

      <style>{`
        .intro-section {
          text-align: center;
          margin-top: 20vh;
          margin-bottom: 2rem;
        }
        .title {
          font-size: 3.5rem;
          margin-bottom: 0.5rem;
        }
        .subtitle {
          font-size: 1.2rem;
          color: var(--text-secondary);
          margin-bottom: 2rem;
        }
        .chat-history {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          padding-bottom: 120px;
        }
        .message-bubble {
          max-width: 85%;
          padding: 1rem 1.5rem;
          border-radius: 12px;
          line-height: 1.6;
        }
        .message-bubble.user {
          align-self: flex-end;
          background: var(--input-bg);
          border: 1px solid var(--border-color);
        }
        .message-bubble.bot {
          align-self: flex-start;
          width: 100%;
          max-width: 100%;
        }
        .user-text {
          font-weight: 500;
        }
        .thinking-container {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          color: var(--primary-color);
          margin-bottom: 1rem;
        }
        .thinking-text {
          font-size: 0.9rem;
          font-weight: 500;
          letter-spacing: 0.5px;
        }
        .input-wrapper {
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          padding: 2rem;
          background: linear-gradient(transparent, var(--bg-color) 40%);
          display: flex;
          flex-direction: column;
          align-items: center;
          z-index: 100;
        }
        .input-container {
          width: 100%;
          max-width: 800px;
          background: #f5f5f5;
          border-radius: 50px;
          display: flex;
          align-items: center;
          padding: 0.5rem 1rem 0.5rem 2rem;
          box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .input-container input {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: #231f20;
          font-size: 1.1rem;
          padding: 0.8rem 0;
        }
        .send-button {
          background: transparent;
          border: none;
          color: var(--primary-color);
          cursor: pointer;
          padding: 0.5rem;
          border-radius: 50%;
          transition: transform 0.2s;
        }
        .send-button:disabled {
          color: #ccc;
          cursor: not-allowed;
        }
        .send-button:hover:not(:disabled) {
          transform: scale(1.1);
        }
        .disclaimer-text {
          margin-top: 1rem;
          font-size: 0.85rem;
          color: var(--text-secondary);
        }
        .markdown-content h1, .markdown-content h2, .markdown-content h3 {
          margin: 1.5rem 0 1rem;
          color: var(--primary-color);
        }
        .markdown-content p {
          margin-bottom: 1rem;
        }
        .markdown-content ul, .markdown-content ol {
          margin-left: 1.5rem;
          margin-bottom: 1rem;
        }
        .source-tag {
          font-size: 0.75rem;
          color: var(--text-secondary);
          margin-top: 1rem;
          padding-top: 1rem;
          border-top: 1px solid var(--border-color);
        }
        .spinning {
          animation: spin 2s linear infinite;
        }
        .pulse {
          animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.4; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
