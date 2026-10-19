import React, { useState, useEffect, useMemo, useCallback, useRef, memo } from "react";
import { useDebounce, useCacheFetch, useWebSocket } from "../finance/useApi.js";
import { Skeleton } from "../components.jsx";
import { useButterflyBenchmark } from "../hooks/useButterflyBenchmark.js";
import { useI18n } from "../i18n/context.js";
import { IconActivity, IconInfo, IconAlertCircle, IconTarget, IconDown } from "../icons.jsx";
import ButterflyErrorBoundary, { ButterflyStatus } from "./ButterflyErrorBoundary.jsx";

// Utilities extracted from stock_analyzer.jsx
const fmt = (val, dec = 2) => {
  if (val === null || val === undefined) return "---";
  if (typeof val === 'object') return "---";
  const v = Number(val);
  return isNaN(v) ? "---" : v.toFixed(dec);
};

const isValidGraphData = (data) => {
  return data && typeof data === 'object' && Array.isArray(data.nodes);
};

const sanitizePayload = (data) => {
  if (!data || !data.nodes || !Array.isArray(data.nodes)) {
    console.warn("ButterflyMap: Invalid payload received", data);
    return { nodes: [], edges: [] };
  }
  
  const cleanNodes = data.nodes.filter(node => 
    node &&
    typeof node === 'object' &&
    node.ticker && 
    typeof node.ticker === 'string'
  ).map(node => ({
    ...node,
    correlation: !isNaN(Number(node.correlation)) ? Number(node.correlation) : 0,
    impact: String(node.impact || "Low"),
    description: String(node.description || "Sector related risk")
  }));
  
  const nodeIds = new Set(cleanNodes.map(n => n.ticker));
  const cleanEdges = (Array.isArray(data.edges) ? data.edges : []).filter(edge => 
    edge &&
    typeof edge === 'object' &&
    nodeIds.has(edge.source) && 
    nodeIds.has(edge.target)
  );
  
  return { nodes: cleanNodes, edges: cleanEdges };
};

const MapNode = memo(({ node, pulseManager }) => {
  const { t } = useI18n();
  const [pulsing, setPulsing] = useState(false);
  const timerRef = useRef(null);
  
  useEffect(() => {
    if (!pulseManager || !node.ticker) return;
    
    try {
      const unsubscribe = pulseManager.subscribe(node.ticker, () => {
        setPulsing(true);
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          setPulsing(false);
          timerRef.current = null;
        }, 1000);
      });

      return () => {
        unsubscribe();
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    } catch (e) {
      console.error("MapNode pulse subscription error:", e);
    }
  }, [node.ticker, pulseManager]);

  return (
    <div 
      style={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center", 
        padding: "12px 16px", 
        background: "var(--bg3)", 
        borderRadius: 16, 
        border: `1px solid ${pulsing ? "var(--cy)" : "var(--bdr)"}`,
        boxShadow: pulsing ? "0 0 15px rgba(0, 255, 255, 0.15)" : "none",
        transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)"
      }}
    >
       <div>
          <div style={{ fontSize: 13, fontWeight: 900 }}>{node.ticker || t("butterfly.unknown")}</div>
          <div style={{ fontSize: 8, color: "var(--tx3)", textTransform: "uppercase" }}>{node.description}</div>
       </div>
       <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 14, fontWeight: 900, color: Math.abs(node.correlation) > 0.6 ? "var(--yl)" : "var(--tx)" }}>
            {fmt(node.correlation * 100, 1)}%
          </div>
          <div style={{ fontSize: 8, fontWeight: 900, color: node.impact === "High" ? "var(--rd)" : "var(--tx3)" }}>{String(node.impact).toUpperCase()} {t("butterfly.impact")}</div>
       </div>
    </div>
  );
});

