import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { apiFetch, useUniverseAudit } from "../finance/useApi.js";
import { PageWrapper } from "../animations.jsx";
import { useI18n } from "../i18n/context.js";
import { 
  IconActivity, IconTarget, IconRefresh, IconArrowRight, 
  IconFlash, IconPieChart, IconInfo, IconAlertCircle,
  IconShieldCheck, IconUp, IconDown, IconMore, IconSearch, IconX
} from "../icons.jsx";

const ParamCard = ({ label, value, sub }) => (
  <div style={{ background: "var(--bg3)", padding: 16, borderRadius: 16, border: "1px solid var(--bdr)" }}>
    <div style={{ fontSize: 9, fontWeight: 900, color: "var(--tx3)", textTransform: "uppercase", marginBottom: 8 }}>{label}</div>
    <div style={{ fontSize: 18, fontWeight: 900, color: "var(--tx)" }}>{value}</div>
    {sub && <div style={{ fontSize: 9, color: "var(--tx3)", marginTop: 4 }}>{sub}</div>}
  </div>
);

const EvolutionChart = ({ logs }) => {
  const { t } = useI18n();
  if (!logs || logs.length === 0) return null;
  const maxMae = Math.max(...logs.map(l => l.mae));
  const minMae = Math.min(...logs.map(l => l.mae));
  const range = maxMae - minMae;

  return (
    <div style={{ height: 120, display: "flex", alignItems: "flex-end", gap: 2, padding: "20px 0" }}>
      {logs.map((l, i) => {
        const h = range === 0 ? 50 : ((maxMae - l.mae) / range) * 80 + 20;
        return (
          <div 
            key={l.id} 
            title={t("genetic.iter_mae", { iter: l.iteration, mae: l.mae.toFixed(6) })}
            style={{ 
              flex: 1, 
              height: `${h}%`, 
              background: l.is_winner ? "var(--cy)" : "var(--bg4)",
              borderRadius: 2,
              opacity: l.is_winner ? 1 : 0.4,
              transition: "all 0.3s ease"
            }} 
          />
        );
      })}
    </div>
  );
};

