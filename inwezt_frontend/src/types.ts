export interface Message {
    id: string;
    type: 'user' | 'bot';
    content: string;
    thinking?: string | undefined;
    isComplete: boolean;
    metadata?: Record<string, unknown>;
    researchSteps?: ResearchStep[];
}

export interface ResearchStep {
    label: string;
    status: 'pending' | 'active' | 'done';
}
