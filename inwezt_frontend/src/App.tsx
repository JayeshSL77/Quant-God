import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Send } from 'lucide-react';
import { useStreamingAPI } from './hooks/useStreamingAPI.js';
import type { ChatEvent } from './hooks/useStreamingAPI.js';
import { ChatMessage } from './components/ChatMessage.js';
import { ChatInput } from './components/ChatInput.js';
import type { Message, ResearchStep } from './types.js';
import './styles/App.css';

const DEFAULT_STEPS: ResearchStep[] = [
  { label: 'Market Dynamics', status: 'pending' },
  { label: 'Deep Filings & Concalls', status: 'pending' },
  { label: 'Recent Developments', status: 'pending' },
  { label: 'Technical Indicators', status: 'pending' },
];

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
      thinking: 'Analyzing query perspective...',
      isComplete: false,
      researchSteps: [...DEFAULT_STEPS]
    };

    setMessages((prev) => [...prev, newUserMessage, newBotMessage]);

    await streamQuery(userQuery, (event: ChatEvent) => {
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.id === newBotMessageId) {
            let updatedMsg = { ...msg };

            if (event.status === 'thinking') {
              const text = event.message || '';
              updatedMsg.thinking = text;

              if (updatedMsg.researchSteps) {
                updatedMsg.researchSteps = updatedMsg.researchSteps.map(step => {
                  if (text.includes(`[✓] Processed ${step.label}`)) return { ...step, status: 'done' };
                  if (text.includes(`Queued ${step.label}`)) return { ...step, status: 'active' };
                  return step;
                });
              }
            } else if (event.status === 'success') {
              updatedMsg.content = event.response || '';
              updatedMsg.metadata = event.data_used || updatedMsg.metadata;

              if (!event.is_partial) {
                updatedMsg.isComplete = true;
                updatedMsg.thinking = undefined;
                if (updatedMsg.researchSteps) {
                  updatedMsg.researchSteps = updatedMsg.researchSteps.map(s => ({ ...s, status: 'done' }));
                }
              }
            } else if (event.status === 'error') {
              updatedMsg.content = event.response || 'Error occurred';
              updatedMsg.isComplete = true;
              updatedMsg.thinking = undefined;
            }

            return updatedMsg;
          }
          return msg;
        });
      });
    });
  };

  return (
    <div className="main-container">
      {messages.length === 0 ? (
        <div className="landing-container">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
            className="intro-section"
          >
            <h1 className="title">Introducing Analyez</h1>
            <p className="subtitle">AI Powered Investing Co-Pilot for Mass-Affluent Indian Investors</p>
          </motion.div>

          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
            onSubmit={handleSubmit}
            className="input-container"
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Analyez Anything..."
              autoFocus
              disabled={isStreaming}
            />
            <button type="submit" className="send-button" disabled={!query.trim() || isStreaming}>
              <Send size={24} />
            </button>
          </motion.form>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="disclaimer-text"
          >
            AI Generated. Not Investment Advice. Review Accuracy.
          </motion.div>
        </div>
      ) : (
        <>
          <div className="chat-history">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} msg={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          <ChatInput
            query={query}
            setQuery={setQuery}
            handleSubmit={handleSubmit}
            isStreaming={isStreaming}
            hasMessages={true}
          />
        </>
      )}
    </div>
  );
}