export default function GeneticPortfolioLab({ onToast }) {
  const { t } = useI18n();
  const [models, setModels] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState(null);
  const [universeStats, setUniverseStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [auditSearch, setAuditSearch] = useState("");
  const [optimizing, setOptimizing] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [pollingProgress, setPollingProgress] = useState(0);
  const [lastDiagnostics, setLastDiagnostics] = useState(null);
  const [diagnosticsExpanded, setDiagnosticsExpanded] = useState(false);
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);

  const { data: universeAudit, loading: auditLoading, reload: reloadAudit } = useUniverseAudit();

  // Optimizer Parameters
  const [minAssets, setMinAssets] = useState(1);
  const [maxAssets, setMaxAssets] = useState(10);
  const [riskMode, setRiskMode] = useState("sharpe");

  const [dataError, setDataError] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setDataError(null);
    try {
      const [m, s, stats] = await Promise.all([
        apiFetch("/genetic/models"),
        apiFetch("/genetic/status"),
        apiFetch("/genetic/portfolio/stats")
      ]);
      setModels(m || []);
      setStatus(s);
      setUniverseStats(stats);
      setSelectedTicker(current => {
        if (!current && m?.length > 0) return m[0].ticker;
        return current;
      });
    } catch (e) {
      console.error("Failed to load genetic data", e);
      setDataError(e?.message || String(e) || t("genetic.load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  const handleOptimize = async () => {
    if (optimizing) return;

    // Synchronous Validation Gates
    if (minAssets > maxAssets) {
      onToast(t("genetic.err_min_max"), "error");
      return;
    }
    if (!universeStats || universeStats.eligible_count === 0) {
      onToast(t("genetic.err_no_eligible"), "error");
      return;
    }
    if (!riskMode) {
      onToast(t("genetic.err_missing_config"), "error");
      return;
    }

    setOptimizing(true);
    setPollingProgress(0);
    try {
      const res = await apiFetch("/genetic/portfolio/optimize", {
        method: "POST",
        body: JSON.stringify({
          min_assets: minAssets,
          max_assets: maxAssets,
          risk_mode: riskMode
        })
      });
      
      if (res?.error) {
        onToast(res.message || res.error, "error");
        setOptimizing(false);
      } else if (res?.task_id) {
        setActiveTaskId(res.task_id);
        onToast(t("genetic.task_started"));
      } else {
        // Fallback for immediate results if any
        if (res?.diagnostics) {
          setLastDiagnostics(res.diagnostics);
        }
        onToast(t("genetic.reoptimized"));
        reloadAudit();
        await loadData();
        setOptimizing(false);
      }
    } catch (e) {
      console.error("Optimization failed", e);
      if (e.status === 400) {
        onToast(t("genetic.err_400"), "error");
      } else if (e.status === 422) {
        onToast(t("genetic.err_422"), "error");
      } else if (e.status === 503) {
        onToast(t("genetic.err_503"), "error");
      } else {
        onToast(t("genetic.opt_failed", { error: e.message }), "error");
      }
      setOptimizing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    let timeoutId;
    let isMounted = true;

    const poll = async () => {
      if (!activeTaskId || !isMounted) return;
      
      try {
        const res = await apiFetch(`/genetic/portfolio/status/${activeTaskId}`);
        if (!isMounted) return;

        if (res?.status === "completed") {
          if (res.result?.diagnostics) {
            setLastDiagnostics(res.result.diagnostics);
          }
          onToast(t("genetic.reoptimized"));
          reloadAudit();
          await loadData();
          setActiveTaskId(null);
          setOptimizing(false);
          setPollingProgress(100);
        } else if (res?.status === "failed" || res?.status === "timeout") {
          if (res?.status === "timeout") {
            onToast(t("genetic.err_timeout"), "error");
          } else {
            onToast(t("genetic.opt_failed", { error: res.error || t("genetic.check_diag") }), "error");
          }
          setActiveTaskId(null);
          setOptimizing(false);
        } else {
          if (res?.progress !== undefined) {
            setPollingProgress(res.progress);
          }
          timeoutId = setTimeout(poll, 2000);
        }
      } catch (e) {
        console.error("Polling failed", e);
        if (isMounted) {
          onToast(t("genetic.err_status"), "error");
          setActiveTaskId(null);
          setOptimizing(false);
        }
      }
    };

    if (activeTaskId) {
      poll();
    }
    
    return () => {
      isMounted = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [activeTaskId, loadData, onToast, reloadAudit]);

  useEffect(() => {
    if (selectedTicker) {
      apiFetch(`/genetic/logs/${selectedTicker}`)
        .then(res => setLogs(res || []))
        .catch(e => console.error("Failed to load logs", e));
    }
  }, [selectedTicker]);

  const filteredModels = useMemo(() => {
    if (!searchTerm) return models;
    return models.filter(m => 
      m.ticker.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.category.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [models, searchTerm]);

  const activeModel = useMemo(() => 
    models.find(m => m.ticker === selectedTicker), 
  [models, selectedTicker]);

  const filteredExcluded = useMemo(() => {
    if (!universeAudit?.excluded) return [];
    if (!auditSearch) return universeAudit.excluded;
    const s = auditSearch.toLowerCase();
    return universeAudit.excluded.filter(x => 
      x.ticker.toLowerCase().includes(s) || 
      x.reason.toLowerCase().includes(s)
    );
  }, [universeAudit, auditSearch]);

  return (
    <PageWrapper title={t("genetic.title")}>
      <div style={{ padding: 20 }}>
        <h1 className="sr-only">{t("genetic.sr_title")}</h1>
        {dataError && (
          <div style={{ 
            padding: "16px 20px", borderRadius: 16, marginBottom: 24,
            background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.25)",
            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16
          }}>
            <div>
              <div style={{ fontWeight: 800, fontSize: 13, color: "var(--rd)", marginBottom: 4 }}>
                ⚠️ {t("genetic.fetch_error")}
              </div>
              <div style={{ fontSize: 11, color: "var(--tx2)" }}>
                {typeof dataError === "string" ? dataError : dataError?.message || String(dataError)}
              </div>
            </div>
            <button className="btn btn-g btn-s" onClick={loadData}>
              <IconRefresh size={13} style={{ marginRight: 4 }} /> {t("common.retry")}
            </button>
          </div>
        )}
        {/* Header Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 20, marginBottom: 32 }}>
          <div className="card" style={{ padding: 24, background: "var(--glass)", border: "1px solid var(--bdr)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <IconFlash size={20} color="var(--cy)" />
              <span className="pill cy" style={{ fontSize: 9 }}>{t("genetic.active")}</span>
            </div>
            <div style={{ fontSize: 24, fontWeight: 900 }}>{universeStats?.eligible_count || 0}</div>
            <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase" }}>{t("genetic.eligible_universe")}</div>
          </div>
          <div className="card" style={{ padding: 24, background: "var(--glass)", border: "1px solid var(--bdr)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <IconActivity size={20} color="var(--gr)" />
              <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)" }}>{t("genetic.latest_run")}</span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 900 }}>{status?.last_run ? new Date(status.last_run).toLocaleDateString() : t("genetic.never")}</div>
            <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase", marginTop: 4 }}>{t("genetic.system_heartbeat")}</div>
          </div>
          <div className="card" style={{ padding: 24, background: "var(--glass)", border: "1px solid var(--bdr)" }}>
             <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <IconShieldCheck size={20} color="var(--cy)" />
                <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)" }}>{t("genetic.total_assets")}</span>
             </div>
             <div style={{ fontSize: 24, fontWeight: 900 }}>{universeStats?.total_count || 1051}</div>
             <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase", marginTop: 4 }}>{t("genetic.cached_tickers")}</div>
          </div>
        </div>

        <div className="genetic-grid">
          {/* Sidebar: Model List */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {/* Optimizer Settings */}
            <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>{t("genetic.optimizer_config")}</div>
              
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <label style={{ fontSize: 10, fontWeight: 800, color: "var(--tx2)" }}>{t("genetic.min_assets")}</label>
                  <span style={{ fontSize: 10, fontWeight: 900, color: "var(--cy)" }}>{minAssets}</span>
                </div>
                <input 
                  type="range" min="1" max={universeStats?.eligible_count || 500} 
                  value={minAssets} 
                  onChange={e => setMinAssets(parseInt(e.target.value))}
                  style={{ width: "100%", accentColor: "var(--cy)" }}
                />
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <label style={{ fontSize: 10, fontWeight: 800, color: "var(--tx2)" }}>{t("genetic.max_assets")}</label>
                  <span style={{ fontSize: 10, fontWeight: 900, color: "var(--cy)" }}>{maxAssets}</span>
                </div>
                <input 
                  type="range" min="1" max={universeStats?.total_count || 1000} 
                  value={maxAssets} 
                  onChange={e => setMaxAssets(parseInt(e.target.value))}
                  style={{ width: "100%", accentColor: "var(--cy)" }}
                />
              </div>

              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 10, fontWeight: 800, color: "var(--tx2)", display: "block", marginBottom: 8 }}>{t("genetic.risk_mode")}</label>
                <select 
                  value={riskMode}
                  onChange={e => setRiskMode(e.target.value)}
                  style={{ width: "100%", height: 36, background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 10, fontSize: 12, color: "var(--tx)", padding: "0 8px" }}
                >
                  <option value="sharpe">{t("genetic.risk_sharpe")}</option>
                  <option value="returns">{t("genetic.risk_returns")}</option>
                  <option value="volatility">{t("genetic.risk_volatility")}</option>
                </select>
              </div>

              <button 
                className={`btn ${optimizing ? 'btn-disabled' : 'btn-cy'}`}
                onClick={handleOptimize}
                disabled={optimizing}
                style={{ width: "100%", borderRadius: 12, height: 40, fontWeight: 900, fontSize: 12 }}
              >
                {optimizing ? (
                  <>
                    <IconRefresh size={14} className="spin-ico" style={{ marginRight: 8 }} />
                    {pollingProgress <= 30 ? t("genetic.optimizing") :
                     pollingProgress <= 70 ? t("genetic.recalculating") :
                     t("genetic.fetching_results")}
                  </>
                ) : t("genetic.run_optimizer")}
              </button>
            </div>

            <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)", height: "calc(100vh - 600px)", display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>{t("genetic.optimized_models")}</div>
              
              <div style={{ position: "relative", marginBottom: 16 }}>
                <IconSearch size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--tx3)" }} />
                <input 
                  type="text" 
                  placeholder={t("genetic.filter_tickers")} 
                  style={{ width: "100%", height: 36, background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 10, paddingLeft: 36, fontSize: 12, color: "var(--tx)" }}
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                />
              </div>

              <div 
                ref={containerRef}
                onScroll={e => setScrollTop(e.target.scrollTop)}
                style={{ flex: 1, overflowY: "auto", position: "relative", paddingRight: 4 }}
              >
                <div style={{ height: filteredModels.length * 80, position: "relative" }}>
                  {filteredModels.slice(
                    Math.max(0, Math.floor(scrollTop / 80) - 5),
                    Math.min(filteredModels.length, Math.floor((scrollTop + 800) / 80) + 5)
                  ).map((m, i) => {
                    const index = Math.max(0, Math.floor(scrollTop / 80) - 5) + i;
                    return (
                      <div 
                        key={m.ticker} 
                        onClick={() => setSelectedTicker(m.ticker)}
                        style={{ 
                          position: "absolute",
                          top: index * 80,
                          left: 0,
                          right: 4,
                          height: 68,
                          padding: 16, 
                          background: selectedTicker === m.ticker ? "var(--bg3)" : "transparent",
                          borderRadius: 16,
                          border: "1px solid",
                          borderColor: selectedTicker === m.ticker ? "var(--cy)" : "transparent",
                          cursor: "pointer",
                          transition: "all 0.2s ease"
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontWeight: 900, fontSize: 16 }}>{m.ticker}</span>
                          <span style={{ fontSize: 9, color: "var(--tx3)" }}>{m.category.toUpperCase()}</span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 4 }}>MAE: {m.best_mae.toFixed(6)}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </aside>

          {/* Main Content: Evolution View */}
          <main>
            {activeModel ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
                {/* Evolution Progress */}
                <div className="card" style={{ padding: 32, background: "var(--bg2)", borderRadius: 32, border: "1px solid var(--bdr)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 2, marginBottom: 4 }}>{t("genetic.evolutionary_path")}</div>
                      <div style={{ fontSize: 24, fontWeight: 900 }}>{t("genetic.sniper_opt", { ticker: activeModel.ticker })}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)" }}>{t("genetic.best_mae")}</div>
                      <div style={{ fontSize: 24, fontWeight: 900, color: "var(--cy)" }}>{activeModel.best_mae.toFixed(6)}</div>
                    </div>
                  </div>
                  
                  <EvolutionChart logs={logs} />
                  
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, fontWeight: 800, color: "var(--tx3)", marginTop: 8 }}>
                    <span>{t("genetic.generation", { n: 0 })}</span>
                    <span>{t("genetic.generation", { n: logs.length - 1 })}</span>
                  </div>
                </div>

                {/* Parameters Grid */}
                <div className="genetic-params-grid">
                   <div className="card" style={{ padding: 24, borderRadius: 24, border: "1px solid var(--bdr)" }}>
                      <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>{t("genetic.winning_params")}</div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                         <ParamCard label={t("genetic.param_lr")} value={activeModel.params.learning_rate.toFixed(4)} />
                         <ParamCard label={t("genetic.param_max_depth")} value={activeModel.params.max_depth} />
                         <ParamCard label={t("genetic.param_estimators")} value={activeModel.params.n_estimators} />
                         <ParamCard label={t("genetic.param_subsample")} value={activeModel.params.subsample.toFixed(2)} />
                      </div>
                   </div>

                   <div className="card" style={{ padding: 24, borderRadius: 24, border: "1px solid var(--bdr)", background: "var(--bg2)", display: "flex", flexDirection: "column" }}>
                     <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                       <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1.5 }}>{t("genetic.data_health")}</div>
                       <div className="pill cy" style={{ fontSize: 9 }}>{t("genetic.system_diag")}</div>
                     </div>

                     <div style={{ marginBottom: 24, display: "flex", alignItems: "center", justifyContent: "space-between" }}>                        <div>
                          <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", marginBottom: 4 }}>{t("genetic.universe_filtered")}</div>
                          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                            <span style={{ fontSize: 32, fontWeight: 900, color: "var(--tx)" }}>
                              {universeStats?.total_count && universeStats?.eligible_count 
                                ? (((universeStats.total_count - universeStats.eligible_count) / universeStats.total_count) * 100).toFixed(1) 
                                : "0.0"}%
                            </span>
                            <span style={{ fontSize: 11, fontWeight: 800, color: "var(--rd)" }}>{t("genetic.reduced")}</span>
                          </div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                           <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", marginBottom: 4 }}>{t("genetic.dropout")}</div>
                           <div style={{ fontSize: 20, fontWeight: 900, color: "var(--rd)" }}>
                              {universeStats?.eligible_count ? Math.max(0, universeStats.eligible_count - models.length) : 0}
                           </div>
                        </div>
                      </div>

                      <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", marginBottom: 12, letterSpacing: 1 }}>{t("genetic.exclusion_reasons")}</div>
                      <div style={{ flex: 1, overflowY: "auto", maxHeight: 200, display: "flex", flexDirection: "column", gap: 8 }}>
                        {universeStats?.excluded_reasons && Object.entries(universeStats.excluded_reasons).map(([reason, count]) => {
                          const isCritical = reason.toLowerCase().includes("missing") || reason.toLowerCase().includes("failed");
                          const isWarning = reason.toLowerCase().includes("stale") || reason.toLowerCase().includes("history");
                          const color = isCritical ? "var(--rd)" : isWarning ? "var(--yl)" : "var(--cy)";
                          
                          return (
                            <div key={reason} style={{ 
                              background: "var(--bg3)", 
                              padding: "12px 16px", 
                              borderRadius: 16, 
                              border: "1px solid var(--bdr)",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center"
                            }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
                                <span style={{ fontSize: 11, fontWeight: 800, color: "var(--tx2)" }}>{reason}</span>
                              </div>
                              <span style={{ fontSize: 13, fontWeight: 900, color }}>{count}</span>
                            </div>
                          );
                        })}
                        {(!universeStats?.excluded_reasons || Object.keys(universeStats.excluded_reasons).length === 0) && (
                          <div style={{ fontSize: 12, color: "var(--tx3)", textAlign: "center", padding: 32, border: "2px dashed var(--bdr)", borderRadius: 16 }}>
                            {t("genetic.all_healthy")}
                          </div>
                        )}
                      </div>

                      <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--bdr)", fontSize: 9, color: "var(--tx3)", display: "flex", alignItems: "center", gap: 6 }}>
                        <IconInfo size={10} />
                        <span>{t("genetic.diagnostics_note")}</span>
                      </div>
                   </div>
                </div>
              </div>
            ) : (
              <div style={{ height: "60vh", display: "flex", flexDirecton: "column", alignItems: "center", justifyContent: "center", border: "2px dashed var(--bdr)", borderRadius: 32 }}>
                <div style={{ textAlign: "center" }}>
                  <IconTarget size={48} color="var(--bg4)" style={{ marginBottom: 16 }} />
                  <div style={{ fontSize: 14, fontWeight: 900, color: "var(--tx3)" }}>{t("genetic.select_model")}</div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
      
      {/* Diagnostics Bar */}
      {(lastDiagnostics || universeAudit) && (
        <div style={{ 
          position: "fixed", 
          bottom: 0, 
          left: 0, 
          right: 0, 
          background: "var(--bg2)", 
          borderTop: "1px solid var(--bdr)", 
          backdropFilter: "blur(10px)",
          height: diagnosticsExpanded ? 350 : 30,
          transition: "height 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          zIndex: 100,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }}>
          <div 
            onClick={() => setDiagnosticsExpanded(!diagnosticsExpanded)}
            style={{ 
              height: 30, 
              minHeight: 30,
              display: "flex", 
              alignItems: "center", 
              justifyContent: "space-between", 
              padding: "0 20px", 
              cursor: "pointer",
              borderBottom: diagnosticsExpanded ? "1px solid var(--bdr)" : "none"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ fontSize: 9, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1.5 }}>{t("genetic.diagnostics")}</div>
              {lastDiagnostics && (
                <>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: lastDiagnostics.is_converged ? "var(--gr)" : "var(--rd)" }} />
                  <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx2)" }}>
                    OPTIMIZER: {t("genetic.diag_optimizer", { ms: lastDiagnostics.duration_ms })} • {lastDiagnostics.iterations} ITER
                  </span>
                </>
              )}
              {universeAudit && (
                <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx2)", marginLeft: lastDiagnostics ? 12 : 0 }}>
                  {t("genetic.diag_universe", { eligible: universeAudit.eligible, total: universeAudit.total })}
                </span>
              )}
            </div>
            {diagnosticsExpanded ? <IconDown size={14} color="var(--tx3)" /> : <IconUp size={14} color="var(--tx3)" />}
          </div>
          
          <div style={{ 
            flex: 1,
            padding: "20px",
            opacity: diagnosticsExpanded ? 1 : 0,
            transition: "opacity 0.2s ease",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            gap: 20
          }}>
            {/* Optimizer Row */}
            {lastDiagnostics && (
              <div style={{ display: "flex", alignItems: "center", gap: 24, paddingBottom: 20, borderBottom: "1px solid var(--bdr)" }}>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>{t("genetic.matrix_dims")}</span>
                  <span style={{ fontSize: 10, fontWeight: 900, color: "var(--tx)" }}>{lastDiagnostics.matrix_dim}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>{t("genetic.status")}</span>
                  <span style={{ fontSize: 10, fontWeight: 900, color: lastDiagnostics.is_converged ? "var(--gr)" : "var(--rd)" }}>
                    {lastDiagnostics.is_converged ? t("genetic.converged") : t("genetic.failed_convergence")}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>{t("genetic.memory")}</span>
                  <span style={{ fontSize: 10, fontWeight: 900, color: "var(--tx)" }}>{t("genetic.stable")}</span>
                </div>
              </div>
            )}

            {/* Universe Audit Section */}
            {universeAudit && (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12, overflow: "hidden" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1 }}>{t("genetic.excluded_assets", { count: universeAudit.excluded.length })}</div>
                  <div style={{ position: "relative", width: 250 }}>
                    <IconSearch size={12} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--tx3)" }} />
                    <input 
                      type="text"
                      placeholder={t("genetic.search_excluded")}
                      value={auditSearch}
                      onChange={e => setAuditSearch(e.target.value)}
                      style={{ 
                        width: "100%", height: 28, background: "var(--bg3)", border: "1px solid var(--bdr)", 
                        borderRadius: 8, paddingLeft: 30, fontSize: 10, color: "var(--tx)" 
                      }}
                    />
                    {auditSearch && (
                      <IconX 
                        size={12} 
                        onClick={() => setAuditSearch("")}
                        style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: "var(--tx3)", cursor: "pointer" }} 
                      />
                    )}
                  </div>
                </div>

                <div style={{ flex: 1, overflowY: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 8, paddingRight: 4 }}>
                  {filteredExcluded.map(x => (
                    <div key={x.ticker} style={{ 
                      background: "var(--bg3)", padding: "10px 12px", borderRadius: 10, border: "1px solid var(--bdr)",
                      display: "flex", flexDirection: "column", gap: 2
                    }}>
                      <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx)" }}>{x.ticker}</div>
                      <div style={{ fontSize: 9, color: "var(--tx3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={x.reason}>
                        {x.reason}
                      </div>
                    </div>
                  ))}
                  {filteredExcluded.length === 0 && (
                    <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: 40, color: "var(--tx3)", fontSize: 11 }}>
                      {t("genetic.no_results", { query: auditSearch })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .genetic-grid { display: grid; grid-template-columns: 300px 1fr; gap: 32px; }
        .genetic-params-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
        .btn-disabled { opacity: 0.5; cursor: not-allowed; filter: grayscale(1); }
        .btn-cy { background: var(--cy); color: var(--bg); border: none; }
        .btn-cy:hover { filter: brightness(0.9); }
        .pill.cy { background: rgba(0, 255, 255, 0.1); color: var(--cy); border: 1px solid var(--cy); }
        .spin-ico { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @media (max-width: 1100px) {
          .genetic-grid { grid-template-columns: 1fr; }
          .genetic-params-grid { grid-template-columns: 1fr; }
        }
      `}</style>
    </PageWrapper>
  );
}
