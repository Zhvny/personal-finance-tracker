import React, { Component } from "react";
import { IconActivity, IconInfo, IconAlertCircle, IconTarget } from "../icons.jsx";

export const ButterflyStatus = ({ type, message, onRetry }) => {
  const icons = {
    loading: <IconActivity size={24} color="var(--cy)" className="pulse" />,
    empty: <IconInfo size={24} color="var(--tx3)" />,
    error: <IconAlertCircle size={24} color="var(--rd)" />,
    degraded: <IconTarget size={24} color="var(--yl)" />
  };

  return (
    <div style={{ 
      display: "flex", 
      flexDirection: "column", 
      alignItems: "center", 
      justifyContent: "center", 
      padding: "40px 20px", 
      gap: 16,
      background: "var(--bg3)",
      borderRadius: 16,
      border: "1px dashed var(--bdr)",
      minHeight: 200
    }}>
      <div style={{ 
        width: 48, height: 48, borderRadius: "50%", background: "var(--bg2)", 
        display: "flex", alignItems: "center", justifyContent: "center",
        border: `1px solid ${type === 'error' ? 'var(--rd)' : 'var(--bdr)'}`
      }}>
        {icons[type] || icons.empty}
      </div>
      <div style={{ 
        fontSize: 11, fontWeight: 800, color: "var(--tx2)", 
        textAlign: "center", textTransform: "uppercase", letterSpacing: 1,
        maxWidth: 200, lineHeight: 1.4
      }}>
        {message}
      </div>
      {onRetry && (
        <button 
          onClick={onRetry}
          style={{
            background: "var(--bg4)",
            border: "1px solid var(--bdr)",
            borderRadius: 8,
            padding: "6px 16px",
            fontSize: 10,
            fontWeight: 900,
            color: "var(--cy)",
            cursor: "pointer",
            marginTop: 4,
            transition: "all 0.2s ease"
          }}
          onMouseOver={e => e.target.style.background = "var(--bg2)"}
          onMouseOut={e => e.target.style.background = "var(--bg4)"}
        >
          RETRY VISUALIZATION
        </button>
      )}
    </div>
  );
};

export default class ButterflyErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, showDetails: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ButterflyComponent Crash:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, showDetails: false });
  };

  toggleDetails = () => {
    this.setState(s => ({ showDetails: !s.showDetails }));
  };

  copyError = () => {
    const errorText = this.state.error?.stack || this.state.error?.message || "Unknown error";
    navigator.clipboard.writeText(errorText).then(() => {
      alert("Error copied to clipboard");
    }).catch(err => {
      console.error("Failed to copy error:", err);
      alert("Failed to copy to clipboard. See console.");
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          background: "var(--bg2)", 
          borderRadius: 24, 
          padding: 24, 
          border: "1px solid var(--bdr)",
          display: "flex",
          flexDirection: "column",
          gap: 16
        }}>
          <ButterflyStatus 
            type="error" 
            message={this.props.message || "Graphics Engine Stalled"} 
            onRetry={this.handleRetry}
          />
          
          <div style={{ textAlign: 'center' }}>
            <button 
              onClick={this.toggleDetails}
              style={{ 
                background: "transparent", 
                border: "none", 
                fontSize: 9, 
                color: "var(--tx3)", 
                cursor: "pointer",
                textDecoration: "underline",
                textTransform: "uppercase",
                letterSpacing: 0.5
              }}
            >
              {this.state.showDetails ? "Hide technical details" : "Show technical details"}
            </button>
          </div>

          {this.state.showDetails && (
            <div style={{ 
              fontSize: 10, 
              color: 'var(--rd)', 
              padding: 16, 
              background: "var(--bg3)",
              borderRadius: 12, 
              fontFamily: "monospace", 
              opacity: 0.9,
              border: "1px solid rgba(239, 68, 68, 0.2)",
              maxHeight: 150,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              position: "relative"
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div style={{ fontWeight: 900, textTransform: "uppercase" }}>Exception trace:</div>
                <button 
                  onClick={this.copyError}
                  style={{
                    background: "var(--bg4)",
                    border: "1px solid var(--bdr)",
                    borderRadius: 4,
                    padding: "2px 6px",
                    fontSize: 8,
                    fontWeight: 900,
                    color: "var(--cy)",
                    cursor: "pointer"
                  }}
                >
                  COPY ERROR
                </button>
              </div>
              {this.state.error?.stack || this.state.error?.message || "Unknown error"}
            </div>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
