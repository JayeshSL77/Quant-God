import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import type { ResearchStep } from '../types.js';

interface ResearchTraceProps {
    steps: ResearchStep[];
}

export const ResearchTrace = ({ steps }: ResearchTraceProps) => {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="research-trace"
        >
            {steps.map((step, idx) => (
                <div key={idx} className={`trace-item ${step.status}`}>
                    {step.status === 'done' ? (
                        <CheckCircle2 size={16} className="vivid-blue" />
                    ) : step.status === 'active' ? (
                        <Loader2 size={16} className="spinning vivid-blue" />
                    ) : (
                        <Circle size={16} className="muted-icon" />
                    )}
                    <span>{step.label}</span>
                </div>
            ))}
        </motion.div>
    );
};
