export const ThinkingStatus = ({ children }: { children: React.ReactNode }) => {
    return (
        <div className="thinking-status">
            <span className="dot-pulse" />
            {children}
        </div>
    );
};
