import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { Sparkles } from 'lucide-react';
import { ResearchTrace } from './ResearchTrace.js';
import { ThinkingStatus } from './ThinkingStatus.js';
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
                        <span className="bot-name">Analyez AI</span>
                    </div>

                    {!msg.isComplete && msg.researchSteps && (
                        <ResearchTrace steps={msg.researchSteps} />
                    )}

                    {msg.thinking && !msg.isComplete && !msg.content && (
                        <ThinkingStatus>{msg.thinking}</ThinkingStatus>
                    )}

                    {msg.content && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="markdown-content"
                        >
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </motion.div>
                    )}

                    {msg.isComplete && (
                        <div className="source-tag">Institutional Analysis • Verify before acting.</div>
                    )}
                </div>
            )}
        </motion.div>
    );
};
