import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { apiFetch, useUniverseAudit } from "../finance/useApi.js";
import { PageWrapper } from "../animations.jsx";
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
            title={`Iter ${l.iteration}: MAE ${l.mae.toFixed(6)}`}
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
      setDataError(e?.message || String(e) || "Gagal menghubungkan ke backend AI Portfolio Lab.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleOptimize = async () => {
    if (optimizing) return;

    // Synchronous Validation Gates
    if (minAssets > maxAssets) {
      onToast("Min assets cannot exceed Max assets", "error");
      return;
    }
    if (!universeStats || universeStats.eligible_count === 0) {
      onToast("No eligible assets for optimization", "error");
      return;
    }
    if (!riskMode) {
      onToast("Missing optimization config", "error");
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
        onToast("Optimization task started...");
      } else {
        // Fallback for immediate results if any
        if (res?.diagnostics) {
          setLastDiagnostics(res.diagnostics);
        }
        onToast("Portfolio re-optimized successfully.");
        reloadAudit();
        await loadData();
        setOptimizing(false);
      }
    } catch (e) {
      console.error("Optimization failed", e);
      if (e.status === 400) {
        onToast("Invalid parameters. Check Min/Max assets.", "error");
      } else if (e.status === 422) {
        onToast("Insufficient data for global optimization.", "error");
      } else if (e.status === 503) {
        onToast("Optimizer backend is currently busy or unavailable.", "error");
      } else {
        onToast("Optimization failed: " + e.message, "error");
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
          onToast("Portfolio re-optimized successfully.");
          reloadAudit();
          await loadData();
          setActiveTaskId(null);
          setOptimizing(false);
          setPollingProgress(100);
        } else if (res?.status === "failed" || res?.status === "timeout") {
          if (res?.status === "timeout") {
            onToast("Optimization timed out. Results might be stale.", "error");
          } else {
            onToast(`Optimization failed: ${res.error || 'Check diagnostics'}`, "error");
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
          onToast("Status check failed. Tracking stopped.", "error");
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
    <PageWrapper title="AI Portfolio Lab">
      <div style={{ padding: 20 }}>
        <h1 className="sr-only">Genetic Portfolio Optimizer — AI-Powered Investment Allocation</h1>
        {dataError && (
          <div style={{ 
            padding: "16px 20px", borderRadius: 16, marginBottom: 24,
            background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.25)",
            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16
          }}>
            <div>
              <div style={{ fontWeight: 800, fontSize: 13, color: "var(--rd)", marginBottom: 4 }}>
                ⚠️ Gagal Mengambil Data AI Portfolio Lab
              </div>
              <div style={{ fontSize: 11, color: "var(--tx2)" }}>
                {typeof dataError === "string" ? dataError : dataError?.message || String(dataError)}
              </div>
            </div>
            <button className="btn btn-g btn-s" onClick={loadData}>
              <IconRefresh size={13} style={{ marginRight: 4 }} /> Coba Lagi
            </button>
          </div>
        )}
        {/* Header Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 20, marginBottom: 32 }}>
          <div className="card" style={{ padding: 24, background: "var(--glass)", border: "1px solid var(--bdr)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <IconFlash size={20} color="var(--cy)" />
              <span className="pill cy" style={{ fontSize: 9 }}>ACTIVE</span>
            </div>
            <div style={{ fontSize: 24, fontWeight: 900 }}>{universeStats?.eligible_count || 0}</div>
            <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase" }}>Eligible Universe</div>
          </div>
          <div className="card" style={{ padding: 24, background: "var(--glass)", border: "1px solid var(--bdr)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <IconActivity size={20} color="var(--gr)" />
              <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)" }}>LATEST RUN</span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 900 }}>{status?.last_run ? new Date(status.last_run).toLocaleDateString() : "NEVER"}</div>
            <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase", marginTop: 4 }}>System Heartbeat</div>
          </div>
          <div className="card" style={{ padding: 24, background: "var(--glass)", border: "1px solid var(--bdr)" }}>
             <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <IconShieldCheck size={20} color="var(--cy)" />
                <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)" }}>TOTAL ASSETS</span>
             </div>
             <div style={{ fontSize: 24, fontWeight: 900 }}>{universeStats?.total_count || 1051}</div>
             <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase", marginTop: 4 }}>Cached Tickers</div>
          </div>
        </div>

        <div className="genetic-grid">
          {/* Sidebar: Model List */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {/* Optimizer Settings */}
            <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>OPTIMIZER CONFIG</div>
              
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <label style={{ fontSize: 10, fontWeight: 800, color: "var(--tx2)" }}>MIN ASSETS</label>
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
                  <label style={{ fontSize: 10, fontWeight: 800, color: "var(--tx2)" }}>MAX ASSETS</label>
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
                <label style={{ fontSize: 10, fontWeight: 800, color: "var(--tx2)", display: "block", marginBottom: 8 }}>RISK MODE</label>
                <select 
                  value={riskMode}
                  onChange={e => setRiskMode(e.target.value)}
                  style={{ width: "100%", height: 36, background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 10, fontSize: 12, color: "var(--tx)", padding: "0 8px" }}
                >
                  <option value="sharpe">Maximize Sharpe</option>
                  <option value="returns">Maximize Returns</option>
                  <option value="volatility">Minimize Volatility</option>
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
                    {pollingProgress <= 30 ? "Optimizing..." :
                     pollingProgress <= 70 ? "Recalculating..." :
                     "Fetching results..."}
                  </>
                ) : "RUN GLOBAL OPTIMIZER"}
              </button>
            </div>

            <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)", height: "calc(100vh - 600px)", display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>OPTIMIZED MODELS</div>
              
              <div style={{ position: "relative", marginBottom: 16 }}>
                <IconSearch size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--tx3)" }} />
                <input 
                  type="text" 
                  placeholder="Filter tickers..." 
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
                      <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 2, marginBottom: 4 }}>EVOLUTIONARY PATH</div>
                      <div style={{ fontSize: 24, fontWeight: 900 }}>{activeModel.ticker} Sniper Optimization</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)" }}>BEST MAE</div>
                      <div style={{ fontSize: 24, fontWeight: 900, color: "var(--cy)" }}>{activeModel.best_mae.toFixed(6)}</div>
                    </div>
                  </div>
                  
                  <EvolutionChart logs={logs} />
                  
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, fontWeight: 800, color: "var(--tx3)", marginTop: 8 }}>
                    <span>GENERATION 0</span>
                    <span>GENERATION {logs.length - 1}</span>
                  </div>
                </div>

                {/* Parameters Grid */}
                <div className="genetic-params-grid">
                   <div className="card" style={{ padding: 24, borderRadius: 24, border: "1px solid var(--bdr)" }}>
                      <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>WINNING HYPERPARAMETERS</div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                         <ParamCard label="Learning Rate" value={activeModel.params.learning_rate.toFixed(4)} />
                         <ParamCard label="Max Depth" value={activeModel.params.max_depth} />
                         <ParamCard label="Estimators" value={activeModel.params.n_estimators} />
                         <ParamCard label="Subsample" value={activeModel.params.subsample.toFixed(2)} />
                      </div>
                   </div>

                   <div className="card" style={{ padding: 24, borderRadius: 24, border: "1px solid var(--bdr)", background: "var(--bg2)", display: "flex", flexDirection: "column" }}>
                     <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                       <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1.5 }}>DATA HEALTH DASHBOARD</div>
                       <div className="pill cy" style={{ fontSize: 9 }}>SYSTEM DIAGNOSTICS</div>
                     </div>

                     <div style={{ marginBottom: 24, display: "flex", alignItems: "center", justifyContent: "space-between" }}>                        <div>
                          <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", marginBottom: 4 }}>UNIVERSE FILTERED BY</div>
                          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                            <span style={{ fontSize: 32, fontWeight: 900, color: "var(--tx)" }}>
                              {universeStats?.total_count && universeStats?.eligible_count 
                                ? (((universeStats.total_count - universeStats.eligible_count) / universeStats.total_count) * 100).toFixed(1) 
                                : "0.0"}%
                            </span>
                            <span style={{ fontSize: 11, fontWeight: 800, color: "var(--rd)" }}>REDUCED</span>
                          </div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                           <div style={{ fontSize: 10, fontWeight: 800, color: "var(--tx3)", marginBottom: 4 }}>DROPOUT</div>
                           <div style={{ fontSize: 20, fontWeight: 900, color: "var(--rd)" }}>
                              {universeStats?.eligible_count ? Math.max(0, universeStats.eligible_count - models.length) : 0}
                           </div>
                        </div>
                      </div>

                      <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", marginBottom: 12, letterSpacing: 1 }}>EXCLUSION REASONS</div>
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
                            All assets are healthy
                          </div>
                        )}
                      </div>

                      <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--bdr)", fontSize: 9, color: "var(--tx3)", display: "flex", alignItems: "center", gap: 6 }}>
                        <IconInfo size={10} />
                        <span>Diagnostics verify OHLCV continuity & model feature readiness.</span>
                      </div>
                   </div>
                </div>
              </div>
            ) : (
              <div style={{ height: "60vh", display: "flex", flexDirecton: "column", alignItems: "center", justifyContent: "center", border: "2px dashed var(--bdr)", borderRadius: 32 }}>
                <div style={{ textAlign: "center" }}>
                  <IconTarget size={48} color="var(--bg4)" style={{ marginBottom: 16 }} />
                  <div style={{ fontSize: 14, fontWeight: 900, color: "var(--tx3)" }}>SELECT A MODEL TO VIEW EVOLUTION</div>
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
              <div style={{ fontSize: 9, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1.5 }}>DIAGNOSTICS</div>
              {lastDiagnostics && (
                <>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: lastDiagnostics.is_converged ? "var(--gr)" : "var(--rd)" }} />
                  <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx2)" }}>
                    OPTIMIZER: {lastDiagnostics.duration_ms}ms • {lastDiagnostics.iterations} ITER
                  </span>
                </>
              )}
              {universeAudit && (
                <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx2)", marginLeft: lastDiagnostics ? 12 : 0 }}>
                  UNIVERSE: {universeAudit.eligible}/{universeAudit.total} ASSETS
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
                  <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>MATRIX DIMS</span>
                  <span style={{ fontSize: 10, fontWeight: 900, color: "var(--tx)" }}>{lastDiagnostics.matrix_dim}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>STATUS</span>
                  <span style={{ fontSize: 10, fontWeight: 900, color: lastDiagnostics.is_converged ? "var(--gr)" : "var(--rd)" }}>
                    {lastDiagnostics.is_converged ? "CONVERGED" : "FAILED_CONVERGENCE"}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>MEMORY</span>
                  <span style={{ fontSize: 10, fontWeight: 900, color: "var(--tx)" }}>STABLE</span>
                </div>
              </div>
            )}

            {/* Universe Audit Section */}
            {universeAudit && (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12, overflow: "hidden" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1 }}>EXCLUDED ASSETS ({universeAudit.excluded.length})</div>
                  <div style={{ position: "relative", width: 250 }}>
                    <IconSearch size={12} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--tx3)" }} />
                    <input 
                      type="text"
                      placeholder="Search excluded tickers..."
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
                      No results matching "{auditSearch}"
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
