// ─── AIPassiveStatus.jsx ─────────────────────────────────────────────────────
// Non-intrusive AI status indicator. Replaces the loud/interactive AIStatusBadge.
// 
// Mandatory variants:
//   - Using Local AI (Ollama)
//   - AI Processing Available (Claude/Gemini)
//   - Enhanced Vision Enabled (Vision active)

import React from "react";
import { IconML, IconScan, IconShieldCheck } from "../icons.jsx";
import { useI18n } from "../i18n/context.js";

/**
 * Props:
 *   status  : object from useAIStatus().status
 *   loading : bool
 */
export default function AIPassiveStatus({ status, loading }) {
  const { t } = useI18n();
  if (loading || !status) {
    return (
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "3px 10px", borderRadius: 99, fontSize: 10,
        color: "var(--tx3)", background: "var(--ind-d)",
        border: "1px solid var(--bdr)",
        opacity: 0.6, height: 24, boxSizing: "border-box"
      }}>
        <div className="spin-mini" />
        <span style={{ lineHeight: 1 }}>{t("behavioral.ai_initializing")}</span>
        <style>{`
          .spin-mini {
            width: 10px; height: 10px; border: 1.5px solid var(--tx3);
            border-top-color: transparent; border-radius: 50%;
            animation: ft-spin 1s linear infinite;
          }
          @keyframes ft-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        `}</style>
      </div>
    );
  }

  let text = t("behavioral.ai_available");
  let Icon = IconML; // Default to brain for general AI
  
  if (status.vision) {
    text = t("behavioral.vision_enabled");
    Icon = IconScan;
  } else if (status.active === "ollama") {
    text = t("behavioral.local_ai");
    Icon = IconML;
  } else if (status.active === "rules") {
    text = t("behavioral.rule_engine_active");
    Icon = IconShieldCheck;
  } else if (status.active === "none") {
    text = t("behavioral.ai_idle");
    Icon = IconML;
  }

  return (
    <div 
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        borderRadius: 99,
        fontSize: 10,
        fontWeight: 600,
        color: "var(--tx3)",
        background: "var(--ind-d)",
        border: "1px solid var(--bdr)",
        letterSpacing: "0.2px",
        transition: "var(--trans-base)",
        cursor: "default",
        userSelect: "none",
        height: 24,
        boxSizing: "border-box"
      }} 
      title={status.reason || `${status.active}: ${status.model || 'auto'}`}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Icon size={13} style={{ opacity: 0.8 }} />
      </div>
      <span style={{ lineHeight: 1 }}>{text}</span>
      {status.active !== "none" && (
        <span style={{
          width: 4, height: 4, borderRadius: "50%",
          background: "var(--gr)",
          marginLeft: 2,
          boxShadow: "var(--glow-gr)"
        }} />
      )}
    </div>
  );
}
