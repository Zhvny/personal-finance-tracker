// â”€â”€â”€ AIInsightPanel.jsx â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Claude-powered behavioral finance analysis panel.
// Zero emojis â€” all icons from ../icons.jsx.

import { useState, useRef } from "react";
import { apiFetch, useAIStatus, _getToken } from "../finance/useApi.js";
import { useI18n } from "../i18n/context.js";
import { API_BASE } from "../finance/constants.js";
import {
  IconRefresh, IconAlert, IconCheck, IconBarChart,
  IconUp, IconAnalysis, IconInfo, IconExpense,
  IconBehavioral, IconRisk,
} from "../icons.jsx";

function PriorityBadge({ priority }) {
  const { t } = useI18n();
  const map = {
    high:   { bg: "rgba(248,113,113,.18)", color: "#f87171",  label: t("behavioral.priority_high") },
    medium: { bg: "rgba(251,191,36,.15)",  color: "#fbbf24",  label: t("behavioral.priority_medium") },
    low:    { bg: "rgba(52,211,153,.15)",  color: "#34d399",  label: t("behavioral.priority_low") },
  };
  const s = map[priority] || map.low;
  return (
    <span style={{ display:"inline-flex", alignItems:"center", padding:"3px 10px", borderRadius:99,
      fontSize:10, fontWeight:700, background:s.bg, color:s.color, letterSpacing:".3px" }}>{s.label}</span>
  );
}

function ScoreRing({ score }) {
  const { t } = useI18n();
  if (score == null) return null;
  const pct = Math.round(Math.min(100, Math.max(0, score)));
  const color = pct >= 70 ? "var(--gr)" : pct >= 45 ? "var(--yl)" : "var(--rd)";
  const label = pct >= 70 ? t("behavioral.stable") : pct >= 45 ? t("behavioral.score_fair") : t("behavioral.score_attention");
  const r = 28, circ = 2 * Math.PI * r, dash = (pct / 100) * circ;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:12 }}>
      <svg width={72} height={72} style={{ flexShrink:0 }}>
        <circle cx={36} cy={36} r={r} fill="none" stroke="var(--bg4)" strokeWidth={6} />
        <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={6}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 36 36)" style={{ transition:"stroke-dasharray .6s" }} />
        <text x={36} y={40} textAnchor="middle"
          style={{ fontSize:15, fontWeight:700, fill:color, fontFamily:"var(--mono)" }}>{pct}</text>
      </svg>
      <div>
        <div style={{ fontSize:10, color:"var(--tx3)", textTransform:"uppercase", letterSpacing:".8px", marginBottom:3 }}>{t("behavioral.score_ring_label")}</div>
        <div style={{ fontSize:14, fontWeight:700, color }}>{label}</div>
        <div style={{ fontSize:11, color:"var(--tx3)", marginTop:2 }}>{t("behavioral.of_100")}</div>
      </div>
    </div>
  );
}

