import { motion } from 'framer-motion';
import { Send } from 'lucide-react';

interface ChatInputProps {
    query: string;
    setQuery: (q: string) => void;
    handleSubmit: (e?: React.FormEvent) => void;
    isStreaming: boolean;
    hasMessages: boolean;
}

export const ChatInput = ({ query, setQuery, handleSubmit, isStreaming, hasMessages }: ChatInputProps) => {
    return (
        <motion.div
            layout
            initial={false}
            animate={hasMessages ? "bottom" : "center"}
            variants={{
                center: { top: "50%", bottom: "auto", transform: "translateY(-50%)" },
                bottom: { top: "auto", bottom: "0", transform: "translateY(0)" }
            }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            className="input-wrapper"
        >
            <form onSubmit={handleSubmit} className="input-container">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Analyez Anything..."
                    autoFocus
                    disabled={isStreaming}
                />
                <button type="submit" className="send-button" disabled={!query.trim() || isStreaming}>
                    <Send size={24} className={isStreaming ? 'pulse' : ''} />
                </button>
            </form>
            {!hasMessages && (
                <div className="disclaimer-text">AI Generated. Not Investment Advice. Review Accuracy.</div>
            )}
        </motion.div>
    );
};
