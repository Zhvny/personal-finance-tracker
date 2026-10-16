import React from 'react';

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // You can also log the error to an error reporting service
    console.error("Uncaught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <div style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          textAlign: 'center',
          background: 'var(--bg)',
          color: 'var(--tx)'
        }}>
          <h1 style={{ color: 'var(--rd)', marginBottom: '16px' }}>Something went wrong.</h1>
          <p style={{ color: 'var(--tx2)', marginBottom: '24px' }}>
            The application encountered an unexpected error.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '12px 24px',
              background: 'var(--cy)',
              border: 'none',
              borderRadius: '8px',
              color: 'var(--bg)',
              fontWeight: 'bold',
              cursor: 'pointer'
            }}
          >
            Reload Application
          </button>
          {import.meta.env.DEV && (
            <details style={{ whiteSpace: 'pre-wrap', marginTop: '24px', textAlign: 'left', maxWidth: '800px', width: '100%' }}>
              <summary>Error Details</summary>
              <p>{this.state.error && this.state.error.toString()}</p>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default AppErrorBoundary;
