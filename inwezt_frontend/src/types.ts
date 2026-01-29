export interface ChartData {
    base64: string;
    type: string;
    title: string;
    symbol?: string;
    insight?: string;
}

export interface ComparisonData {
    symbols: string[];
    metrics: Record<string, Record<string, number | string | null>>;
}

export interface Message {
    id: string;
    type: 'user' | 'bot';
    content: string;
    thinking?: string | undefined;
    isComplete: boolean;
    metadata?: Record<string, unknown>;
    researchSteps?: ResearchStep[];
    chart?: ChartData;
    comparison?: ComparisonData;
}

export interface ResearchStep {
    label: string;
    status: 'pending' | 'active' | 'done';
}
