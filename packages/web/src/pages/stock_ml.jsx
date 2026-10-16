import { useState, useEffect, useMemo } from "react";
import { apiFetch, useMacro } from "../finance/useApi.js";
import { getSignalVariant } from "../finance/constants.js";
import { PageWrapper } from "../animations.jsx";
import { IconRefresh, IconInfo, IconBarChart, IconSearch, IconInsight } from "../icons.jsx";
import { Skeleton } from "../components.jsx";

// ── Skeleton ───────────────────────────────────────────────────────────────
function StockMLSkeleton() {
  return (
    <>
      <div className="sg" style={{ gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 }}>
        {[1,2,3].map(i => <div key={i} className="sc"><Skeleton h={10} mb={10} w="40%" /><Skeleton h={24} w="60%" /></div>)}
      </div>
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: 20 }}><Skeleton h={20} w={100} /></div>
        {[1,2,3,4,5,6].map(i => (
          <div key={i} style={{ padding: "12px 20px", display:"flex", gap: 15, borderTop: "1px solid var(--bdr)" }}>
            <Skeleton h={15} w="20%" />
            <Skeleton h={15} w="15%" />
            <Skeleton h={15} w="15%" />
            <Skeleton h={20} w="15%" style={{marginLeft:"auto"}} />
            <Skeleton h={15} w="10%" />
          </div>
        ))}
      </div>
    </>
  );
}