const ButterflyMapContent = memo(({ ticker, crash }) => {
  const { t } = useI18n();
  if (crash) {
    throw new Error("Butterfly Visualization Engine encountered a critical failure (simulated)");
  }

  const debouncedTicker = useDebounce(ticker, 500);
  
  const { benchmarkMode, setBenchmarkMode, metrics, scale, setScale } = useButterflyBenchmark();

  const { data: cacheData, loading, error: fetchError } = useCacheFetch(
    benchmarkMode 
      ? `/butterfly/benchmark/${scale}`
      : (debouncedTicker ? `/butterfly/risk-map/${debouncedTicker}` : null)
  );
  
  const { lastMessage: wsMessage } = useWebSocket("butterfly");

  const [map, setMap] = useState({ nodes: [], edges: [] });
  
  const pulseManagerRef = useRef(null);
  if (!pulseManagerRef.current) {
    pulseManagerRef.current = {
      listeners: {},
      subscribe(id, cb) {
        this.listeners[id] = cb;
        return () => { delete this.listeners[id]; };
      },
      trigger(id) {
        if (this.listeners[id]) this.listeners[id]();
      }
    };
  }
  const pulseManager = pulseManagerRef.current;

  const graphRef = useRef({ data: { nodes: [], edges: [] } });

  const updateMap = useCallback((newData) => {
    try {
      if (!isValidGraphData(newData)) return;
      
      const sanitized = sanitizePayload(newData);
      
      sanitized.nodes.forEach(node => {
        const prev = graphRef.current.data.nodes.find(n => n.ticker === node.ticker);
        if (prev && prev.correlation !== node.correlation) {
          pulseManager.trigger(node.ticker);
        }
      });

      graphRef.current.data = sanitized;
      setMap(sanitized);
    } catch (e) {
      console.error("ButterflyMap update error:", e);
      // Fallback to empty map instead of crashing
      setMap({ nodes: [], edges: [] });
    }
  }, [pulseManager]);

  useEffect(() => {
    if (cacheData) updateMap(cacheData);
  }, [cacheData, updateMap]);

  useEffect(() => {
    if (!benchmarkMode && wsMessage && wsMessage.ticker === debouncedTicker) {
      updateMap(wsMessage.data);
    }
  }, [wsMessage, debouncedTicker, updateMap, benchmarkMode]);

  const renderedNodes = useMemo(() => {
    if (loading && map.nodes.length === 0) {
      return [1, 2, 3, 4, 5].map(i => <Skeleton key={i} h={40} r={12} mb={0} />);
    }
    
    if (map.nodes.length > 0) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {map.nodes.map(node => (
            <MapNode key={node.ticker} node={node} pulseManager={pulseManager} />
          ))}
        </div>
      );
    }

    if (!loading) {
      if (fetchError) return <ButterflyStatus type="error" message={t("butterfly.graph_unavailable")} />;
      return <ButterflyStatus type="empty" message={t("butterfly.no_relationships")} />;
    }

    return null;
  }, [map, loading, fetchError, pulseManager, t]);

  return (
    <div className="card" style={{ padding: 24, background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)", position: "relative" }}>
       {benchmarkMode && (
         <div style={{ 
           position: "absolute", top: 12, right: 12, padding: "8px 12px", 
           background: "rgba(0,0,0,0.8)", borderRadius: 12, border: "1px solid var(--cy)",
           display: "flex", gap: 16, zIndex: 10, fontSize: 10, fontWeight: 900, color: "var(--cy)"
         }}>
           <div>FPS: {metrics.fps}</div>
           <div>MEM: {metrics.memory}MB</div>
           <div>NODES: {map.nodes.length}</div>
         </div>
       )}
       <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
             <IconActivity size={18} color="var(--cy)" />
             <span style={{ fontSize: 11, fontWeight: 900, color: "var(--tx2)", letterSpacing: 1 }}>{t("butterfly.title")}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
             {benchmarkMode && (
               <div style={{ display: "flex", background: "var(--bg3)", borderRadius: 8, padding: 2, border: "1px solid var(--bdr)" }}>
                 {[10, 100, 500].map(s => (
                   <button 
                     key={s} 
                     onClick={() => setScale(s)}
                     style={{ 
                       padding: "4px 8px", fontSize: 9, fontWeight: 900, border: "none", borderRadius: 6,
                       background: scale === s ? "var(--cy)" : "transparent",
                       color: scale === s ? "var(--bg)" : "var(--tx3)", cursor: "pointer"
                     }}
                   >
                     {s}
                   </button>
                 ))}
               </div>
             )}
             <button 
               onClick={() => setBenchmarkMode(!benchmarkMode)}
               style={{ 
                 background: benchmarkMode ? "var(--cy)" : "var(--bg3)", 
                 border: "1px solid var(--bdr)", borderRadius: 8, padding: "4px 8px",
                 fontSize: 9, fontWeight: 900, color: benchmarkMode ? "var(--bg)" : "var(--tx3)",
                 cursor: "pointer", transition: "all 0.2s ease"
               }}
             >
               {benchmarkMode ? t("butterfly.benchmark_on") : t("butterfly.benchmark_off")}
             </button>
             {!benchmarkMode && <span style={{ fontSize: 9, fontWeight: 800, color: "var(--tx3)" }}>{t("butterfly.cross_asset")}</span>}
          </div>
       </div>
       <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {renderedNodes}
       </div>
    </div>
  );
});

const ButterflyMap = (props) => (
  <ButterflyErrorBoundary>
    <ButterflyMapContent {...props} />
  </ButterflyErrorBoundary>
);

export default memo(ButterflyMap);
