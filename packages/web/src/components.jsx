// ─── components.jsx ──────────────────────────────────────────────────────────
// Reusable UI atoms shared across all page modules.
// High Cohesion : each component owns exactly ONE visual responsibility.
// Low Coupling  : no business logic, no API calls — pure presentational.

import { Component, useEffect, useRef, useCallback, useState, Children, cloneElement, isValidElement } from "react";
import { createPortal } from "react-dom";
import { fmt, fmtS } from "./constants.js";
import { useI18n, I18nContext } from "./i18n/context.js";
import {
  IconCheck, IconClose, IconRefresh, IconAlert,
  IconUp, IconDown, IconBarChart, IconWarning,
} from "./icons.jsx";

// ── useFocusTrap ──────────────────────────────────────────────────────────────
// WCAG 2.4.3: Traps keyboard focus within a dialog while open and restores
// it to the previously focused element on close.
const FOCUSABLE = [
  'a[href]', 'area[href]', 'input:not([disabled])', 'select:not([disabled])',
   'textarea:not([disabled])', 'button:not([disabled])', '[tabindex]:not([tabindex="-1"])',
  '[contenteditable]',
].join(',');

function useFocusTrap(containerRef) {
  const prevFocusRef = useRef(null);
  useEffect(() => {
    // Save current focus so we can restore it on unmount
    prevFocusRef.current = document.activeElement;
    // Move focus into the container (to the first focusable element, or the container itself)
    const container = containerRef.current;
    if (!container) return;
    const first = container.querySelectorAll(FOCUSABLE)[0];
    if (first) first.focus();
    else container.focus();

    const handleKeyDown = (e) => {
      if (e.key !== 'Tab') return;
      const focusable = Array.from(container.querySelectorAll(FOCUSABLE));
      if (!focusable.length) { e.preventDefault(); return; }
      const firstEl = focusable[0];
      const lastEl  = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === firstEl) { e.preventDefault(); lastEl.focus(); }
      } else {
        if (document.activeElement === lastEl)  { e.preventDefault(); firstEl.focus(); }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      // Restore focus to the element that triggered the dialog
      if (prevFocusRef.current && prevFocusRef.current.focus) {
        prevFocusRef.current.focus();
      }
    };
  }, [containerRef]);
}

