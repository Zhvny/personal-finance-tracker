// ─── admin.jsx ────────────────────────────────────────────────────────────────
// Admin page — hidden from sidebar, accessible via /admin directly.
// Contains logs tab (and can be extended with other admin tabs).

import { useState, useEffect } from "react";
import { apiFetch } from "../finance/useApi.js";
import { IconRefresh, IconClose } from "../icons.jsx";
import { useI18n } from "../i18n/context.js";

export default function AdminPage({ onToast }) {
  const { t } = useI18n();
  const [tab, setTab] = useState("logs");
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch("/logs");
      setLogs(Array.isArray(data) ? data : data?.logs ?? []);
    } catch (e) {
      setError(e.message || t("admin.load_failed"));
      onToast?.(e.message || t("admin.load_failed"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadLogs(); }, []);

  return (
    <div>
      <h1 className="sr-only">{t("admin.sr_title")}</h1>
      <div style={{ marginBottom: 14, display: "flex", gap: 8 }}>
        <button className={`tab ${tab === "logs" ? "act" : ""}`} onClick={() => setTab("logs")}>
          <IconRefresh size={13} /> {t("admin.tab_logs")}
        </button>
      </div>

      {tab === "logs" && (
        <div className="card">
          <div className="card-h">
            <span className="card-t">{t("admin.system_logs")}</span>
            <button className="db-action-btn" onClick={loadLogs} disabled={loading}>
              <IconRefresh size={14} style={{ animation: loading ? "comp-spin 1s linear infinite" : "none" }} />
              {t("common.refresh")}
            </button>
          </div>
          <div className="card-b">
            {loading && <div style={{ color: "var(--tx3)", fontSize: 13 }}>{t("admin.loading_logs")}</div>}
            {error && <div style={{ color: "var(--rd)", fontSize: 13 }}>{error}</div>}
            {!loading && !error && logs.length === 0 && (
              <div style={{ color: "var(--tx3)", fontSize: 13 }}>{t("admin.no_logs")}</div>
            )}
            {!loading && !error && logs.length > 0 && (
              <div style={{ maxHeight: 500, overflowY: "auto", fontSize: 12, fontFamily: "monospace" }}>
                {logs.map((log, i) => (
                  <div key={i} style={{ padding: "6px 8px", borderBottom: "1px solid var(--bdr)", display: "flex", gap: 10 }}>
                    <span style={{ color: "var(--tx3)", minWidth: 80 }}>{log.timestamp || log.time || "—"}</span>
                    <span style={{ color: log.level === "error" ? "var(--rd)" : log.level === "warn" ? "var(--yl)" : "var(--tx2)", minWidth: 50 }}>{log.level || "info"}</span>
                    <span style={{ color: "var(--tx)" }}>{log.message || log.msg || JSON.stringify(log)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