export default function StockML() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/ml-stocks/summary");
      setData(res || []);
    } catch (err) {
      console.error(err);
      setError(err?.message || String(err) || "Failed to load ML predictions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const filteredData = useMemo(() => {
    if (!data) return [];
    if (!search) return data;
    const s = search.toUpperCase();
    return data.filter(r => r.ticker?.includes(s));
  }, [data, search]);

  const SignalBadge = ({ signal }) => {
    const variant = getSignalVariant(signal);
    return (
      <div className={`pill ${variant}`} style={{ minWidth: 80, justifyContent: "center", fontWeight: 900 }}>
        {String(signal || "").toUpperCase()}
      </div>
    );
  };

  return (
    <PageWrapper title="SHPIS Engine">
      <h1 className="sr-only">ML Stock Predictor — AI Signal &amp; Prediction Engine</h1>
      {loading && data.length === 0 ? (
        <StockMLSkeleton />
      ) : error ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 320, gap: 16, border: "1px dashed rgba(239,68,68,.4)", borderRadius: 20, padding: 36, background: "rgba(239,68,68,.05)", margin: "20px 0" }}>
          <div style={{ fontSize: 36 }}>⚠️</div>
          <div style={{ fontWeight: 900, fontSize: 16, color: "var(--rd)", letterSpacing: 1 }}>ML PREDICTION ENGINE ERROR</div>
          <div style={{ fontSize: 12, color: "var(--tx2)", textAlign: "center", maxWidth: 460, lineHeight: 1.6 }}>
            {typeof error === "string" ? error : error?.message || String(error)}
          </div>
          <div style={{ fontSize: 11, color: "var(--tx3)", textAlign: "center", maxWidth: 440 }}>
            Pastikan server API backend aktif di <code>http://localhost:8444</code> dan model XGBoost telah dilatih via CLI menu 6.
          </div>
          <button className="btn btn-g btn-s" onClick={loadData} style={{ marginTop: 8 }}>
            <IconRefresh size={14} style={{ marginRight: 6 }} /> Coba Lagi
          </button>
        </div>
      ) : data.length === 0 ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 280, gap: 14, border: "1px dashed var(--bdr)", borderRadius: 20, padding: 32, background: "var(--bg2)", margin: "20px 0" }}>
          <IconBarChart size={40} color="var(--tx3)" />
          <div style={{ fontWeight: 800, fontSize: 14, color: "var(--tx)" }}>Belum Ada Model ML Aktif</div>
          <div style={{ fontSize: 12, color: "var(--tx3)", textAlign: "center", maxWidth: 420 }}>
            Tidak ada prediksi ML yang tersimpan. Jalankan latihan model di CLI atau pastikan <code>stock-ml</code> service aktif.
          </div>
          <button className="btn btn-p btn-s" onClick={loadData}>
            <IconRefresh size={14} style={{ marginRight: 6 }} /> Refresh Data
          </button>
        </div>
      ) : (
        <>
          {error && (
            <div style={{ padding: "10px 16px", borderRadius: 12, background: "rgba(239,68,68,.1)", border: "1px solid rgba(239,68,68,.3)", color: "var(--rd)", fontSize: 12, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>⚠️ <strong>Gagal Memperbarui:</strong> {typeof error === "string" ? error : error?.message || String(error)}</span>
              <button className="btn btn-s" style={{ background: "transparent", color: "var(--rd)", border: "none" }} onClick={loadData}>Coba Lagi</button>
            </div>
          )}
          <div className="sg" style={{ gridTemplateColumns: "repeat(5, 1fr)", gap: 16, marginBottom: 20 }}>
            <div className="sc net" style={{ padding: 16 }}>        
              <div className="sc-lbl">MODELS</div>
              <div className="sc-val">{data.length}</div>
            </div>
            <div className="sc net" style={{ padding: 16, borderLeft: "4px solid var(--cy)" }}>
              <div className="sc-lbl">AVG PRECISION</div>
              <div className="sc-val" style={{ color: "var(--cy)" }}>
                {(data.reduce((acc, r) => acc + (r.precision || 0), 0) / (data.length || 1) * 100).toFixed(1)}%
              </div>
            </div>
            <div className="sc net" style={{ padding: 16, borderLeft: "4px solid var(--gr)" }}>
              <div className="sc-lbl">TOTAL SIGNALS</div>
              <div className="sc-val" style={{ color: "var(--gr)" }}>
                {data.reduce((acc, r) => acc + (r.n_signals || 0), 0).toLocaleString()}
              </div>
            </div>
            <div className="sc net" style={{ padding: 16, borderLeft: "4px solid var(--yl)" }}>
              <div className="sc-lbl">LAST UPDATE</div>
              <div className="sc-val" style={{ color: "var(--yl)", fontSize: 14 }}>
                {(() => {
                  const ts = data[0]?.timestamp || data[0]?.updated_at || data[0]?.date;
                  if (!ts) return "--:--";
                  if (ts.includes("T")) return ts.split("T")[1]?.slice(0, 8) || ts;
                  if (ts.includes(" ")) return ts.split(" ")[1] || ts;
                  return ts;
                })()}
              </div>
            </div>
            <button className="btn btn-p" style={{ height: "100%", borderRadius: 12, fontWeight: 900 }} onClick={loadData} disabled={loading}>
               {loading ? <IconRefresh size={16} style={{ animation: "comp-spin 1s linear infinite" }} /> : "SYNC DATA"}
            </button>
          </div>
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ paddingLeft: 20 }}>Asset</th>
                  <th>Acc.</th>
                  <th>Precision</th>
                  <th style={{ textAlign: "center" }}>Signal</th>
                  <th style={{ paddingRight: 20, textAlign: "right" }}>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map(r => (
                  <tr key={r.ticker}>
                    <td style={{ paddingLeft: 20 }}><b>{r.ticker}</b></td>
                    <td style={{ fontSize: 11 }}>{(r.global_acc * 100).toFixed(1)}%</td>
                    <td style={{ color: "var(--cy)", fontWeight: 800 }}>{(r.precision * 100).toFixed(1)}%</td>
                    <td style={{ textAlign: "center" }}><SignalBadge signal={r.signal} /></td>
                    <td style={{ paddingRight: 20, textAlign: "right", fontFamily: "var(--mono)", width: 120 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
                        <span>{(r.prob * 100).toFixed(1)}%</span>
                        <div className="prog-wrap" style={{ width: 40, height: 4, borderRadius: 2 }}>
                           <div className="prog-fill" style={{ 
                             width: `${(r.prob || 0) * 100}%`, 
                             background: r.prob > 0.7 ? "var(--gr)" : r.prob > 0.5 ? "var(--cy)" : "var(--yl)" 
                           }} />
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 16, padding: 16, background: "var(--bg3)", borderRadius: 12, fontSize: 11, color: "var(--tx3)", lineHeight: 1.5 }}>
             <IconInsight size={14} style={{ marginRight: 6, verticalAlign: "middle", color: "var(--cy)" }} />
             <strong>Model Confidence (SoftMax Probability):</strong> This value represents the <strong>Class Probability</strong> calculated via a SoftMax function. 
             It indicates the model's mathematical certainty (0-100%) that the current market features align with historical patterns for the predicted signal (BUY, SELL, or NEUTRAL). 
             A confidence above 70% triggers a "SNIPER" classification.
          </div>
        </>
      )}
    </PageWrapper>
  );
}
