import React from 'react';
import { I18nContext } from '../../i18n/context.js';

class AppErrorBoundary extends React.Component {
  static contextType = I18nContext;
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
    const t = this.context.t;
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
          <h1 style={{ color: 'var(--rd)', marginBottom: '16px' }}>{t('components.error_title')}</h1>
          <p style={{ color: 'var(--tx2)', marginBottom: '24px' }}>
            {t('components.error_body_short')}
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
            {t('components.reload_app')}
          </button>
          {import.meta.env.DEV && (
            <details style={{ whiteSpace: 'pre-wrap', marginTop: '24px', textAlign: 'left', maxWidth: '800px', width: '100%' }}>
              <summary>{t('components.error_details')}</summary>
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
