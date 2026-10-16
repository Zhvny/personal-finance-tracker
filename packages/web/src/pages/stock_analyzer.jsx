import { useState, useEffect, useMemo, useCallback, useRef, memo, Component } from "react";
import { apiFetch, useDebounce, useCacheFetch, useWebSocket } from "../finance/useApi.js";
import { TickerProvider, useTicker } from "../finance/TickerContext.jsx";
import { getSignalVariant } from "../finance/constants.js";
import { PageWrapper } from "../animations.jsx";
import { 
  IconUp, IconDown, IconRefresh, IconSearch, IconBarChart, 
  IconPieChart, IconInfo, IconActivity, IconTarget, IconAlertCircle,
  IconShieldCheck, IconFlash, IconFilter, IconArrowRight, IconMenuOpen,
  IconMore, IconSettings, IconStar
} from "../icons.jsx";
import { Skeleton } from "../components.jsx";
import { useButterflyBenchmark } from "../hooks/useButterflyBenchmark.js";
import ButterflyMap from "../components/ButterflyMap.jsx";
import ButterflyErrorBoundary from "../components/ButterflyErrorBoundary.jsx";

// â”€â”€â”€ Constants & Utils â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const getSym = (t) => (String(t || "").endsWith(".JK") || String(t || "").includes("IDR")) ? "Rp" : "$";
const fmtPrice = (val, t) => {
  const s = getSym(t);
  const v = Number(val || 0);
  if (v === 0) return "---";
  if (s === "Rp") return `Rp${v.toLocaleString("id-ID", { minimumFractionDigits: 0 })}`;
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const fmt = (val, dec = 2) => {
  if (val === null || val === undefined) return "---";
  if (typeof val === 'object') return "---"; // Still returning --- for consistency but logic is now separated
  const v = Number(val);
  return isNaN(v) ? "---" : v.toFixed(dec);
};



// CRITICAL UI FAILSAFE: Ensures forecast values shown to user are always in realistic ranges.
const clampForecast = (val, maxRange = 0.40) => {
  let v = Number(val || 0);
  // If backend sent Ribuan Persen (e.g. 5.5 instead of 0.055), auto-normalize
  if (Math.abs(v) > 1.0) v = v / 100.0;
  // Strict clipping to realistic financial boundaries
  return Math.max(-maxRange, Math.min(maxRange, v));
};

const getSignalColor = (sig) => {
  const v = getSignalVariant(sig);
  if (v === "g") return "var(--gr)";
  if (v === "r") return "var(--rd)";
  return "var(--yl)";
};

// â”€â”€â”€ Shared Components â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const ScoreGauge = ({ score, size = 100 }) => {
  const pct = (score / 10) * 100;
  const color = score >= 7.5 ? "var(--gr)" : score >= 5.5 ? "var(--cy)" : score > 0 ? "var(--yl)" : "var(--rd)";
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
        <circle cx="18" cy="18" r="15.9155" fill="none" stroke="var(--bg4)" strokeWidth="3" />
        <circle cx="18" cy="18" r="15.9155" fill="none" stroke={color} strokeWidth="3" 
          strokeDasharray={`${pct}, 100`} strokeLinecap="round" 
          style={{ transition: "stroke-dasharray 0.6s ease" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: size * 0.24, fontWeight: 900, color: "var(--tx)" }}>{fmt(score, 1)}</span>
        <span style={{ fontSize: size * 0.09, color: "var(--tx3)", textTransform: "uppercase", fontWeight: 700 }}>Score</span>
      </div>
    </div>
  );
};

