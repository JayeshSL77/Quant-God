import { useState, useCallback } from 'react';

export interface ChatEvent {
    status: 'thinking' | 'success' | 'error';
    message?: string;
    response?: string;
    chunk?: string;
    intent?: string;
    data_used?: any;
    processing_time_ms?: number;
    is_partial?: boolean;
}

export const useStreamingAPI = () => {
    const [isStreaming, setIsStreaming] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const streamQuery = useCallback(async (query: string, onEvent: (event: ChatEvent) => void) => {
        setIsStreaming(true);
        setError(null);

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query,
                    include_tax_context: true,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            if (!reader) return;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Keep the last partial line in the buffer
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event: ChatEvent = JSON.parse(line);
                        onEvent(event);
                    } catch (e) {
                        console.error('Error parsing NDJSON line:', e, 'Line:', line);
                    }
                }
            }

            // Parse any remaining content in the buffer
            if (buffer.trim()) {
                try {
                    const event: ChatEvent = JSON.parse(buffer);
                    onEvent(event);
                } catch (e) {
                    console.error('Error parsing final NDJSON buffer:', e, 'Buffer:', buffer);
                }
            }
        } catch (err: any) {
            setError(err.message || 'Failed to connect to backend');
            onEvent({ status: 'error', response: err.message || 'Connection failed' });
        } finally {
            setIsStreaming(false);
        }
    }, []);

    return { streamQuery, isStreaming, error };
};