// ── Error Boundary ────────────────────────────────────────────────────────────
// Catch rendering errors and show a graceful fallback instead of a white screen.
export class ErrorBoundary extends Component {
  static contextType = I18nContext;
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  componentDidCatch(error, errorInfo) { console.error("React Crash:", error, errorInfo); }
  render() {
    const t = this.context.t;
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: "center", background: "var(--bg)", height: "100vh", display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <IconAlert size={48} color="var(--rd)" style={{ margin: "0 auto 20px" }} />
          <h2 style={{ color: "var(--tx)" }}>{t("components.error_title")}</h2>
          <p style={{ color: "var(--tx2)", fontSize: 14, maxWidth: 400, margin: "0 auto 20px" }}>
            {t("components.error_body")}
          </p>
          <pre style={{ background: "var(--bg2)", padding: 12, borderRadius: 8, fontSize: 11, color: "var(--rd)", overflow: "auto", maxWidth: "100%", textAlign: "left" }}>
            {this.state.error?.toString()}
          </pre>
          <button className="btn btn-p" onClick={() => window.location.reload()} style={{ marginTop: 24, alignSelf: "center" }}>
            {t("components.reload_app")}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Offline Banner ────────────────────────────────────────────────────────────
export function OfflineBanner() {
  const { t } = useI18n();
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  useEffect(() => {
    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  if (isOnline) return null;

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 10000,
      background: "var(--rd)", color: "var(--bg2)", padding: "8px 16px",
      fontSize: 12, fontWeight: 700, textAlign: "center",
      display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
      boxShadow: "var(--sh)"
    }}>
      <IconWarning size={14} />
      {t("components.offline")}
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────
export function Toast({ msg, type, onClose }) {
  const { t } = useI18n();
  useEffect(() => {
    const tid = setTimeout(onClose, 4000);
    return () => clearTimeout(tid);
  }, [onClose]);
  return (
    <div
      className={`toast ${type === "success" ? "s" : "e"}`}
      onClick={onClose}
      role="status"
      aria-live="polite"
      title={t("components.dismiss")}
    >
      <span style={{ display:"flex", alignItems:"center" }}>
        {type === "success"
          ? <IconCheck size={14} color="var(--gr)" />
          : <IconClose size={14} color="var(--rd)" />}
      </span>
      <span style={{ flex: 1 }}>{msg}</span>
      <span style={{ marginLeft: 8, opacity: .45, fontSize: 11, flexShrink: 0 }}>×</span>
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────
// Rendered via createPortal into document.body so position:fixed is always
// relative to the viewport — never affected by scrollable ancestor containers.
export function Modal({ title, onClose, children, footer }) {
  const dialogRef = useRef(null);
  useFocusTrap(dialogRef);

  useEffect(() => {
    // Lock scroll on the .content scrollable region, NOT body
    // (body overflow is managed by CSS; locking body fights mobile CSS rules)
    const content = document.querySelector(".content");
    const prev = content ? content.style.overflow : "";
    if (content) content.style.overflow = "hidden";
    // iOS Safari: also lock body to prevent bounce-scroll behind fixed overlay
    const prevBody = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = e => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (content) content.style.overflow = prev;
      document.body.style.overflow = prevBody;
    };
  }, [onClose]);

  return createPortal(
    <div className="mo" onClick={e => e.target === e.currentTarget && onClose()}
      role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="md" ref={dialogRef} tabIndex={-1}>
        <div className="md-title" id="modal-title">{title}</div>
        <div style={{ overflowY: "auto", flex: "1 1 auto", minHeight: 0 }}>
          {children}
        </div>
        {footer && <div className="md-foot">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
// flex:0 0 auto on each tab so the row scrolls horizontally instead of
// compressing tab labels to fit the viewport width.
export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(t => (
        <div
          key={t.key}
          className={`tab${active === t.key ? " act" : ""}`}
          onClick={() => onChange(t.key)}
          role="tab"
          aria-selected={active === t.key}
          tabIndex={active === t.key ? 0 : -1}
          onKeyDown={e => (e.key === "Enter" || e.key === " ") && onChange(t.key)}
          style={{ flex: "0 0 auto" }}
        >
          {t.icon && (
            <span className="tab-icon">{t.icon}</span>
          )}
          <span className="tab-label">{t.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
export function Skeleton({ w = "100%", h = 20, r = 8, mb = 0, style = {} }) {
  return (
    <div
      className="shimmer"
      style={{
        width: w,
        height: h,
        borderRadius: r,
        marginBottom: mb,
        ...style
      }}
    />
  );
}

/** Specific skeleton for dashboard widgets/cards. */
export function WidgetSkeleton({ rows = 3, h = 160 }) {
  return (
    <div className="card shimmer-card" style={{ height: h, marginBottom: 16 }}>
      <div className="card-h">
        <Skeleton w={120} h={14} />
      </div>
      <div className="card-b" style={{ padding: 16 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} style={{ display: "flex", gap: 12, marginBottom: 12 }}>
            <Skeleton w={24} h={24} r={6} />
            <div style={{ flex: 1 }}>
              <Skeleton w="40%" h={10} mb={6} />
              <Skeleton w="100%" h={8} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Full-page skeleton for dashboard stats row. */
export function DashboardSkeleton() {
  return (
    <div className="sg-4" style={{ marginBottom: 16 }}>
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="sc shimmer-card" style={{ height: 100 }}>
          <Skeleton w={60} h={10} mb={12} />
          <Skeleton w="80%" h={24} mb={12} />
          <Skeleton w="40%" h={8} />
        </div>
      ))}
    </div>
  );
}


// ── ModuleLoader ─────────────────────────────────────────────────────────────
// Action-based status messages for financial/trading UX.
export function ModuleLoader({ pageKey }) {
  const { t } = useI18n();
  const messages = {
    dashboard:   "components.load_dashboard",
    investments: "components.load_investments",
    expenses:    "components.load_expenses",
    income:      "components.load_income",
    stocks:      "components.load_stocks",
    ml_stocks:   "components.load_ml_stocks",
    receipt:     "components.load_receipt",
    behavioral:  "components.load_behavioral",
    earn:        "components.load_earn",
    advanced:    "components.load_advanced",
  };

  const msg = t(messages[pageKey] || "components.load_init");

  return (
    <div className="module-loader" style={{ padding: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header Skeleton */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end" }}>
           <div>
              <Skeleton w={140} h={12} mb={8} />
              <Skeleton w={200} h={28} />
           </div>
           <Skeleton w={100} h={36} r={8} />
        </div>

        {/* Action Status */}
        <div style={{ 
          display: "flex", alignItems: "center", gap: 12, 
          padding: "16px 20px", background: "var(--bg2)", 
          borderRadius: "var(--rl)", border: "1px solid var(--bdr)" 
        }}>
          <div className="spin" style={{ 
            width: 16, height: 16, borderRadius: "50%", 
            border: "2px solid var(--bdr2)", borderTopColor: "var(--ind-b)" 
          }} />
          <span style={{ fontSize: 13, color: "var(--tx2)", fontWeight: 500 }}>{msg}</span>
        </div>

        {/* Content Skeleton Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ background: "var(--bg2)", padding: 20, borderRadius: "var(--rl)", border: "1px solid var(--bdr)" }}>
              <Skeleton w={80} h={10} mb={12} />
              <Skeleton w="60%" h={24} mb={20} />
              <Skeleton w="100%" h={8} r={4} />
            </div>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}


// ── StatCard ──────────────────────────────────────────────────────────────────
// `variant`: "default" | "hero" (larger, focal) | "compact" (smaller, secondary).
// Lets a metric row establish a focal point instead of N identical-weight cards.
export function StatCard({ label, value, color, accent, sub, className = "", variant = "default", onClick }) {
  return (
    <div
      className={`sc sc-${variant} ${className}`}
      style={accent ? { borderTop: `2px solid ${accent}` } : {}}
      onClick={onClick}
    >
      <div className="sc-lbl">{label}</div>
      <div className={`sc-val ${color || "n"}`}>{value}</div>
      {sub && <div className="sc-chg nt">{sub}</div>}
    </div>
  );
}

// ── LoadingSpinner ─────────────────────────────────────────────────────────────
export function LoadingSpinner({ msg }) {
  const { t } = useI18n();
  return (
    <div style={{ textAlign: "center", padding: 48, color: "var(--tx2)" }}>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
        <div style={{
          width: 28, height: 28, borderRadius: "50%",
          border: "3px solid var(--bdr2)",
          borderTopColor: "var(--ind-b)",
          animation: "comp-spin 0.9s linear infinite",
        }} />
      </div>
      <div style={{ fontSize: 13 }}>{msg || t("common.loading")}</div>
      <style>{`@keyframes comp-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── ApiError ──────────────────────────────────────────────────────────────────
export function ApiError({ error, onRetry }) {
  const { t } = useI18n();
  const isOffline = error?.type === "OFFLINE";
  const isInternal = error?.type === "INTERNAL";
  const status = error?.status;
  const url = error?.url || "/api/...";

  let title = t("components.api_error_title");
  let msg = String((typeof error === "string" ? error : (error?.message ? String(error.message) : error)) || t("components.api_error_msg"));
  let advice = t("components.api_error_advice");
  let showRunCmd = false;


  if (isOffline) {
    title = t("components.api_offline_title");
    msg = t("components.api_offline_msg");
    advice = t("components.api_offline_advice");
    showRunCmd = true;
  } else if (isInternal) {
    title = t("components.api_internal_title", { status: status || "500" });
    msg = error?.message || t("components.api_internal_msg");
    advice = t("components.api_internal_advice");
  }

  // Handle specific known startup crash (Case 2)
  if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
    advice = t("components.api_startup_advice");
  }

  return (
    <div style={{
      background: "rgba(248,113,113,.08)", border: "1px solid rgba(248,113,113,.25)",
      borderRadius: "var(--r)", padding: "20px 24px", textAlign: "center", margin: "16px 0",
    }}>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 10 }}>
        <IconAlert size={28} color="var(--rd)" />
      </div>
      <div style={{ fontSize: 13, color: "var(--rd)", fontWeight: 600, marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: "var(--tx2)", marginBottom: 12 }}>{msg}</div>
      <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 14 }}>
        {showRunCmd ? (
          <>{t("components.api_run")} <code style={{ background: "var(--bg4)", padding: "2px 6px", borderRadius: 4 }}>python api_server.py</code></>
        ) : advice}
      </div>

      <div style={{ fontSize: 10, color: "var(--tx3)", marginBottom: 16, opacity: 0.6, fontFamily: "var(--mono)", wordBreak: "break-all" }}>
        {t("components.api_endpoint")} {url}
      </div>

      <div style={{ display: "flex", justifyContent: "center", gap: 10 }}>
        {onRetry && (
          <button className="btn btn-g btn-s" onClick={onRetry}
            style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <IconRefresh size={13} /> {t("common.retry")}
          </button>
        )}
        <button className="btn btn-s" onClick={() => window.location.hash = "#/advanced"}
          style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          {t("components.help_panel")}
        </button>
      </div>
    </div>
  );
}


// ── Empty State ───────────────────────────────────────────────────────────────
// ── Empty State — Premium Illustrated ─────────────────────────────────────────
// SVG illustrations are inline to avoid extra network requests and ensure
// they inherit the current theme's CSS variables.

function EmptySVGExpense() {
  return (
    <svg width="110" height="90" viewBox="0 0 110 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <style>{`
        .es-float { animation: es-float 3s ease-in-out infinite; transform-origin: center; }
        .es-float2 { animation: es-float 3s ease-in-out infinite 0.5s; transform-origin: center; }
        .es-fade { animation: es-fadein 0.6s ease forwards; }
        @keyframes es-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        @keyframes es-fadein { from{opacity:0;transform:scale(.85)} to{opacity:1;transform:scale(1)} }
      `}</style>
      {/* Receipt */}
      <g className="es-float es-fade">
        <rect x="28" y="12" width="54" height="66" rx="6" fill="var(--bg3)" stroke="var(--bdr2)" strokeWidth="1.5"/>
        <rect x="36" y="26" width="28" height="4" rx="2" fill="var(--bdr2)"/>
        <rect x="36" y="36" width="22" height="3" rx="1.5" fill="var(--bdr2)"/>
        <rect x="36" y="44" width="32" height="3" rx="1.5" fill="var(--bdr2)"/>
        <rect x="36" y="52" width="18" height="3" rx="1.5" fill="var(--bdr2)"/>
        <path d="M28 70 l5-5 5 5 5-5 5 5 5-5 5 5 5-5 5 5 5-5 v8 H28 Z" fill="var(--bg2)"/>
      </g>
      {/* X mark */}
      <g className="es-float2 es-fade" style={{animationDelay:".2s"}}>
        <circle cx="76" cy="22" r="12" fill="var(--bg2)" stroke="var(--rd)" strokeWidth="1.5"/>
        <line x1="72" y1="18" x2="80" y2="26" stroke="var(--rd)" strokeWidth="2" strokeLinecap="round"/>
        <line x1="80" y1="18" x2="72" y2="26" stroke="var(--rd)" strokeWidth="2" strokeLinecap="round"/>
      </g>
      {/* Glow */}
      <ellipse cx="55" cy="84" rx="30" ry="5" fill="var(--rd)" opacity="0.07"/>
    </svg>
  );
}

function EmptySVGIncome() {
  return (
    <svg width="110" height="90" viewBox="0 0 110 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <style>{`
        .ei-coin { animation: ei-coin 2.5s ease-in-out infinite; transform-origin: 55px 42px; }
        .ei-arrow { animation: ei-arrow 2.5s ease-in-out infinite; }
        @keyframes ei-coin { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-7px) scale(1.04)} }
        @keyframes ei-arrow { 0%,100%{opacity:.4;transform:translateY(0)} 50%{opacity:1;transform:translateY(-4px)} }
      `}</style>
      {/* Coin stack */}
      <ellipse cx="55" cy="62" rx="22" ry="7" fill="var(--bg3)" stroke="var(--bdr2)" strokeWidth="1.2"/>
      <ellipse cx="55" cy="56" rx="22" ry="7" fill="var(--bg3)" stroke="var(--bdr2)" strokeWidth="1.2"/>
      <ellipse cx="55" cy="50" rx="22" ry="7" fill="var(--bg3)" stroke="var(--bdr2)" strokeWidth="1.2"/>
      {/* Main coin */}
      <g className="ei-coin">
        <ellipse cx="55" cy="38" rx="22" ry="7" fill="var(--ind)" opacity="0.85"/>
        <ellipse cx="55" cy="34" rx="22" ry="7" fill="var(--ind)" stroke="var(--yl)" strokeWidth="1"/>
        <text x="55" y="37" textAnchor="middle" fontSize="8" fill="var(--bg)" fontWeight="900" fontFamily="var(--mono)">IDR</text>
      </g>
      {/* Up arrow */}
      <g className="ei-arrow">
        <path d="M55 14 L55 26" stroke="var(--gr)" strokeWidth="2.5" strokeLinecap="round"/>
        <path d="M49 20 L55 14 L61 20" stroke="var(--gr)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      </g>
      <ellipse cx="55" cy="84" rx="30" ry="5" fill="var(--gr)" opacity="0.07"/>
    </svg>
  );
}

function EmptySVGInvestment() {
  return (
    <svg width="110" height="90" viewBox="0 0 110 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <style>{`
        .inv-line { stroke-dasharray: 100; stroke-dashoffset: 100; animation: inv-draw 1.2s ease forwards 0.2s; }
        .inv-float { animation: inv-float 3s ease-in-out infinite; }
        .inv-dot { animation: inv-pop 0.4s cubic-bezier(.34,1.56,.64,1) forwards; opacity:0; }
        @keyframes inv-draw { to{stroke-dashoffset:0} }
        @keyframes inv-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
        @keyframes inv-pop { to{opacity:1;transform:scale(1)} from{transform:scale(0)} }
      `}</style>
      <g className="inv-float">
        {/* Chart frame */}
        <rect x="15" y="15" width="80" height="60" rx="8" fill="var(--bg3)" stroke="var(--bdr2)" strokeWidth="1.2"/>
        {/* Grid lines */}
        <line x1="15" y1="55" x2="95" y2="55" stroke="var(--bdr)" strokeWidth="0.7" strokeDasharray="3,3"/>
        <line x1="15" y1="40" x2="95" y2="40" stroke="var(--bdr)" strokeWidth="0.7" strokeDasharray="3,3"/>
        {/* Chart line */}
        <polyline className="inv-line" points="23,65 38,58 50,60 62,42 75,36 87,22" fill="none" stroke="var(--cy)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        {/* Dots */}
        <circle className="inv-dot" cx="87" cy="22" r="4" fill="var(--cy)" style={{animationDelay:"1.1s"}}/>
        <circle className="inv-dot" cx="75" cy="36" r="3" fill="var(--cy)" opacity="0.6" style={{animationDelay:"1.3s"}}/>
      </g>
      <ellipse cx="55" cy="84" rx="30" ry="5" fill="var(--cy)" opacity="0.07"/>
    </svg>
  );
}

function EmptySVGGeneric() {
  return (
    <svg width="110" height="90" viewBox="0 0 110 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <style>{`
        .es-wallet-float { animation: es-wallet-float 3s ease-in-out infinite; transform-origin: center; }
        .es-wallet-glow { animation: es-wallet-glow 3s ease-in-out infinite; }
        @keyframes es-wallet-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        @keyframes es-wallet-glow { 0%,100%{opacity:0.06;transform:scale(1)} 50%{opacity:0.12;transform:scale(1.1)} }
      `}</style>
      <g className="es-wallet-float">
        {/* Credit Cards behind */}
        <rect x="35" y="20" width="40" height="24" rx="3" fill="var(--ind)" opacity="0.4" transform="rotate(-10 35 20)" />
        <rect x="42" y="18" width="40" height="24" rx="3" fill="var(--cy)" opacity="0.6" transform="rotate(-3 42 18)" />
        
        {/* Wallet Main Body */}
        <rect className="es-wallet-body" x="25" y="30" width="60" height="42" rx="8" fill="var(--bg3)" stroke="var(--bdr2)" strokeWidth="1.5"/>
        
        {/* Wallet Outer Flap */}
        <path d="M55 30 L85 30 C87.5 30 89 32 88 35 L82 49 C81 52 78.5 52 76 52 L55 52 Z" fill="var(--bg2)" stroke="var(--bdr2)" strokeWidth="1.5" />
        
        {/* Metal button/snap */}
        <circle cx="76" cy="41" r="3.5" fill="var(--yl)" stroke="var(--bdr)" strokeWidth="1" />
        
        {/* Gold Coin popping out */}
        <circle cx="34" cy="28" r="7" fill="var(--yl)" opacity="0.85" />
        <circle cx="34" cy="28" r="7" stroke="var(--bdr)" strokeWidth="1" fill="none" />
        <text x="34" y="30.5" textAnchor="middle" fontSize="7" fill="var(--bg)" fontWeight="900" fontFamily="var(--mono)">$</text>
      </g>
      {/* Wallet Glow */}
      <ellipse className="es-wallet-glow" cx="55" cy="82" rx="32" ry="5" fill="var(--ind)" opacity="0.08"/>
    </svg>
  );
}

const EMPTY_SVG_MAP = {
  expense:    EmptySVGExpense,
  income:     EmptySVGIncome,
  investment: EmptySVGInvestment,
  generic:    EmptySVGGeneric,
};

export function Empty({ icon, msg, sub, variant = "generic", action, actionLabel }) {
  const { t } = useI18n();
  const SVGIllustration = EMPTY_SVG_MAP[variant] ?? EmptySVGGeneric;
  return (
    <div className="empty-state">
      <div className="empty-state-illo">
        {icon ? (
          <div className="empty-state-icon-wrap">{icon}</div>
        ) : (
          <SVGIllustration />
        )}
      </div>
      <div className="empty-state-msg">{msg || t("components.no_data")}</div>
      {sub && <div className="empty-state-sub">{sub}</div>}
      {action && (
        <button className="btn btn-p empty-state-btn" onClick={action}>
          {actionLabel || t("components.get_started")}
        </button>
      )}
    </div>
  );
}

// ── ProgressBar ───────────────────────────────────────────────────────────────
export function ProgressBar({ pct, color }) {
  return (
    <div className="prog-wrap">
      <div className="prog-fill" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
    </div>
  );
}

// ── Pill ──────────────────────────────────────────────────────────────────────
// `emph` promotes a pill to the solid, glowing emphasized style. Use it only
// for the single most important status on a surface; leave the rest muted.
export function Pill({ children, variant = "dim", emph = false, style }) {
  return <span className={`pill ${variant}${emph ? " emph" : ""}`} style={style}>{children}</span>;
}

// ── CategoryBar ───────────────────────────────────────────────────────────────
export function CategoryBar({ label, amount, max, color, icon }) {
  return (
    <div className="cat-row">
      <div className="cat-lbl">{icon} {label}</div>
      <div className="cat-bw">
        <div className="cat-bf" style={{ width: `${(amount / max) * 100}%`, background: color }} />
      </div>
      <div className="cat-amt">{fmt(amount)}</div>
    </div>
  );
}

// WCAG 1.3.1: label is now programmatically associated with its input via htmlFor/id.
// Pass an `id` prop to FormGroup; it is forwarded to the label (htmlFor) and
// cloned onto the child input as its `id` attribute.

export function FormGroup({ label, children, id }) {
  // If caller passes an explicit id, use it; otherwise derive one from label text.
  const inputId = id || `fg-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const labelledChildren = Children.map(children, (child) =>
    isValidElement(child) && !child.props.id
      ? cloneElement(child, { id: inputId })
      : child
  );
  return (
    <div className="fg">
      <label className="fl" htmlFor={inputId}>{label}</label>
      {labelledChildren}
    </div>
  );
}

export function FormRow({ children }) {
  return <div className="fr">{children}</div>;
}

// ── PLBadge ───────────────────────────────────────────────────────────────────
export function PLBadge({ pl, pct, isUSD = false }) {
  const pos = pl >= 0;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      color: pos ? "var(--gr)" : "var(--rd)",
      fontFamily: "var(--mono)", fontWeight: 700, fontSize: 12,
      whiteSpace: "nowrap",
    }}>
      {pos
        ? <IconUp   size={12} color="var(--gr)" />
        : <IconDown size={12} color="var(--rd)" />}
      {fmtS(pl, isUSD)}{pct !== undefined ? ` (${pct >= 0 ? "+" : ""}${pct?.toFixed(1)}%)` : ""}
    </span>
  );
}

// ── SumBox ────────────────────────────────────────────────────────────────────
export function SumBox({ items }) {
  return (
    <div className="sum-box">
      {items.map(({ label, value, color }) => (
        <div key={label} className="si">
          <div className="si-lbl">{label}</div>
          <div className="si-val" style={color ? { color } : {}}>{value}</div>
        </div>
      ))}
    </div>
  );
}

// ── ConfirmDialog ─────────────────────────────────────────────────────────────
// Replaces window.confirm() — native confirm dialogs are styled inconsistently
// and often blocked on mobile browsers (especially iOS WebView & Android Chrome).
// This component is fully touch-friendly and respects safe-area insets.
export function ConfirmDialog({ message, onConfirm, onCancel, confirmLabel, danger = false }) {
  const { t } = useI18n();
  const dialogRef = useRef(null);
  useFocusTrap(dialogRef);

  useEffect(() => {
    const content = document.querySelector(".content");
    const prev = content ? content.style.overflow : "";
    if (content) content.style.overflow = "hidden";
    const prevBody = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = e => { if (e.key === "Escape") onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (content) content.style.overflow = prev;
      document.body.style.overflow = prevBody;
    };
  }, [onCancel]);

  return createPortal(
    <div className="mo" onClick={onCancel}
      role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-msg">
      <div className="md" ref={dialogRef} tabIndex={-1} style={{ maxWidth: 360, padding: "22px 24px" }} onClick={e => e.stopPropagation()}>
        <div className="md-title" id="confirm-title" style={{ fontSize: 15, marginBottom: 12 }}>
          {t("components.confirm_title")}
        </div>
        <div id="confirm-msg" style={{ fontSize: 13, color: "var(--tx2)", lineHeight: 1.6, marginBottom: 20 }}>
          {message}
        </div>
        <div className="md-foot" style={{ marginTop: 0 }}>
          <button className="btn btn-g" onClick={onCancel} style={{ minHeight: 44 }}>{t("common.cancel")}</button>
          <button
            className={`btn ${danger ? "btn-d" : "btn-p"}`}
            onClick={() => { onConfirm(); onCancel(); }}
            style={{ minHeight: 44 }}
          >
            {confirmLabel || t("components.confirm")}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
