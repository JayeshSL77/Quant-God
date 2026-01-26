import React, { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="main-container" style={{ justifyContent: 'center', alignItems: 'center', height: '100vh', textAlign: 'center' }}>
                    <h1 className="title" style={{ fontSize: '2.5rem' }}>Something went wrong</h1>
                    <p className="subtitle" style={{ marginBottom: '2rem' }}>
                        We encountered an unexpected error. Please try refreshing the page.
                    </p>
                    <button
                        onClick={() => window.location.reload()}
                        className="user-content"
                        style={{ border: 'none', cursor: 'pointer', background: 'var(--vivid-blue)' }}
                    >
                        Refresh Page
                    </button>
                    {import.meta.env.DEV && (
                        <pre style={{ marginTop: '2rem', textAlign: 'left', background: '#333', padding: '1rem', borderRadius: '8px', maxWidth: '80%', overflow: 'auto' }}>
                            {this.state.error?.toString()}
                        </pre>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}