function RecommendationCard({ rec }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const pcfg = {
    high:   { line:"#f87171", bg:"rgba(248,113,113,.06)", Icon: IconAlert, iconColor:"#f87171" },
    medium: { line:"#fbbf24", bg:"rgba(251,191,36,.05)",  Icon: IconAlert, iconColor:"#fbbf24" },
    low:    { line:"#34d399", bg:"rgba(52,211,153,.05)",  Icon: IconInfo,  iconColor:"#34d399" },
  };
  const s = pcfg[rec.priority] || pcfg.low;
  const Icon = s.Icon;
  return (
    <div onClick={() => setExpanded(e => !e)} style={{
      background:s.bg, borderRadius:12, padding:"13px 15px", marginBottom:8,
      cursor:"pointer", border:`1px solid var(--bdr)`, borderLeftColor:s.line,
      borderLeftWidth:3, borderLeftStyle:"solid", transition:"background .15s",
    }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:8 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:"flex", alignItems:"center", gap:7, flexWrap:"wrap", marginBottom:6 }}>
            <Icon size={14} color={s.iconColor} style={{ flexShrink:0 }} />
            <PriorityBadge priority={rec.priority} />
          </div>
          <div style={{ fontSize:13, fontWeight:600, color:"var(--tx)", lineHeight:1.5 }}>{rec.action}</div>
          {expanded && (
            <div style={{ marginTop:10, paddingTop:10, borderTop:"1px solid var(--bdr)" }}>
              {rec.reason && (
                <div style={{ fontSize:12, color:"var(--tx2)", lineHeight:1.7, marginBottom:6 }}>
                  <span style={{ color:"var(--tx3)", fontWeight:600 }}>{t("behavioral.reason")}: </span>{rec.reason}
                </div>
              )}
              {rec.impact && (
                <div style={{ fontSize:12, color:"var(--gr)", lineHeight:1.6, display:"flex", gap:6, alignItems:"flex-start" }}>
                  <IconCheck size={13} style={{ flexShrink:0, marginTop:1 }} /><span><strong>{t("behavioral.impact")}:</strong> {rec.impact}</span>
                </div>
              )}
            </div>
          )}
        </div>
        <span style={{ fontSize:11, color:"var(--tx3)", flexShrink:0, marginTop:2,
          transition:"transform .2s", display:"inline-block",
          transform:expanded?"rotate(180deg)":"none" }}>â–¼</span>
      </div>
    </div>
  );
}

function InsightSkeleton() {
  const Bar = ({ w="100%", h=14, mb=8 }) => (
    <div style={{ width:w, height:h, borderRadius:6, marginBottom:mb,
      background:"linear-gradient(90deg,var(--bg3)25%,var(--bg4)50%,var(--bg3)75%)",
      backgroundSize:"200% 100%", animation:"beh-shimmer 1.6s infinite linear" }} />
  );
  return (
    <div>
      <Bar h={72} mb={14} /><Bar h={12} mb={8} /><Bar h={12} w="85%" mb={20} />
      <Bar h={16} w="40%" mb={10} /><Bar h={60} mb={8} /><Bar h={60} mb={8} /><Bar h={60} mb={0} />
      <style>{`@keyframes beh-shimmer{from{background-position:200% 0}to{background-position:-200% 0}}`}</style>
    </div>
  );
}

function NoProviderState({ onRetry }) {
  const { t } = useI18n();
  return (
    <div style={{ padding:32, background:"rgba(255,255,255,.02)", border:"1px solid var(--bdr)",
      borderRadius:"var(--rl)", textAlign:"center" }}>
      <div style={{ display:"flex", justifyContent:"center", marginBottom:16 }}>
        <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--bg3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <IconBehavioral size={24} color="var(--tx3)" />
        </div>
      </div>
      <div style={{ fontSize:15, fontWeight:700, color:"var(--tx)", marginBottom:8 }}>{t("behavioral.ai_unavailable_title")}</div>
      <div style={{ fontSize:12, color:"var(--tx3)", lineHeight:1.6, marginBottom:20, maxWidth: 300, margin: "0 auto 24px" }}>
        {t("behavioral.ai_unavailable_body")}
      </div>
      <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
        <button className="btn btn-p btn-s" onClick={() => window.open('https://github.com/zhvny/finance-tracker#ai-setup', '_blank')}>{t("behavioral.setup_guide")}</button>
        <button className="btn btn-g btn-s" onClick={onRetry}><IconRefresh size={13} /> {t("common.refresh")}</button>
      </div>
    </div>
  );
}

function InsightRow({ Icon, label, value, color="var(--tx2)" }) {
  return (
    <div style={{ display:"flex", alignItems:"flex-start", gap:10, padding:"10px 0", borderBottom:"1px solid var(--bdr)" }}>
      {Icon && <Icon size={14} style={{ flexShrink:0, marginTop:2, opacity:.75 }} />}
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:10, color:"var(--tx3)", textTransform:"uppercase", letterSpacing:".6px", marginBottom:2 }}>{label}</div>
        <div style={{ fontSize:12, color, lineHeight:1.65 }}>{value}</div>
      </div>
    </div>
  );
}