const PriceStructure = memo(({ data }) => {
  const isBull = data.signal.includes("BUY") || data.signal.includes("BULL");
  const isBear = data.signal.includes("SELL") || data.signal.includes("BEAR");
  const variant = isBull ? "bullish" : isBear ? "bearish" : "neutral";

  // Derived levels for the ladder
  const levels = useMemo(() => {
    const p = data.price;
    const raw = [
      { id: "r2",  label: "Resistance 2",   val: data.resistance * 1.05, type: "res", isOuter: true },
      { id: "r1",  label: "Resistance",     val: data.resistance,       type: "res" },
      { id: "tp2", label: "Take Profit 2",  val: data.take_profit * 1.03, type: "tp" },
      { id: "tp1", label: "Take Profit 1",  val: data.take_profit,       type: "tp" },
      { id: "p",   label: "Current Price",  val: p,                      type: "price", isHero: true },
      { id: "sl1", label: "Stop Loss 1",    val: data.stop_loss,         type: "sl" },
      { id: "sl2", label: "Stop Loss 2",    val: data.stop_loss * 0.97,  type: "sl" },
      { id: "s1",  label: "Support 1",      val: data.support,           type: "sup" },
      { id: "s2",  label: "Support 2",      val: data.support * 0.95,    type: "sup", isOuter: true },
    ];
    // Sort descending: Highest price at top
    return raw.sort((a, b) => b.val - a.val);
  }, [data]);

  return (
    <div className="stk-ladder">
      <div className="stk-ladder-version">QUANT_LADDER_PRO_V5</div>
      
      {levels.map((l) => {
        const nodeColor = l.type === "res" ? "var(--rd)" : l.type === "sup" ? "var(--gr)" : l.type === "tp" ? "var(--cy)" : l.type === "sl" ? "var(--rd)" : "var(--tx3)";
        
        return (
          <div key={l.id} className={`stk-ladder-node ${l.isHero ? "hero-wrap" : "outer"}`}>
            {l.isHero ? (
              <div className={`stk-ladder-hero ${variant}`}>
                <div className="pulse-ring" style={{ color: getSignalColor(data.signal) }} />
                <div className="stk-ladder-label">LATEST PRICE FOCUS</div>
                <div className="stk-ladder-price">
                  {fmtPrice(l.val, data.ticker)}
                </div>
                <div className="stk-ladder-hero-badge" style={{ color: getSignalColor(data.signal), border: `1px solid ${getSignalColor(data.signal)}` }}>
                  {data.signal}
                </div>
              </div>
            ) : (
              <div className="stk-ladder-content" style={{ opacity: l.isOuter ? 0.35 : 1 }}>
                <div className="stk-ladder-label" style={{ color: nodeColor }}>{l.label}</div>
                <div className="stk-ladder-price" style={{ fontSize: l.isOuter ? 14 : 18 }}>
                  {fmtPrice(l.val, data.ticker)}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
});

// â”€â”€â”€ Custom Hooks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function useInterval(callback, delay) {
  const savedCallback = useRef();
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);
  useEffect(() => {
    function tick() {
      savedCallback.current();
    }
    if (delay !== null) {
      let id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}

// â”€â”€â”€ Skeletons â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function StockAnalyzerSkeleton({ isMobile }) {
  if (isMobile) {
    return (
      <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
        <Skeleton h={40} mb={10} />
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display:"flex", justifyContent:"space-between" }}>
            <div style={{ width:"60%" }}><Skeleton h={10} mb={8} w="30%" /><Skeleton h={30} /></div>
            <Skeleton h={30} w={60} r={15} />
          </div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
          <Skeleton h={80} />
          <Skeleton h={80} />
        </div>
        <Skeleton h={150} />
      </div>
    );
  }
  return (
    <div className="stk-main-grid">
      <div>
        <div className="card" style={{ padding: 15, marginBottom: 16 }}>
          <Skeleton h={38} mb={10} />
          <Skeleton h={34} />
        </div>
        <div className="card" style={{ padding: 15 }}>
          {[1,2,3,4,5].map(i => <Skeleton key={i} h={50} mb={8} />)}
        </div>
      </div>
      <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
        <div className="card" style={{ padding: 32 }}>
          <div style={{ display:"flex", justifyContent:"space-between" }}>
            <div style={{ width:"50%" }}><Skeleton h={48} mb={10} w="40%" /><Skeleton h={30} w="60%" /></div>
            <Skeleton h={110} w={110} r={55} />
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:20, marginTop:30 }}>
            {[1,2,3,4].map(i => <div key={i}><Skeleton h={10} mb={6} w="40%" /><Skeleton h={20} /></div>)}
          </div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:20 }}>
          <Skeleton h={120} />
          <Skeleton h={120} />
          <Skeleton h={120} />
        </div>
      </div>
    </div>
  );
}

// â”€â”€â”€ Main Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const WhaleActivity = memo(({ ticker, assetType }) => {
  const [whale, setWhale] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    let ignore = false;
    setLoading(true);
    apiFetch(`/stocks/whale/${ticker}?asset_type=${assetType || 'stock'}`)
      .then(res => {
        if (!ignore) setWhale(res);
      })
      .catch(e => {
        if (!ignore) console.error("Whale API failed", e);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, [ticker, assetType]);

  if (!whale && !loading) return null;
  if (whale?.error) {
    return (
      <div className="card" style={{ padding: 14, background: "rgba(239,68,68,.05)", borderRadius: 16, border: "1px dashed rgba(239,68,68,.3)", marginBottom: 16, fontSize: 11, color: "var(--rd)" }}>
        ⚠️ Whale Activity Tracker: {typeof whale.error === "string" ? whale.error : whale.error?.message || "Service unavailable"}
      </div>
    );
  }

  const isWhale = whale?.is_whale_activity;
  const signal = whale?.signal || "NORMAL";

  return (
    <div className="card" style={{ 
      padding: 24, 
      background: "var(--bg2)", 
      borderRadius: 24, 
      border: `1px solid ${isWhale ? "var(--cy)" : "var(--bdr)"}`, 
      position: "relative", 
      overflow: "hidden",
      boxShadow: isWhale ? "0 0 20px rgba(0, 255, 255, 0.05)" : "none"
    }}>
       <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, position: "relative", zIndex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
             <IconActivity size={18} color={isWhale ? "var(--cy)" : "var(--tx3)"} />
             <span style={{ fontSize: 11, fontWeight: 900, color: "var(--tx2)", letterSpacing: 1 }}>WHALE ACTIVITY TRACKER</span>
          </div>
          {isWhale && (
            <div style={{ 
              fontSize: 9, fontWeight: 900, color: "var(--bg)", background: "var(--cy)", 
              padding: "4px 10px", borderRadius: 8, animation: "pulse 2s infinite" 
            }}>
              ACTIVE SIGNAL
            </div>
          )}
       </div>
       
       {loading ? <Skeleton h={80} r={16} /> : (
         <div style={{ position: "relative", zIndex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
               <div style={{ 
                  width: 48, height: 48, borderRadius: 12, background: "var(--bg3)", 
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: signal.includes("ACCUMULATION") ? "var(--gr)" : signal.includes("DISTRIBUTION") ? "var(--rd)" : "var(--tx3)"
               }}>
                  <IconFlash size={24} />
               </div>
               <div>
                  <div style={{ fontSize: 14, fontWeight: 900, color: isWhale ? "var(--cy)" : "var(--tx)" }}>
                    {signal.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--tx3)", fontWeight: 700 }}>
                    VOL RATIO: {fmt(whale?.vol_ratio, 2)}x â€¢ PRICE RANGE: {fmt(whale?.price_range_pct, 2)}%
                  </div>
               </div>
            </div>
            <div style={{ 
              fontSize: 11, color: "var(--tx2)", lineHeight: 1.5, background: "var(--bg3)", 
              padding: 12, borderRadius: 12, border: "1px solid var(--bdr)",
              fontFamily: "monospace"
            }}>
               {whale?.description?.replace(/\[.*?\]/g, "").replace(/âš ï¸ /g, "") || "No significant institutional activity detected in recent sessions."}
            </div>
         </div>
       )}
    </div>
  );
});

const InfoTooltip = ({ text }) => {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: "relative", display: "inline-flex", marginLeft: 6 }}>
      <IconInfo 
        size={10} 
        style={{ cursor: "help", color: "var(--tx3)", opacity: 0.6 }}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 10px)", left: "50%", transform: "translateX(-50%)",
          background: "var(--bg3)", color: "var(--tx)", padding: "10px 14px", borderRadius: 12,
          fontSize: 10, lineHeight: 1.5, width: 220, zIndex: 1000, pointerEvents: "none",
          boxShadow: "0 8px 24px rgba(0,0,0,0.4)", border: "1px solid var(--bdr)",
          backdropFilter: "blur(10px)"
        }}>
          {text}
          <div style={{
            position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)",
            border: "6px solid transparent", borderTopColor: "var(--bdr)"
          }} />
        </div>
      )}
    </div>
  );
};

