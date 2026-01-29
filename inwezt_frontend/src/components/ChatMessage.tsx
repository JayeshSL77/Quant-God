import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles } from 'lucide-react';
import { ResearchTrace } from './ResearchTrace.js';
import { ThinkingStatus } from './ThinkingStatus.js';
import { ComparisonTable } from './ComparisonTable.js';
import type { Message } from '../types.js';

interface ChatMessageProps {
    msg: Message;
}

export const ChatMessage = ({ msg }: ChatMessageProps) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
            className={`message-bubble ${msg.type}`}
        >
            {msg.type === 'user' ? (
                <div className="user-content-wrapper">
                    <div className="user-content">{msg.content}</div>
                </div>
            ) : (
                <div className="bot-content">
                    <div className="bot-header">
                        <Sparkles size={20} className="vivid-blue" />
                        <span className="bot-name">Analyze AI</span>
                    </div>

                    {msg.content && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="markdown-content"
                        >
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        </motion.div>
                    )}

                    {!msg.isComplete && msg.researchSteps && (
                        <ResearchTrace steps={msg.researchSteps} />
                    )}

                    {!msg.isComplete && msg.thinking && !msg.content && (
                        <ThinkingStatus>{msg.thinking}</ThinkingStatus>
                    )}

                    {msg.chart && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className="chart-container"
                            style={{
                                marginTop: '1rem',
                                marginBottom: '1.5rem',
                                borderRadius: '12px',
                                overflow: 'hidden',
                                border: '1px solid rgba(255,255,255,0.08)',
                                background: '#111'
                            }}
                        >
                            <img
                                src={`data:image/png;base64,${msg.chart.base64}`}
                                alt={msg.chart.title}
                                style={{ width: '100%', height: 'auto', display: 'block' }}
                            />
                            {msg.chart.insight && (
                                <div className="chart-insight" style={{
                                    padding: '1rem',
                                    fontSize: '0.9rem',
                                    color: '#cbd5e1',
                                    background: 'rgba(255,255,255,0.02)',
                                    borderTop: '1px solid rgba(255,255,255,0.05)',
                                    display: 'flex',
                                    alignItems: 'start',
                                    gap: '8px'
                                }}>
                                    <Sparkles size={16} className="vivid-blue" style={{ marginTop: '3px', flexShrink: 0 }} />
                                    <span>{msg.chart.insight}</span>
                                </div>
                            )}
                        </motion.div>
                    )}

                    {msg.comparison && (
                        <ComparisonTable data={msg.comparison} />
                    )}

                    {msg.isComplete && (
                        <div className="source-tag">Institutional Analysis • Verify before acting.</div>
                    )}
                </div>
            )}
        </motion.div>
    );
};