export default function AIInsightPanel() {
  const { t } = useI18n();
  const [insights,   setInsights]   = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);
  const [noApiKey,   setNoApiKey]   = useState(false);
  const [loaded,     setLoaded]     = useState(false);
  const [streamText, setStreamText] = useState("");   // live token preview
  const [tokenCount, setTokenCount] = useState(0);   // how many tokens received
  const abortRef = useRef(null);
  const { status: aiStatus } = useAIStatus();

  const load = async () => {
    // Cancel any in-flight stream
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true); setError(null); setNoApiKey(false);
    setStreamText(""); setTokenCount(0);

    try {
      const res = await fetch(`${API_BASE}/ai/insights/stream`, {
        signal: controller.signal,
        headers: {
          "Accept": "text/event-stream",
          "Authorization": `Bearer ${_getToken()}`,
        },
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errJson.detail || `HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const lines = buf.split("\n");
        buf = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === "token") {
              setStreamText(t => t + evt.text);
              setTokenCount(n => n + 1);
            } else if (evt.type === "status") {
              setStreamText(evt.message);
            } else if (evt.type === "done") {
              if (evt.result?.ok === false && evt.result?.provider === "none") {
                setNoApiKey(true);
              } else {
                setInsights(evt.result);
              }
              setStreamText("");
              break;  // stream complete â€” exit loop, finally fires loading=false
            } else if (evt.type === "error") {
              setError(evt.message);
              setStreamText("");
              break;  // stop reading â€” finally will set loading=false
            }
          } catch { /* malformed SSE line â€” skip */ }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      setLoading(false);
      setLoaded(true);
      setStreamText("");
      abortRef.current = null;
    }
  };

  if (!loaded && !loading) load();

  const PROVIDER_BADGE = {
    claude: { label:t("behavioral.provider_claude"), bg:"rgba(167,139,250,.15)", color:"var(--pu)", border:"rgba(167,139,250,.25)", Icon: IconAnalysis },
    gemini: { label:t("behavioral.provider_gemini"), bg:"rgba(79,70,229,.15)",   color:"#4f46e5",   border:"rgba(79,70,229,.25)",  Icon: IconAnalysis },
    ollama: { label:t("behavioral.provider_ollama"), bg:"rgba(52,211,153,.12)",  color:"var(--gr)", border:"rgba(52,211,153,.25)",  Icon: IconInfo     },
    rules:  { label:t("behavioral.provider_rules"), bg:"rgba(96,165,250,.12)",  color:"#60a5fa",   border:"rgba(96,165,250,.25)",  Icon: IconBarChart  },
  };
  const activeProvider = insights?.provider || aiStatus?.active || "claude";
  const badge = PROVIDER_BADGE[activeProvider] || PROVIDER_BADGE.claude;
  const BadgeIcon = badge.Icon;

  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:16, flexWrap:"wrap", gap:10 }}>
        <div>
          <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
            <span style={{ padding:"3px 10px", borderRadius:99, fontSize:10, fontWeight:700,
              background:badge.bg, color:badge.color, border:`1px solid ${badge.border}`,
              display:"inline-flex", alignItems:"center", gap:5 }}>
              <BadgeIcon size={10} />{badge.label}
            </span>
            <span style={{ fontSize:14, fontWeight:700, color:"var(--tx)" }}>{t("behavioral.insights_title")}</span>
            {activeProvider === "rules" && (
              <span style={{ padding:"2px 7px", borderRadius:99, fontSize:9, fontWeight:700,
                background:"rgba(251,191,36,.1)", color:"var(--yl)", border:"1px solid rgba(251,191,36,.2)" }}>{t("behavioral.offline_badge")}</span>
            )}
          </div>
              {insights?.data_period && (
            <div style={{ fontSize:11, color:"var(--tx3)", marginTop:3 }}>
              {t("behavioral.analysis_for", { period: insights?.data_period })}
              {insights?.generated_at && <span> · {t("behavioral.updated_at", { time: new Date(insights.generated_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"}) })}</span>}
            </div>
          )}
        </div>
        <button className="btn btn-g btn-s" onClick={load} disabled={loading}
          style={{ display:"flex", alignItems:"center", gap:5, flexShrink:0 }}>
          <IconRefresh size={13} style={{ animation:loading?"comp-spin 1s linear infinite":"none" }} />
          {loading ? t("behavioral.analyzing") : t("common.refresh")}
        </button>
      </div>

      {loading && (
        <div style={{ padding: "20px 0" }}>
          {/* Token counter progress bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <div style={{ flex: 1, height: 3, background: "var(--bg3)", borderRadius: 99, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 99,
                background: "var(--ind)",
                width: tokenCount > 0 ? `${Math.min(95, tokenCount / 5.12)}%` : "0%",
                transition: "width 0.3s ease",
                animation: tokenCount === 0 ? "comp-spin-bar 1.5s ease-in-out infinite" : "none",
              }} />
            </div>
            <span style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "var(--mono)", flexShrink: 0 }}>
              {tokenCount > 0 ? `${tokenCount} ${t("behavioral.token")}` : t("common.loading")}
            </span>
          </div>
          {/* Live text preview */}
          {streamText && (
            <div style={{
              padding: "12px 14px", background: "var(--bg3)", borderRadius: 8,
              border: "1px solid var(--bdr)", fontSize: 12, color: "var(--tx2)",
              fontFamily: "var(--mono)", lineHeight: 1.6,
              maxHeight: 120, overflow: "hidden",
              maskImage: "linear-gradient(to bottom, var(--tx) 60%, transparent)",
              WebkitMaskImage: "linear-gradient(to bottom, black 60%, transparent)",
            }}>
              {streamText}
              <span style={{ display: "inline-block", width: 1, height: 14, background: "var(--tx2)",
                marginLeft: 2, verticalAlign: "middle", animation: "blink-cursor 0.8s step-end infinite" }} />
            </div>
          )}
          {!streamText && <InsightSkeleton />}
        </div>
      )}
      {noApiKey && <NoProviderState onRetry={load} />}
      {error && !noApiKey && (
        <div style={{ padding:"14px 16px", background:"rgba(248,113,113,.08)", border:"1px solid rgba(248,113,113,.2)",
          borderRadius:"var(--rl)", fontSize:12, color:"var(--rd)", display:"flex", alignItems:"flex-start", gap:8 }}>
          <IconAlert size={14} style={{ flexShrink:0, marginTop:1 }} /> {t("behavioral.insights_failed", { error })}
        </div>
      )}

      {!loading && insights && !noApiKey && (
        <div style={{ display:"flex", flexDirection:"column", gap:14 }}>

          {/* Hero: Score + Assessment */}
          <div style={{ background:"linear-gradient(135deg,var(--bg3)0%,var(--bg2)100%)",
            border:"1px solid var(--bdr2)", borderRadius:14, padding:"16px 18px" }}>
            {insights.fbs_score != null && <ScoreRing score={insights.fbs_score} />}
            {insights.overall_assessment && (
              <div style={{ fontSize:13, color:"var(--tx2)", lineHeight:1.7,
                marginTop:insights.fbs_score!=null?14:0, paddingTop:insights.fbs_score!=null?14:0,
                borderTop:insights.fbs_score!=null?"1px solid var(--bdr)":"none",
                display:"flex", gap:8, alignItems:"flex-start" }}>
                <IconBarChart size={14} style={{ flexShrink:0, marginTop:1, opacity:.7 }} />
                <div><strong style={{ color:"var(--tx)" }}>{t("behavioral.condition_this_month")}: </strong>{insights.overall_assessment}</div>
              </div>
            )}
          </div>

          {/* Win + Risk */}
          <div className="sg" style={{ gap:12 }}>
            {insights.biggest_win && (
              <div style={{ background:"rgba(52,211,153,.07)", border:"1px solid rgba(52,211,153,.2)", borderRadius:12, padding:"14px 16px" }}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"1px", color:"var(--gr)", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
                  <IconCheck size={11} /> {t("behavioral.biggest_win")}
                </div>
                <div style={{ fontSize:12, color:"var(--tx2)", lineHeight:1.65 }}>{insights.biggest_win}</div>
              </div>
            )}
            {insights.top_risk && (
              <div style={{ background:"rgba(248,113,113,.07)", border:"1px solid rgba(248,113,113,.2)", borderRadius:12, padding:"14px 16px" }}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"1px", color:"var(--rd)", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
                  <IconAlert size={11} /> {t("behavioral.top_risk")}
                </div>
                <div style={{ fontSize:12, color:"var(--tx2)", lineHeight:1.65 }}>{insights.top_risk}</div>
              </div>
            )}
          </div>

          {/* Analysis */}
          {(insights.spending_pattern || insights.impulse_analysis || insights.lifestyle_inflation_verdict) && (
            <div style={{ background:"var(--bg2)", border:"1px solid var(--bdr)", borderRadius:12, overflow:"hidden" }}>
              <div style={{ padding:"10px 16px", borderBottom:"1px solid var(--bdr)",
                fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"1px", color:"var(--tx3)",
                display:"flex", alignItems:"center", gap:6 }}>
                <IconAnalysis size={12} /> {t("behavioral.pattern_analysis")}
              </div>
              <div style={{ padding:"4px 16px 8px" }}>
                {insights.spending_pattern            && <InsightRow Icon={IconExpense} label={t("behavioral.row_spending_pattern")}    value={insights.spending_pattern} />}
                {insights.impulse_analysis            && <InsightRow Icon={IconAlert}   label={t("behavioral.row_impulse_behavior")}  value={insights.impulse_analysis} color="var(--yl)" />}
                {insights.lifestyle_inflation_verdict && <InsightRow Icon={IconUp}   label={t("behavioral.row_lifestyle")} value={insights.lifestyle_inflation_verdict} />}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {insights.recommendations?.length > 0 && (
            <div>
              <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"1px", color:"var(--tx3)", marginBottom:10, display:"flex", alignItems:"center", gap:6 }}>
                <IconRisk size={11} /> {t("behavioral.actions_title")} <span style={{ fontSize:9, fontWeight:400, marginLeft:4 }}>{t("behavioral.click_details")}</span>
              </div>
              {insights.recommendations.map((rec, i) => <RecommendationCard key={i} rec={rec} />)}
            </div>
          )}

          {/* Forecast + Motivation */}
          <div className="sg" style={{ gap:12 }}>
            {insights.next_month_forecast && (
              <div style={{ background:"var(--bg2)", border:"1px solid var(--bdr)", borderRadius:12, padding:"14px 16px" }}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"1px", color:"var(--ind-b)", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
                  <IconBarChart size={11} color="var(--ind-b)" /> {t("behavioral.next_month_pred")}
                </div>
                <div style={{ fontSize:12, color:"var(--tx2)", lineHeight:1.65 }}>{insights.next_month_forecast}</div>
              </div>
            )}
            {insights.motivational_note && (
              <div style={{ background:"linear-gradient(135deg,rgba(79,110,247,.08),rgba(167,139,250,.08))",
                border:"1px solid rgba(79,110,247,.2)", borderRadius:12, padding:"14px 16px" }}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"1px", color:"var(--pu)", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
                  <IconInfo size={11} color="var(--pu)" /> {t("behavioral.today_message")}
                </div>
                <div style={{ fontSize:12, color:"var(--tx2)", lineHeight:1.7, fontStyle:"italic" }}>"{insights.motivational_note}"</div>
              </div>
            )}
          </div>

          {insights.score_interpretation && (
            <div style={{ fontSize:11, color:"var(--tx3)", borderTop:"1px solid var(--bdr)", paddingTop:12, lineHeight:1.6, display:"flex", gap:8, alignItems:"flex-start" }}>
              <IconInfo size={13} style={{ flexShrink:0, marginTop:1, opacity:.7 }} />
              <div><strong style={{ color:"var(--tx2)" }}>{t("behavioral.fbs_interpretation")}: </strong>{insights.score_interpretation}</div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}