const getDxyExplanation = (val, assetType) => {
  const isNumeric = typeof val === "number" && isFinite(val);
  const absVal = isNumeric ? Math.abs(val) : null;
  const isDivergent = isNumeric && absVal > 1.5;
  const category = (assetType || "").toLowerCase() === "crypto" ? "crypto" : "equities";

  const definitions = {
    dxy: "DXY Divergence (DCDS): Measures statistical deviation between asset price and US Dollar Index. High values indicate a 'Breakdown' in standard liquidity rules.",
    usd: "Relasi USD Correlation: Standard benchmark where USD strength (DXY Up) typically forces capital out of risk assets (Equities/Crypto)."
  };

  const impacts = {
    equities: {
      normal: "Impact Makro: High inverse correlation. USD strength pressures global earnings and reduces valuation multiples.",
      divergent: "Regime Divergent: Stocks are ignoring USD strength (Irrational Exuberance) or ignoring USD weakness (Structural Risk)."
    },
    crypto: {
      normal: "Impact Makro: Pure liquidity proxy. BTC/ETH usually move inversely to USD; highly sensitive to global M2 supply changes.",
      divergent: "Regime Divergent: Crypto is decoupling. Could indicate independent bull run or imminent liquidity flush if USD spikes."
    }
  };

  const stateDesc = !isNumeric
    ? "Awaiting macro synchronization. Statistical engine is mapping correlation matrix."
    : isDivergent 
      ? "Breakdown Detected! Asset is decoupling from historical USD liquidity trends. Extreme volatility expected."
      : "Standard Regime. Asset is moving in sync with USD liquidity cycles. Negative correlation is intact.";

  const impactDesc = isDivergent ? impacts[category].divergent : impacts[category].normal;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div><span style={{ color: "var(--cy)", fontWeight: 800 }}>• DXY:</span> {definitions.dxy}</div>
      <div><span style={{ color: "var(--cy)", fontWeight: 800 }}>• USD:</span> {definitions.usd}</div>
      <div><span style={{ color: isDivergent ? "var(--rd)" : "var(--gr)", fontWeight: 800 }}>• STATE:</span> {stateDesc}</div>
      <div><span style={{ color: "var(--yl)", fontWeight: 800 }}>• IMPACT:</span> {impactDesc}</div>
    </div>
  );
};

const DXYStatus = ({ type }) => {
  if (type === "loading") return <div className="pulse">Macro data syncing</div>;
  if (type === "unavailable") return "DXY unavailable";
  if (type === "insufficient") return "Awaiting correlation data";
  if (type === "retrying") return <div className="pulse" style={{ opacity: 0.7 }}>Revalidating...</div>;
  return null;
};

const DXYPanel = ({ data, assetType }) => {
  const { ticker } = data;
  const { data: fetchRes, loading, error, isStale } = useCacheFetch(ticker ? `/stocks/analyze/${ticker}/dxy` : null);
  
  const dcds = fetchRes?.dcds;
  const backendStatus = typeof dcds === "object" ? dcds?.status : null;
  const val = typeof dcds === "number" ? dcds : null;

  const isInsufficient = backendStatus === "insufficient data";
  const isUnavailable = error || backendStatus === "unavailable";
  const isLoading = loading && !fetchRes;
  const isRetrying = loading && fetchRes;

  const isNumeric = typeof val === "number" && isFinite(val);
  const color = !isNumeric ? "var(--tx3)" : (val > 1.5 ? "var(--rd)" : val < -1.5 ? "var(--gr)" : "var(--cy)");
  const dxyExp = getDxyExplanation(val, assetType);

  return (
    <div style={{ background: "var(--bg3)", padding: 16, borderRadius: 16, border: "1px solid var(--bdr)", position: "relative" }}>     
      <div className="lbl" style={{ fontSize: 8, marginBottom: 6, display: "flex", alignItems: "center" }}>
        DXY Divergence
        <InfoTooltip text={dxyExp} />
      </div>
      <div style={{ fontSize: (isLoading || isUnavailable || isInsufficient || isRetrying || val === null) ? 10 : 16, fontWeight: 900, color }}>
        {isLoading ? (
          <DXYStatus type="loading" />
        ) : isUnavailable ? (
          <DXYStatus type="unavailable" />
        ) : isInsufficient ? (
          <DXYStatus type="insufficient" />
        ) : isRetrying ? (
          <DXYStatus type="retrying" />
        ) : val !== null ? (
          fmt(val, 2)
        ) : (
          "---"
        )}
      </div>
      {(isLoading || isRetrying) && (
        <div style={{ position: "absolute", bottom: 4, right: 8, fontSize: 7, opacity: 0.5 }}>BACKGROUND TASK</div>
      )}
    </div>
  );
};

