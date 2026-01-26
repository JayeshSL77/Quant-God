import { useState, useCallback } from 'react';

export interface ChatEvent {
    status: 'thinking' | 'success' | 'error';
    message?: string;
    response?: string;
    intent?: string;
    data_used?: any;
    processing_time_ms?: number;
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

            if (!reader) return;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event: ChatEvent = JSON.parse(line);
                        onEvent(event);
                    } catch (e) {
                        console.error('Error parsing NDJSON line:', e);
                    }
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
