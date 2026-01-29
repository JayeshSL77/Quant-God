import { motion } from 'framer-motion';
import type { ComparisonData } from '../types.js';

interface ComparisonTableProps {
    data: ComparisonData;
}

// Metric display configuration with sector context
const METRIC_CONFIG: Record<string, { label: string; format: (v: number | string | null | undefined, m?: Record<string, unknown>) => string; higherIsBetter: boolean }> = {
    pe_ratio: {
        label: 'P/E Ratio',
        format: (v, m) => {
            if (v == null) return 'N/A';
            const pe = Number(v).toFixed(1);
            const sectorPe = m?.sector_pe;
            const discount = m?.valuation_discount as number | undefined;
            if (sectorPe && discount !== undefined) {
                const arrow = discount > 0 ? '↓' : discount < 0 ? '↑' : '→';
                return `${pe}x vs ${Number(sectorPe).toFixed(1)}x ${arrow}${Math.abs(discount).toFixed(0)}%`;
            }
            return `${pe}x`;
        },
        higherIsBetter: false
    },
    valuation_status: {
        label: 'Valuation',
        format: (v) => v != null ? String(v) : 'N/A',
        higherIsBetter: false
    },
    pb_ratio: { label: 'P/B Ratio', format: (v) => v != null ? `${Number(v).toFixed(1)}x` : 'N/A', higherIsBetter: false },
    roe: { label: 'ROE', format: (v) => v != null ? `${Number(v).toFixed(1)}%` : 'N/A', higherIsBetter: true },
    net_margin: { label: 'Net Margin', format: (v) => v != null ? `${Number(v).toFixed(1)}%` : 'N/A', higherIsBetter: true },
    revenue_growth: { label: 'Rev. Growth', format: (v) => v != null ? `${Number(v).toFixed(1)}%` : 'N/A', higherIsBetter: true },
    ytd_change: { label: 'YTD Return', format: (v) => v != null ? `${Number(v) > 0 ? '+' : ''}${Number(v).toFixed(1)}%` : 'N/A', higherIsBetter: true },
    market_cap: { label: 'Market Cap', format: (v) => v != null ? `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 })}Cr` : 'N/A', higherIsBetter: true },
};

const METRICS_ORDER = ['pe_ratio', 'valuation_status', 'pb_ratio', 'roe', 'net_margin', 'revenue_growth', 'ytd_change', 'market_cap'];

export const ComparisonTable = ({ data }: ComparisonTableProps) => {
    const { symbols, metrics } = data;

    // Find winner for each metric
    const getWinner = (metricKey: string): string | null => {
        const config = METRIC_CONFIG[metricKey];
        if (!config) return null;

        let winner: string | null = null;
        let bestValue: number | null = null;

        symbols.forEach((symbol) => {
            const value = metrics[symbol]?.[metricKey];
            if (value == null) return;
            const numValue = Number(value);
            if (isNaN(numValue)) return;

            if (bestValue === null) {
                bestValue = numValue;
                winner = symbol;
            } else if (config.higherIsBetter && numValue > bestValue) {
                bestValue = numValue;
                winner = symbol;
            } else if (!config.higherIsBetter && numValue < bestValue) {
                bestValue = numValue;
                winner = symbol;
            }
        });

        return winner;
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="comparison-table-container"
            style={{
                marginTop: '1.5rem',
                marginBottom: '1rem',
                borderRadius: '12px',
                overflow: 'hidden',
                border: '1px solid rgba(255,255,255,0.08)',
                background: 'linear-gradient(180deg, rgba(17,17,17,0.95) 0%, rgba(10,10,10,0.98) 100%)',
            }}
        >
            {/* Header */}
            <div
                style={{
                    padding: '0.75rem 1rem',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    background: 'rgba(255,255,255,0.02)',
                }}
            >
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0' }}>
                    📊 Side-by-Side Comparison
                </span>
            </div>

            {/* Table */}
            <div style={{ overflowX: 'auto' }}>
                <table
                    style={{
                        width: '100%',
                        borderCollapse: 'collapse',
                        fontSize: '0.85rem',
                    }}
                >
                    <thead>
                        <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                            <th
                                style={{
                                    textAlign: 'left',
                                    padding: '0.75rem 1rem',
                                    color: '#94a3b8',
                                    fontWeight: 500,
                                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                                }}
                            >
                                Metric
                            </th>
                            {symbols.map((symbol) => (
                                <th
                                    key={symbol}
                                    style={{
                                        textAlign: 'center',
                                        padding: '0.75rem 1rem',
                                        color: '#f1f5f9',
                                        fontWeight: 600,
                                        borderBottom: '1px solid rgba(255,255,255,0.05)',
                                    }}
                                >
                                    {symbol}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {METRICS_ORDER.map((metricKey, index) => {
                            const config = METRIC_CONFIG[metricKey];
                            if (!config) return null;

                            const winner = getWinner(metricKey);

                            return (
                                <tr
                                    key={metricKey}
                                    style={{
                                        background: index % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                                    }}
                                >
                                    <td
                                        style={{
                                            padding: '0.65rem 1rem',
                                            color: '#94a3b8',
                                            borderBottom: '1px solid rgba(255,255,255,0.03)',
                                        }}
                                    >
                                        {config.label}
                                    </td>
                                    {symbols.map((symbol) => {
                                        const value = metrics[symbol]?.[metricKey];
                                        const symbolMetrics = metrics[symbol] || {};
                                        const isWinner = symbol === winner && value != null;

                                        // Special color for valuation status
                                        let cellColor = isWinner ? '#22c55e' : '#e2e8f0';
                                        if (metricKey === 'valuation_status') {
                                            if (value === 'Undervalued') cellColor = '#22c55e';
                                            else if (value === 'Premium') cellColor = '#f59e0b';
                                            else cellColor = '#94a3b8';
                                        }

                                        return (
                                            <td
                                                key={symbol}
                                                style={{
                                                    textAlign: 'center',
                                                    padding: '0.65rem 1rem',
                                                    color: cellColor,
                                                    fontWeight: isWinner || metricKey === 'valuation_status' ? 600 : 400,
                                                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                                                    background: isWinner ? 'rgba(34,197,94,0.08)' : 'transparent',
                                                }}
                                            >
                                                {config.format(value, symbolMetrics)}
                                                {isWinner && metricKey !== 'valuation_status' && (
                                                    <span style={{ marginLeft: '4px', fontSize: '0.7rem' }}>✓</span>
                                                )}
                                            </td>
                                        );
                                    })}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Footer */}
            <div
                style={{
                    padding: '0.5rem 1rem',
                    fontSize: '0.75rem',
                    color: '#64748b',
                    borderTop: '1px solid rgba(255,255,255,0.04)',
                    background: 'rgba(255,255,255,0.01)',
                }}
            >
                <span style={{ color: '#22c55e' }}>●</span> Best value highlighted per metric
            </div>
        </motion.div>
    );
};