const SenateAgent = memo(({ ticker, assetType }) => {
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    let ignore = false;
    setLoading(true);
    apiFetch(`/stocks/senate/${ticker}?asset_type=${assetType || "stock"}`)
      .then(data => {
        if (!ignore) setRes(data);
      })
      .catch(e => {
        if (!ignore) console.error("Senate Agent failed", e);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    
    return () => {
      ignore = true;
    };
  }, [ticker, assetType]);

  if (!loading && !res) return null;

  const getVoteColor = (v) => {
    if (v === "BUY") return "var(--gr)";
    if (v === "SELL") return "var(--rd)";
    return "var(--tx3)";
  };

  return (
    <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)" }}>
       <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
             <IconShieldCheck size={18} color="var(--ind-b)" />
             <span style={{ fontSize: 11, fontWeight: 900, color: "var(--tx2)", letterSpacing: 1 }}>AGENT SENATE CONSENSUS</span>
          </div>
          {res && (
            <span style={{ fontSize: 9, fontWeight: 800, color: getVoteColor(res.consensus), background: `rgba(${res.consensus === "BUY" ? "34, 197, 94" : res.consensus === "SELL" ? "239, 68, 68" : "156, 163, 175"}, 0.1)`, padding: "4px 10px", borderRadius: 12 }}>
               {res.consensus} ({Math.round(res.confidence * 100)}%)
            </span>
          )}
       </div>

       {loading ? (
         <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[1,2,3].map(i => <Skeleton key={i} h={60} r={16} />)}
         </div>
       ) : res ? (
         <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Top Consensus Detail */}
            <div style={{ padding: 16, background: "var(--bg3)", borderRadius: 20, border: "1px solid var(--bdr)", position: "relative", overflow: "hidden" }}>
               <div style={{ position: "absolute", top: 0, left: 0, height: "100%", width: 4, background: getVoteColor(res.consensus) }} />
               <div style={{ fontSize: 9, fontWeight: 900, color: "var(--tx3)", marginBottom: 8, textTransform: "uppercase" }}>Executive Summary</div>
               <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.5, color: "var(--tx2)" }}>
                  {res.opinions.find(o => o.agent.includes("Quant"))?.rationale || "Consensus reached based on multi-agent validation."}
               </div>
            </div>

            {/* Individual Agent Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
               {res.opinions.map(op => (
                 <div key={op.agent} style={{ padding: "12px 14px", background: "var(--bg3)", borderRadius: 16, border: "1px solid var(--bdr)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                       <span style={{ fontSize: 8, fontWeight: 900, color: "var(--tx3)" }}>{op.agent.toUpperCase()}</span>
                       <span style={{ fontSize: 8, fontWeight: 900, color: getVoteColor(op.vote) }}>{op.vote}</span>
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 700 }}>{Math.round(op.confidence * 100)}% Conf.</div>
                    <div style={{ height: 2, background: "var(--bg4)", marginTop: 6, borderRadius: 1 }}>
                       <div style={{ height: "100%", width: `${op.confidence * 100}%`, background: getVoteColor(op.vote), borderRadius: 1 }} />
                    </div>
                 </div>
               ))}
            </div>
            
            <div style={{ fontSize: 8, color: "var(--tx3)", textAlign: "center", opacity: 0.5 }}>
               SYSTEM REGIME: {res.market_regime.toUpperCase()} | AS OF {new Date(res.timestamp).toLocaleTimeString()}
            </div>
         </div>
       ) : (
         <div style={{ padding: 20, textAlign: "center", color: "var(--tx3)", fontSize: 11 }}>No consensus data available.</div>
       )}
    </div>
  );
});

const TickerSearch = memo(({ value, onChange, onAnalyze, isMobile }) => {
  return (
    <div style={{ position: "relative", flex: isMobile ? 1 : 'none', marginBottom: isMobile ? 0 : 24 }}>
      <IconSearch size={isMobile ? 20 : 16} style={{ 
        position: "absolute", 
        left: isMobile ? 16 : 14, 
        top: isMobile ? "50%" : 12, 
        transform: isMobile ? "translateY(-50%)" : "none",
        color: isMobile ? "var(--cy)" : "var(--tx3)" 
      }} />
      <input 
         type="text" 
         placeholder={isMobile ? "SEARCH TICKER..." : "QUICK SEARCH..."} 
         className="stk-search-input" 
         style={{ 
           paddingLeft: isMobile ? 48 : 42, 
           width: "100%", 
           height: isMobile ? 48 : 44,
           fontSize: isMobile ? 16 : 14,
           background: isMobile ? "var(--bg3)" : undefined,
           border: isMobile ? "1px solid var(--cy)" : undefined,
           borderRadius: isMobile ? 16 : undefined
         }} 
         value={value} 
         onChange={e => onChange(e.target.value.toUpperCase())} 
         onKeyDown={e => e.key === "Enter" && onAnalyze(value)} 
         autoFocus={isMobile}
      />
    </div>
  );
});

export default function StockAnalyzer() {
  return (
    <TickerProvider>
      <StockAnalyzerContent />
    </TickerProvider>
  );
}

function StockAnalyzerContent() {
  const { data, loading: tickerLoading, error, analyze, clearError } = useTicker();
  const [baseLoading, setBaseLoading] = useState(false);
  const [baseError, setBaseError] = useState(null);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebounce(searchInput, 400);
  
  const [watchlist, setWatchlist] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [mlMap, setMlMap] = useState({});
  const [macro, setMacro] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 800);

  // Filter States
  const [filterCat, setFilterCat] = useState("ALL");
  const [filterSignal, setFilterSignal] = useState("ALL");
  const [filterMinScore, setFilterMinScore] = useState(0);
  const [activePreset, setActivePreset] = useState("NONE");
  const [showFilters, setShowFilters] = useState(false);
  const [showSearch, setShowSearch] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 800);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Hybrid Debounce: Trigger analysis on debounced search
  useEffect(() => {
    if (debouncedSearch && debouncedSearch.length >= 2) {
      analyze(debouncedSearch);
    }
  }, [debouncedSearch, analyze]);

  const handleAnalyze = useCallback((t) => {
    const symbol = (typeof t === "string" ? t : searchInput).trim().toUpperCase();
    if (!symbol) return;
    if (isMobile) setShowFilters(false);
    analyze(symbol);
  }, [searchInput, isMobile, analyze]);

  const loadBaseData = useCallback(async (silent = false) => {
    try {
      if (!silent) {
        setBaseLoading(true);
        setBaseError(null);
      }
      const [w, ml, m, favs] = await Promise.all([
        apiFetch("/stocks/watchlist"),
        apiFetch("/ml-stocks/summary"),
        apiFetch("/stocks/macro"),
        apiFetch("/stocks/favorites")
      ]);
      
      let flatWatchlist = [];
      const seenTickers = new Set();

      if (w) {
        Object.entries(w).forEach(([cat, symbols]) => {
          (symbols || []).forEach(s => {
            if (!seenTickers.has(s)) {
              flatWatchlist.push({ ticker: s, category: cat });
              seenTickers.add(s);
            }
          });
        });
      }
      
      // Augment with ML data
      if (ml) {
        ml.forEach(item => {
          if (!seenTickers.has(item.ticker)) {
            flatWatchlist.push({ 
              ticker: item.ticker, 
              category: item.category || "US STOCKS"
            });
            seenTickers.add(item.ticker);
          }
        });
      }

      setWatchlist(flatWatchlist);
      setFavorites(favs || []);
      
      if (ml) {
        const mapping = {};
        ml.forEach(item => { mapping[item.ticker] = item; });
        setMlMap(mapping);
      }
      if (m) setMacro(m);

      // TRIGGER BATCH ANALYSIS (Live Market Data)
      if (flatWatchlist.length > 0) {
        const tickers = flatWatchlist.map(i => i.ticker);
        apiFetch("/stocks/analyze/batch", {
           method: "POST",
           body: JSON.stringify(tickers)
        }).then(results => {
          if (Array.isArray(results) && results.length > 0) {
             setMlMap(prev => {
               const newMap = { ...prev };
               results.forEach(res => {
                 if (res && res.ticker) {
                    newMap[res.ticker] = { ...(newMap[res.ticker] || {}), ...res };
                 }
               });
               return newMap;
             });
          }
        }).catch(e => console.error("Batch analysis failed", e));
      }
    } catch (e) { 
      console.error("Data load failed", e);
      setBaseError(e?.message || String(e) || "Gagal memuat data pasar Stock Analyzer.");
    } finally {
      if (!silent) setBaseLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBaseData();
  }, [loadBaseData]);

  useInterval(() => {
    console.log("Auto-refreshing...");
    loadBaseData(true);
  }, 300000);

  const toggleFavorite = async (tkr) => {
    const isFav = favorites.includes(tkr);
    const method = isFav ? "DELETE" : "POST";
    try {
      await apiFetch(`/stocks/favorites/${tkr}`, { method });
      setFavorites(prev => 
        isFav ? prev.filter(t => t !== tkr) : [...prev, tkr]
      );
    } catch (e) {
      console.error("Failed to toggle favorite:", e);
    }
  };

  // â”€â”€â”€ Unified Scoring & Filtering Engine â”€â”€â”€
  const filteredWatchlist = useMemo(() => {
    // 1. Calculate Composite Scores for all items
    const scoredList = watchlist.map(item => {
      const ml = mlMap[item.ticker];
      if (!ml) return { ...item, score: 0 };
      
      // Normalize Inputs (0.0 to 1.0)
      const acc = Math.max(0, Math.min(1, ml.global_acc || 0.5));
      const prec = Math.max(0, Math.min(1, ml.precision || 0.5));
      const prob = Math.max(0, Math.min(1, ml.prob || 0.5));
      
      // Trend: MA_20_R usually 0.95 to 1.05. Normalize to centered around 0.5
      const trendRaw = ml.trend || 1.0;
      const trendScore = Math.max(0, Math.min(1, (trendRaw - 0.9) / 0.2));
      
      // Risk: ATR_R usually 0.01 to 0.05. Lower is better for quality.
      const riskRaw = ml.risk || 0.02;
      const riskScore = Math.max(0, Math.min(1, 1 - (riskRaw / 0.08)));

      // Composite Weighted Score (0-100)
      const composite = (
        (acc * 0.25) + 
        (prec * 0.35) + 
        (prob * 0.20) + 
        (trendScore * 0.10) + 
        (riskScore * 0.10)
      ) * 100;

      return { ...item, ml, compositeScore: composite };
    });

    let list = scoredList;

    // 2. Apply Category Filter
    if (filterCat !== "ALL") {
      list = list.filter(i => i.category.toUpperCase().includes(filterCat.toUpperCase()));
    }

    // 3. Apply Preset/Signal Rules
    if (activePreset === "BEST") {
      list = list.filter(i => {
        if (!i.ml) return false;
        const sig = String(i.ml.signal || "").toUpperCase();
        const isBull = sig.includes("BUY") || sig.includes("BULL");
        // Strict BEST: Bullish + High Score + High Precision
        return isBull && i.compositeScore >= 65 && i.ml.precision >= 0.70;
      });
    } else if (activePreset === "SNIPER") {
      list = list.filter(i => i.ml && String(i.ml.signal || "").includes("SNIPER"));
    } else if (activePreset === "HIGH_ACC") {
      list = list.filter(i => i.ml && i.ml.global_acc >= 0.70);
    } else if (filterSignal !== "ALL") {
      list = list.filter(i => {
        if (!i.ml) return false;
        const sig = String(i.ml.signal || "").toUpperCase();
        if (filterSignal === "BULLISH") return sig.includes("BUY") || sig.includes("BULLISH");
        if (filterSignal === "BEARISH") return sig.includes("SELL") || sig.includes("BEARISH");
        return sig === filterSignal;
      });
    }

    // 4. Manual Accuracy Gate
    if (filterMinScore > 0 && activePreset === "NONE") {
      list = list.filter(i => i.ml && (i.ml.global_acc * 100) >= filterMinScore);
    }

    // 5. Phase 4: Sort by Favorite then by Composite Score
    return list.sort((a, b) => {
      const aFav = favorites.includes(a.ticker);
      const bFav = favorites.includes(b.ticker);
      if (aFav && !bFav) return -1;
      if (!aFav && bFav) return 1;
      return (b.compositeScore || 0) - (a.compositeScore || 0);
    });
  }, [watchlist, filterCat, filterSignal, filterMinScore, mlMap, activePreset, favorites]);

  // Quick Filter Presets
  const applyPreset = (type) => {
    if (activePreset === type) {
      setActivePreset("NONE");
      setFilterSignal("ALL");
      setFilterMinScore(0);
      return;
    }
    setActivePreset(type);
    if (type === "CLEAR") {
      setActivePreset("NONE");
      setFilterSignal("ALL");
      setFilterMinScore(0);
    }
  };

  return (
    <PageWrapper title="Quant Terminal">
      <h1 className="sr-only">Stock Analyzer — Quant Terminal for Market Research &amp; Analysis</h1>
      <div className="tab-toolbar" style={{ 
        padding: "0 20px", 
        marginBottom: 20, 
        borderBottom: "1px solid var(--bdr)", 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center", 
        position: "sticky", 
        top: 0, 
        zIndex: 1200, 
        background: "var(--bg)", 
        backdropFilter: "blur(20px)",
        minHeight: 72 
      }}>
         {isMobile && showSearch ? (
           <div style={{ flex: 1, display: "flex", gap: 12, alignItems: "center", animation: "stk-fade-in 0.3s ease" }}>
              <TickerSearch 
                 value={searchInput} 
                 onChange={setSearchInput} 
                 onAnalyze={handleAnalyze} 
                 isMobile={true} 
              />
              <button className="btn-icon" onClick={() => setShowSearch(false)} style={{ background:"var(--bg3)", borderRadius:12, width:48, height:48, display:"flex", alignItems:"center", justifyContent:"center" }}>
                <IconRefresh size={22} />
              </button>
           </div>
         ) : (
           <>
             <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <button className="btn-icon" onClick={() => window.location.hash = "#/"} style={{ background:"var(--glass)", border: "1px solid var(--bdr)", borderRadius:12, width:44, height:44, display:"flex", alignItems:"center", justifyContent:"center" }}>
                  <IconMenuOpen size={22} color="var(--cy)" />
                </button>
                <div style={{ display: "flex", flexDirection: "column" }}>
                   <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div className="pulse" style={{ width: 8, height: 8, borderRadius: "50%", background: (macro?.regime === "BULLISH" ? "var(--gr)" : "var(--rd)") }} />
                      <span style={{ fontSize: 12, fontWeight: 900, color: "var(--tx)" }}>{macro?.regime || "SYNCING"}</span>
                   </div>
                   <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)", letterSpacing: 1 }}>MARKET REGIME</span>
                </div>
             </div>
             <div style={{ display: "flex", gap: 12 }}>
                {isMobile && (
                  <button className="btn-icon" onClick={() => setShowSearch(true)} style={{ background:"var(--glass)", border: "1px solid var(--bdr)", borderRadius:12, width:44, height:44, display:"flex", alignItems:"center", justifyContent:"center" }}>
                    <IconSearch size={22} color="var(--cy)" />
                  </button>
                )}
                {isMobile && (
                  <button className="btn-icon" onClick={() => setShowFilters(!showFilters)} style={{ background:"var(--glass)", border: "1px solid var(--bdr)", borderRadius:12, width:44, height:44, display:"flex", alignItems:"center", justifyContent:"center" }}>
                    <IconFilter size={22} color={showFilters ? "var(--cy)" : "var(--tx3)"} />
                  </button>
                )}
                {!isMobile && (
                  <div className="card" style={{ padding: "8px 16px", background: "var(--glass)", border: "1px solid var(--bdr)", borderRadius: 12, display: "flex", alignItems: "center", gap: 12 }}>
                     <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 12, fontWeight: 900, color: "var(--tx)" }}>{fmt(macro?.lpi, 2)}</div>
                        <div style={{ fontSize: 8, fontWeight: 800, color: "var(--tx3)" }}>LIQUIDITY</div>
                     </div>
                     <div style={{ width: 1, height: 20, background: "var(--bdr)" }} />
                     <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 12, fontWeight: 900, color: "var(--tx)" }}>{fmt(macro?.ycmo, 2)}</div>
                        <div style={{ fontSize: 8, fontWeight: 800, color: "var(--tx3)" }}>YIELD CURVE</div>
                     </div>
                  </div>
                )}
             </div>
           </>
         )}
      </div>

       {(baseError || error) && (
         <div style={{ 
           padding: "16px 20px", borderRadius: 16, marginBottom: 20,
           background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.25)",
           display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16
         }}>
           <div>
             <div style={{ fontWeight: 800, fontSize: 13, color: "var(--rd)", marginBottom: 4 }}>
               ⚠️ {error ? "Gagal Menganalisis Ticker" : "Gagal Memuat Data Pasar Stock Analyzer"}
             </div>
              <div style={{ fontSize: 11, color: "var(--tx2)" }}>
                {typeof (error || baseError) === "string" ? (error || baseError) : (error?.message || baseError?.message || String(error || baseError))}
              </div>
           </div>
           <button className="btn btn-g btn-s" onClick={() => { if (error) clearError(); loadBaseData(); }}>
             <IconRefresh size={13} style={{ marginRight: 4 }} /> Coba Lagi
           </button>
         </div>
       )}

       {baseLoading ? <StockAnalyzerSkeleton isMobile={isMobile} /> : (
        <div className={`stk-terminal ${!isMobile ? "stk-main-grid" : ""}`}>
           {/* 1. Sidebar (Watchlist) */}
           <aside className={isMobile ? "mobile-sidebar" : "desktop-sidebar"} style={{ 
              display: isMobile && !showFilters ? "none" : "flex"
           }}>
              <div className="card" style={{ padding: 24, marginBottom: 20, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)", boxShadow: "var(--card-shadow)" }}>
                <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", marginBottom: 20, letterSpacing: 1.5 }}>STRATEGIC FILTERS</div>
                
                {!isMobile && (
                  <TickerSearch 
                    value={searchInput} 
                    onChange={setSearchInput} 
                    onAnalyze={handleAnalyze} 
                    isMobile={false} 
                  />
                )}

                <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
                  <div className="stk-filter-group">
                    <label className="stk-filter-label">Market Sector</label>
                    <div className="stk-filter-select-wrap">
                      <select className="stk-filter-select" value={filterCat} onChange={e => setFilterCat(e.target.value)}>
                        <option value="ALL">ALL ASSETS</option>
                        <option value="STOCKS">EQUITIES</option>
                        <option value="CRYPTO">CRYPTO</option>
                        <option value="FOREX">FOREX</option>
                      </select>
                      <IconDown size={16} style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--tx3)" }} />
                    </div>
                  </div>
                  
                  <div className="stk-filter-group">
                    <label className="stk-filter-label">ML Bias</label>
                    <div className="stk-segmented-control">
                      {["ALL", "BULLISH", "BEARISH"].map(s => (
                        <button key={s} className={`stk-segmented-btn ${filterSignal === s ? "active" : ""}`} onClick={() => setFilterSignal(s)}>{s}</button>
                      ))}
                    </div>
                  </div>

                  <div className="stk-preset-grid">
                    <button className={`btn btn-s ${activePreset === "BEST" ? "btn-p" : "btn-g"}`} style={{ borderRadius: 12, height: 40 }} onClick={() => applyPreset("BEST")}>BEST</button>
                    <button className={`btn btn-s ${activePreset === "SNIPER" ? "btn-p" : "btn-g"}`} style={{ borderRadius: 12, height: 40 }} onClick={() => applyPreset("SNIPER")}>SNIPER</button>
                  </div>
                </div>
                <button className="btn btn-g btn-s" style={{ width: "100%", marginTop: 24, borderRadius: 12, height: 44, fontWeight: 900 }} onClick={() => applyPreset("CLEAR")}>RESET ENGINE</button>
              </div>

              <div className="watchlist-container" style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                   <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1.5 }}>LIVE POOL ({filteredWatchlist.length})</div>
                   <IconActivity size={14} color="var(--gr)" className="pulse" />
                </div>
                <div className="watchlist-grid">
                  {filteredWatchlist.map(item => {
                    const ml = mlMap[item.ticker] || {};
                    const isActive = data?.ticker === item.ticker;
                    const sigColor = getSignalColor(ml.signal);
                    const isFav = favorites.includes(item.ticker);
                    return (
                      <div key={`${item.ticker}-${item.category}`} className={`watchlist-item ${isActive ? "active" : ""}`} onClick={() => handleAnalyze(item.ticker)}>
                        <div className="watchlist-signal-bar" style={{ background: sigColor }} />
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontWeight: 900, fontSize: 14, letterSpacing: -0.5 }}>{item.ticker}</span>
                          <button 
                             onClick={(e) => { e.stopPropagation(); toggleFavorite(item.ticker); }}
                             style={{ background: "none", border: "none", padding: 4, color: isFav ? "var(--yl)" : "var(--tx3)", cursor: "pointer", display: "flex", transition: "transform 0.2s ease" }}
                             className="fav-btn"
                          >
                             <IconStar size={16} fill={isFav ? "var(--yl)" : "none"} />
                          </button>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                          <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)", textTransform: "uppercase" }}>{item.category.replace(" STOCKS", "")}</span>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                             <span style={{ fontSize: 11, fontWeight: 900, color: ml.change >= 0 ? "var(--gr)" : "var(--rd)" }}>
                               {ml.change != null ? `${ml.change >= 0 ? "+" : ""}${ml.change.toFixed(2)}%` : "---"}
                             </span>
                             {ml.change >= 0 ? <IconUp size={12} color="var(--gr)" /> : <IconDown size={12} color="var(--rd)" />}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
           </aside>

           {/* 2. Main Terminal Content */}
           <main className="stk-details-main">
              {tickerLoading ? (
                <div style={{ height: "80vh", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 24 }}>
                   <div className="spinner-premium" />
                   <div style={{ fontSize: 11, fontWeight: 900, color: "var(--tx3)", letterSpacing: 3, animation: "pulse 2s infinite" }}>QUANT_ENGINE_LOAD</div>
                </div>
              ) : error ? (
                <div style={{ height: "70vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "2px dashed var(--rd)", borderRadius: 32, margin: isMobile ? 20 : 32, background: "rgba(239, 68, 68, 0.02)" }}>
                   <div style={{ background: "var(--bg2)", padding: 40, borderRadius: "50%", border: "1px solid var(--rd)", marginBottom: 24 }}>
                      <IconAlertCircle size={64} style={{ color: "var(--rd)" }} />
                   </div>
                   <div style={{ fontSize: 16, fontWeight: 900, color: "var(--rd)", letterSpacing: 2, textAlign: "center" }}>ANALYSIS_FAILURE</div>
                   <p style={{ fontSize: 11, color: "var(--tx2)", marginTop: 12, maxWidth: 360, textAlign: "center", lineHeight: 1.6 }}>{typeof error === "string" ? error : error?.message || "Analysis failed. Check API server."}</p>
                   <button className="btn btn-g btn-s" style={{ marginTop: 24, borderRadius: 12 }} onClick={() => clearError()}>RETURN TO HUB</button>
                </div>
              ) : data ? (
                <div key={data.ticker} className="stk-terminal-view">
                   {/* Header: Live Prices */}
                   <div className="stk-term-header">
                      <div className="stk-term-ticker-row">
                         <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                            <button 
                               onClick={() => toggleFavorite(data.ticker)}
                               style={{ background: "var(--glass)", border: "1px solid var(--bdr)", borderRadius: 16, width: 56, height: 56, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: favorites.includes(data.ticker) ? "var(--yl)" : "var(--tx3)", transition: "all 0.3s ease" }}
                            >
                               <IconStar size={28} fill={favorites.includes(data.ticker) ? "var(--yl)" : "none"} />
                            </button>
                            <div>
                               <div className="stk-term-ticker">{data.ticker}</div>
                               <div className="stk-term-meta">{data._category || "SPOT ASSET"} â€¢ REAL-TIME FEED</div>
                            </div>
                         </div>
                         <div style={{ textAlign: "right" }}>
                            <div className="stk-term-price">{fmtPrice(data.price, data.ticker)}</div>
                            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, justifyContent: "flex-end" }}>
                               <div className={`pill ${getSignalVariant(data.signal)}`} style={{ padding: "6px 14px", fontSize: 11, borderRadius: 8 }}>
                                  {data.signal}
                               </div>
                               <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                  <span style={{ fontSize: 14, fontWeight: 900, color: data.change >= 0 ? "var(--gr)" : "var(--rd)" }}>
                                     {data.change >= 0 ? "+" : ""}{fmt(data.change, 2)}%
                                  </span>
                                  {data.change >= 0 ? <IconUp size={16} color="var(--gr)" /> : <IconDown size={16} color="var(--rd)" />}
                               </div>
                            </div>
                         </div>
                      </div>
                   </div>

                   {/* Workspace */}
                   <div className="stk-term-workspace">
                      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1.6fr 1fr", gap: 32 }}>
                         
                         <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
                            {/* Signal Hub */}
                            <div className={`stk-signal-hub ${(data.ml_signal.includes("BUY") || data.ml_signal.includes("BULL")) ? "bullish" : (data.ml_signal.includes("SELL") || data.ml_signal.includes("BEAR")) ? "bearish" : ""}`}>
                               <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                  <div>
                                     <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                                        <IconFlash size={14} color="var(--cy)" />
                                        <label style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: 1.5 }}>Quant Sniper v4.0</label>
                                     </div>
                                     <div className="stk-signal-val" style={{ color: getSignalColor(data.ml_signal) }}>
                                        {data.ml_signal}
                                        {data.mrzg && data.mrzg !== "NONE" && (
                                          <span style={{ 
                                            fontSize: 12, marginLeft: 12, padding: "2px 8px", 
                                            background: (data.mrzg.includes("POTENTIAL") || data.mrzg.includes("OVER")) ? "rgba(234, 179, 8, 0.1)" : "var(--bg3)", 
                                            borderRadius: 6, 
                                            color: (data.mrzg.includes("POTENTIAL") || data.mrzg.includes("OVER")) ? "var(--yl)" : "var(--cy)", 
                                            verticalAlign: "middle",
                                            border: (data.mrzg.includes("POTENTIAL") || data.mrzg.includes("OVER")) ? "1px solid var(--yl)" : "1px solid var(--bdr)"
                                          }}>
                                            {data.mrzg.replace(/_/g, " ")}
                                          </span>
                                        )}
                                     </div>
                                     <div style={{ fontSize: 12, fontWeight: 800, color: "var(--tx2)", marginTop: 8 }}>
                                        Confidence: <span style={{ color: "var(--tx)" }}>{data.ml_prob != null ? `${fmt(data.ml_prob * 100, 1)}%` : "---"}</span>
                                     </div>
                                  </div>
                                  <ScoreGauge score={data.score} size={isMobile ? 100 : 140} />
                               </div>
                               <div style={{ marginTop: 24 }}>
                                  <div className="stk-prog-track" style={{ height: 8, borderRadius: 4 }}>
                                     <div className="stk-prog-bar" style={{ width: `${(data.ml_prob || 0)*100}%`, borderRadius: 4 }} />
                                  </div>
                               </div>
                            </div>

                            {/* Forecasting & Kelly Sizing */}
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                               <div className="stk-forecast-card">
                                  <div style={{ fontSize: 9, fontWeight: 950, color: "var(--tx3)", letterSpacing: 1, marginBottom: 12, position: "relative", zIndex: 1 }}>AI PRICE FORECAST</div>
                                  <div style={{ display: "flex", justifyContent: "space-around", position: "relative", zIndex: 1 }}>
                                     <div style={{ textAlign: "center" }}>
                                        <div style={{ fontSize: 8, color: "var(--tx3)", marginBottom: 4 }}>1 WEEK</div>
                                        <div style={{ fontSize: 18, fontWeight: 900, color: data.forecast_1w > 0 ? "var(--gr)" : data.forecast_1w < 0 ? "var(--rd)" : "var(--tx3)" }}>
                                           {data.forecast_1w === 0 || data.forecast_1w === null ? "N/A" : `${data.forecast_1w > 0 ? "+" : ""}${fmt(data.forecast_1w * 100, 1)}%`}
                                        </div>
                                     </div>
                                     <div style={{ width: 1, height: 30, background: "var(--glass-border)" }} />
                                     <div style={{ textAlign: "center" }}>
                                        <div style={{ fontSize: 8, color: "var(--tx3)", marginBottom: 4 }}>1 MONTH</div>
                                        <div style={{ fontSize: 18, fontWeight: 900, color: data.forecast_1m > 0 ? "var(--gr)" : data.forecast_1m < 0 ? "var(--rd)" : "var(--tx3)" }}>
                                           {data.forecast_1m === 0 || data.forecast_1m === null ? "N/A" : `${data.forecast_1m > 0 ? "+" : ""}${fmt(data.forecast_1m * 100, 1)}%`}
                                        </div>
                                     </div>
                                  </div>
                               </div>
                               <div className="stk-forecast-card">
                                  <div style={{ fontSize: 9, fontWeight: 950, color: "var(--tx3)", letterSpacing: 1, marginBottom: 12, position: "relative", zIndex: 1 }}>KELLY SIZING</div>
                                  <div style={{ textAlign: "center", position: "relative", zIndex: 1 }}>
                                     <div style={{ fontSize: 8, color: "var(--tx3)", marginBottom: 4 }}>RECOMMENDED ALLOCATION</div>
                                     <div style={{ fontSize: 22, fontWeight: 950, color: "var(--cy)" }}>
                                        {data.kelly_fraction === 0 || data.kelly_fraction === null ? "N/A" : `${fmt(data.kelly_fraction * 100, 1)}%`}
                                     </div>
                                  </div>
                               </div>
                            </div>

                            {/* Macro Intelligence */}
                            <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)" }}>
                               <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                     <IconPieChart size={18} color="var(--cy)" />
                                     <span style={{ fontSize: 11, fontWeight: 900, color: "var(--tx2)", letterSpacing: 1 }}>MACRO INTELLIGENCE</span>
                                  </div>
                                  <span style={{ fontSize: 10, fontWeight: 950, color: data.vol_regime === "HIGH" ? "var(--rd)" : "var(--gr)", background: data.vol_regime === "HIGH" ? "rgba(239, 68, 68, 0.1)" : "rgba(34, 197, 94, 0.1)", padding: "4px 12px", borderRadius: 20 }}>
                                     {data.vol_regime} VOLATILITY
                                  </span>
                               </div>
                               <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                                  <div style={{ background: "var(--bg3)", padding: 16, borderRadius: 16, border: "1px solid var(--bdr)" }}>
                                     <div className="lbl" style={{ fontSize: 8, marginBottom: 6 }}>Liquidity (LPI)</div>
                                     <div style={{ fontSize: 16, fontWeight: 900, color: data.css > 70 ? "var(--gr)" : "var(--tx)" }}>
                                        {fmt(data.css, 1)}
                                     </div>
                                  </div>
                                  <DXYPanel data={data} assetType={data._category?.includes("CRYPTO") ? "crypto" : "stock"} />
                                  <div style={{ background: "var(--bg3)", padding: 16, borderRadius: 16, border: "1px solid var(--bdr)" }}>
                                     <div className="lbl" style={{ fontSize: 8, marginBottom: 6 }}>Sentiment (CSI)</div>
                                     <div style={{ fontSize: 16, fontWeight: 900 }}>
                                        {fmt(data.csi, 1)}
                                     </div>
                                  </div>
                               </div>
                            </div>

                            {/* Whale Activity Tracker */}
                            <ButterflyErrorBoundary message="Institutional Data Unavailable">
                               <WhaleActivity ticker={data.ticker} assetType={data._category?.includes("CRYPTO") ? "crypto" : "stock"} />
                            </ButterflyErrorBoundary>

                            {/* Butterfly Effect Map (Correlations) */}
                            <ButterflyMap ticker={data.ticker} />

                            {/* Agent Senate Consensus (New) */}
                            <ButterflyErrorBoundary message="Consensus Engine Offline">
                               <SenateAgent ticker={data.ticker} assetType={data._category} />
                            </ButterflyErrorBoundary>
                         </div>

                         {/* Price Structure Zones */}
                         <div style={{ height: "100%" }}>
                            <PriceStructure data={data} />
                         </div>

                      </div>
                   </div>
                </div>
              ) : (
                <div style={{ height: "70vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "2px dashed var(--bdr)", borderRadius: 32, margin: isMobile ? 20 : 32, background: "rgba(255,255,255,0.01)" }}>
                   <div className="pulse-slow" style={{ background: "var(--bg2)", padding: 40, borderRadius: "50%", border: "1px solid var(--bdr)", marginBottom: 24 }}>
                      <IconFlash size={64} style={{ color: "var(--bg4)" }} />
                   </div>
                   <div style={{ fontSize: 16, fontWeight: 900, color: "var(--tx3)", letterSpacing: 2, textAlign: "center" }}>INITIALIZE QUANT TERMINAL</div>
                   <p style={{ fontSize: 11, color: "var(--tx3)", marginTop: 12, opacity: 0.6 }}>SELECT AN ASSET FROM THE POOL TO BEGIN ANALYSIS</p>
                </div>
              )}
           </main>
        </div>
      )}
    </PageWrapper>
  );
}
