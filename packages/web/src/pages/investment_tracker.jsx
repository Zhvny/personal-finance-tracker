// ─── investment_tracker.jsx ──────────────────────────────────────────────────
// Investment Tracker page — reads/writes the same SQLite DB as the CLI.
// High Cohesion  : only investment logic lives here.
// Low Coupling   : all API calls via useApi.js, all UI atoms via components.jsx,
//                  all constants from constants.js — zero local redeclaration.

import { useState, useEffect, useCallback } from "react";
import {
  useInvestments, useRealized, useInvHistory, useFxRate,
  apiAddInvestment, apiSellInvestment, apiDeleteInvestment, apiRefreshPrices, apiPrunePortfolio,
  apiToggleFavorite, usePersistedTab, apiFetch,
} from "../finance/useApi.js";
import { fmt, fmtS, fmtShortM, today, TYPE_COLOR, CATEGORIES } from "../finance/constants.js";
import { TYPE_ICON } from "../finance/icon-maps.jsx";
import {
  IconSell, IconDelete, IconAdd, IconRefresh, IconClean,
  IconPieChart, IconBarChart, IconCheck, IconStock, IconCrypto, IconGold,
  IconPortfolio, IconAnalysis, IconStar, IconWallet } from "../icons.jsx";
import TrendChart from "../finance/TrendChart.jsx";

// IDR/USD display helpers — fxRate passed as argument, sourced from /api/config
// Never hardcoded: useFxRate() hook returns backend value with 16500 fallback.
const fmtUSD = (n, fxRate) => {
  const val = Number(n || 0);
  const rate = Number(fxRate || 16500);
  return `$${(val / rate).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
const fmtCur = (n, usd, fxRate) => usd ? fmtUSD(n, fxRate) : fmt(Number(n || 0));
import {
  Tabs, Modal, ConfirmDialog, LoadingSpinner, ApiError, Empty,
  FormGroup, FormRow, PLBadge, SumBox, Skeleton
} from "../components.jsx";

// ── Skeletons ───────────────────────────────────────────────────────────────
function PortfolioSkeleton() {
  return (
    <>
      <div className="sg inv-stat-grid">
        {[1,2,3].map(i => <div key={i} className="sc"><Skeleton h={10} mb={10} w="40%" /><Skeleton h={24} w="70%" /></div>)}
      </div>
      <div className="card">
        <div className="card-h"><Skeleton h={18} w={120} /></div>
        <div className="card-b">
          {[1,2,3,4,5].map(i => <Skeleton key={i} h={45} mb={12} />)}
        </div>
      </div>
    </>
  );
}

function AnalysisSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="g2">
        <div className="card">
          <div className="card-h"><Skeleton h={18} w={150} /></div>
          <div className="card-b">
            {[1,2,3].map(i => <div key={i} style={{marginBottom:15}}><Skeleton h={12} mb={6} w="30%" /><Skeleton h={8} /></div>)}
          </div>
        </div>
        <div className="card">
          <div className="card-h"><Skeleton h={18} w={150} /></div>
          <div className="card-b">
            {[1,2,3,4].map(i => <Skeleton key={i} h={20} mb={12} />)}
          </div>
        </div>
      </div>
      <div className="card"><Skeleton h={200} /></div>
    </div>
  );
}

function RealizedSkeleton() {
  return (
    <>
      <div className="sg">
        {[1,2,3].map(i => <div key={i} className="sc"><Skeleton h={10} mb={10} w="40%" /><Skeleton h={24} w="70%" /></div>)}
      </div>
      <div className="card">
        <div className="card-h"><Skeleton h={18} w={140} /></div>
        <div className="card-b">
          {[1,2,3,4].map(i => <Skeleton key={i} h={40} mb={12} />)}
        </div>
      </div>
    </>
  );
}

// ── Sub-component: Holdings table ─────────────────────────────────────────────
function HoldingsTable({ investments, onSell, onDelete, onToggleFavorite, showUSD = false, fxRate = 16500 }) {
  if (!investments.length) return <Empty variant="investment" msg="Portfolio kosong." sub="Tambah investasi pertamamu untuk mulai membangun aset!" />;
  return (
    <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Scrollable data table">
        <table className="tbl">
        <thead>
          <tr>
            <th style={{ width: 30 }}></th>
            <th className="col-cat">Ticker</th><th className="tbl-col-hide-xs">Type</th>
            <th className="tbl-col-hide-sm r">Qty</th>
            <th className="tbl-col-hide-sm r">Remaining</th>
            <th className="tbl-col-hide-sm r">Buy Price</th>
            <th className="tbl-col-hide-sm r">Curr. Price</th>
            <th className="r col-amt">P/L</th><th className="r">P/L %</th>
            <th className="col-act"></th>
          </tr>
        </thead>
        <tbody>
          {investments.map(inv => {
            const assetType = String(inv.asset_type || "stock");
            const buyPrice = Number(inv.buy_price || 0);
            const qty = Number(inv.quantity || 0);
            const remQty = Number(inv.remaining_quantity ?? inv.quantity ?? 0);
            
            // Value in IDR (sourced from Backend buy_price_idr)
            const buyValueIdr = inv.buy_price_idr != null 
              ? Number(inv.buy_price_idr) 
              : (inv.buy_currency === "IDR" ? buyPrice : buyPrice * fxRate);
            // Current price in IDR (sourced from Backend current_price_idr)
            const hasLivePrice = inv.current_price_idr != null;
            const currPriceIdr = hasLivePrice ? Number(inv.current_price_idr) : buyValueIdr;
            
            // P/L calculated on Backend (InvestmentService) — Frontend strictly consumes backend output
            const plIdr = inv.pl != null ? Number(inv.pl) : (currPriceIdr - buyValueIdr) * remQty;
            const plPct = inv.pl_pct != null ? Number(inv.pl_pct) : (buyValueIdr > 0 ? ((currPriceIdr - buyValueIdr) / buyValueIdr) * 100 : 0);

            return (
              <tr key={inv.id || Math.random()} className={inv.is_favorite ? "fav-row" : ""}>
                <td>
                  <button className="btn-icon" onClick={() => onToggleFavorite(inv.id)} title="Toggle Favorite">
                    <IconStar size={14} color={inv.is_favorite ? "var(--yl)" : "var(--tx3)"} style={{ fill: inv.is_favorite ? "var(--yl)" : "none" }} />
                  </button>
                </td>
                <td className="col-cat tkr">{String(inv.ticker || "")}</td>
                <td className="tbl-col-hide-xs"><span className={`ityp ${assetType}`} style={{display:'inline-flex',alignItems:'center',gap:5}}>{TYPE_ICON[assetType]?.({ size: 12 })} {assetType}</span></td>
                <td className="tbl-col-hide-sm r" style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{qty}</td>
                <td className="tbl-col-hide-sm r" style={{ fontFamily: "var(--mono)", fontSize: 12 }}>
                  {remQty}
                  {inv.status === "partial_sold" && <span style={{ marginLeft: 4, fontSize: 10, color: "var(--yl)" }}>◆</span>}
                </td>
                <td className="tbl-col-hide-sm r" style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{fmtCur(buyValueIdr, showUSD, fxRate)} {showUSD ? "USD" : "IDR"}</td>
                <td className="tbl-col-hide-sm r" style={{ fontFamily: "var(--mono)", fontSize: 11, color: hasLivePrice ? "var(--cy)" : "var(--tx3)" }}>
                  {hasLivePrice 
                    ? fmtCur(currPriceIdr, showUSD, fxRate) 
                    : <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--tx3)" }}>{fmtCur(currPriceIdr, showUSD, fxRate)} <span style={{fontSize:9, padding:"1px 4px", borderRadius:4, background:"var(--bg4)", color:"var(--tx3)"}} title="Harga pasar belum tersedia; menggunakan Buy Price">Buy Price</span></span>}
                </td>
                <td className="r">
                  {hasLivePrice
                    ? <PLBadge pl={showUSD ? plIdr / fxRate : plIdr} isUSD={showUSD} />
                    : <span className="pill dim" style={{fontSize:9}} title="P/L membutuhkan data harga pasar">N/A</span>}
                </td>
                <td className="r">
                  {hasLivePrice
                    ? <span className={`pill ${plPct >= 0 ? "g" : "r"}`}>{plPct >= 0 ? "+" : ""}{plPct.toFixed(1)}%</span>
                    : <span className="pill dim">—</span>}
                </td>
                <td className="col-act">
                  <div style={{ display: "flex", gap: 5, flexWrap: "nowrap", alignItems: "center" }}>
                    {inv.status !== "sold" && (
                      <button className="btn btn-d btn-s btn-sell" onClick={() => onSell(inv)}>
                        <IconSell size={12} /> <span className="btn-sell-text">Sell</span>
                      </button>
                    )}
                    <button className="btn btn-g btn-s" onClick={() => onDelete(inv.id)}>
                      <IconDelete size={12} />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Sub-component: Price history chart for a single holding ──────────────────
function PriceHistoryChart({ inv }) {
  const { data: history, loading } = useInvHistory(inv?.id);
  if (!inv) return null;
  if (loading) return <div style={{ padding: 12, fontSize: 11, color: "var(--tx3)" }}>Loading…</div>;
  if (!history?.length || history.length < 2) return (
    <div style={{ padding: 12, fontSize: 11, color: "var(--tx3)" }}>
      No price history found for this period. 
      (Purchase date: {inv.buy_date?.slice(0, 10)})
    </div>
  );

  return (
    <div style={{ position: "relative" }}>
      <div style={{ 
        position: "absolute", top: 12, right: 12, zIndex: 10,
        fontSize: 10, fontWeight: 900, color: "var(--tx3)", 
        background: "var(--bg3)", padding: "2px 8px", borderRadius: 4,
        border: "1px solid var(--bdr2)", letterSpacing: 0.5,
        textTransform: "uppercase"
      }}>
        Since Purchase ({inv.buy_date?.slice(0, 10)})
      </div>
      <TrendChart
        title={`${inv.ticker} — Price History`}
        height={200}
        fmt={n => `Rp${Math.round(n).toLocaleString("id-ID")}`}
        series={[{
          key: "price", label: "Price (IDR)", color: TYPE_COLOR[inv.asset_type] || "var(--ind-b)",
          data: history.map(h => ({ label: h.snapshot_date?.slice(0, 10), value: h.price_idr })),
        }]}
      />
    </div>
  );
}

// ── Sub-component: Portfolio value over time (all active holdings P/L sum) ────
function PortfolioTrendChart({ investments }) {
  // Build per-asset type value breakdown using available data
  const types = [...new Set(investments.map(i => i.asset_type))];
  if (!investments.length || types.length === 0) return null;

  // PL% per ticker (current snapshot only — no time series without history fetch)
  const hasPL = investments.filter(i => i.pl != null && i.pl !== undefined);
  if (!hasPL.length) return null;

  return (
    <div className="card">
      <div className="card-h"><span className="card-t">Unrealized P/L per Asset</span></div>
      <div className="card-b">
        {hasPL.sort((a, b) => (b.pl || 0) - (a.pl || 0)).map(inv => {
          const color = (inv.pl || 0) >= 0 ? "var(--gr)" : "var(--rd)";
          const maxPL = Math.max(...hasPL.map(i => Math.abs(i.pl || 0)), 1);
          const plPctNum = inv.pl_pct != null ? Number(inv.pl_pct) : null;
          return (
            <div key={inv.id || inv.ticker} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                <span style={{ fontWeight: 600, color: "var(--tx1)" }}>{inv.ticker}</span>
                <span style={{ fontFamily: "var(--mono)", fontSize: 11, color }}>
                  {(inv.pl || 0) >= 0 ? "+" : ""}{fmtS(inv.pl || 0)}
                  {plPctNum != null && !isNaN(plPctNum) ? ` (${plPctNum >= 0 ? "+" : ""}${plPctNum.toFixed(1)}%)` : ""}
                </span>
              </div>
              <div style={{ height: 6, background: "var(--bg4)", borderRadius: 4 }}>
                <div style={{
                  height: "100%", borderRadius: 4, background: color,
                  width: `${Math.min(100, (Math.abs(inv.pl || 0) / maxPL) * 100)}%`,
                  marginLeft: (inv.pl || 0) >= 0 ? 0 : undefined,
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Sub-component: Allocation chart ──────────────────────────────────────────
function AllocationChart({ investments }) {
  const byType = investments.reduce((acc, inv) => {
    const val = (inv.current_price_idr ?? inv.buy_price) * (inv.remaining_quantity ?? inv.quantity);
    acc[inv.asset_type] = (acc[inv.asset_type] || 0) + val;
    return acc;
  }, {});
  const total = Object.values(byType).reduce((s, v) => s + v, 0);

  if (!investments.length) return <Empty variant="investment" msg="Portfolio masih kosong." sub="Tambahkan aset pertama untuk melihat distribusi alokasi portfolio kamu." />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Object.entries(byType).map(([type, val]) => {
        const pct = total > 0 ? val / total * 100 : 0;
        return (
          <div key={type}>
            {/* Label row */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <span className={`ityp ${type}`} style={{ display:"inline-flex", alignItems:"center", gap:4, fontSize:11 }}>
                <div style={{ width:8, height:8, borderRadius:2, background: TYPE_COLOR[type] || "gray", flexShrink:0 }} />
                {TYPE_ICON[type]?.({ size: 11 })} {type}
              </span>
              <div style={{ display:"flex", gap:8, alignItems:"center", flexShrink:0 }}>
                <span style={{ fontSize:11, fontFamily:"var(--mono)", color:"var(--tx2)", fontWeight:600 }}>{pct.toFixed(1)}%</span>
                <span style={{ fontSize:11, fontFamily:"var(--mono)", color:"var(--tx3)" }}>{fmtS(val)}</span>
              </div>
            </div>
            {/* Progress bar */}
            <div className="prog-wrap">
              <div className="prog-fill" style={{ width: `${pct}%`, background: TYPE_COLOR[type] || "gray" }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Sub-component: P/L bar chart ──────────────────────────────────────────────
function PLChart({ investments }) {
  const active = investments.filter(i => i.pl !== null && i.pl !== undefined);
  if (!active.length) return <Empty variant="investment" msg="Belum ada data harga live." sub="Refresh harga untuk melihat P/L chart setiap aset." />;
  const maxAbs = Math.max(...active.map(i => Math.abs(i.pl)), 1);
  return (
    <div>
      {active.map(inv => (
        <div key={inv.id} className="pl-row">
          <span className="tkr" style={{ width: "clamp(56px, 18vw, 80px)", fontSize: 12, flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{inv.ticker}</span>
          <div className="pl-bar-bg">
            <div className="pl-bar" style={{ width: `${Math.abs(inv.pl) / maxAbs * 100}%`, background: inv.pl >= 0 ? "var(--gr)" : "var(--rd)" }} />
          </div>
          <span style={{ fontSize: 12, fontFamily: "var(--mono)", color: inv.pl >= 0 ? "var(--gr)" : "var(--rd)", fontWeight: 700, width: "clamp(80px, 28vw, 120px)", textAlign: "right", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {fmtS(inv.pl)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Sub-component: Realized P/L ───────────────────────────────────────────────
function RealizedPL({ data }) {
  if (!data) return <LoadingSpinner />;
  const { transactions, summary } = data;
  return (
    <>
      <div className="sg">
        <div className="sc" style={{ borderTop: `2px solid ${summary.total_pl >= 0 ? "var(--gr)" : "var(--rd)"}` }}>
          <div className="sc-lbl">Total Realized P/L</div>
          <div className={`sc-val ${summary.total_pl >= 0 ? "g" : "r"}`}>{fmtS(summary.total_pl)}</div>
        </div>
        <div className="sc">
          <div className="sc-lbl">Win / Loss</div>
          <div className="sc-val n">
            <span style={{ color: "var(--gr)" }}>{summary.wins}W</span> / <span style={{ color: "var(--rd)" }}>{summary.losses}L</span>
          </div>
        </div>
        <div className="sc">
          <div className="sc-lbl">Win Rate</div>
          <div className="sc-val i">{summary.win_rate?.toFixed(0) || 0}%</div>
        </div>
      </div>
      <div className="card">
        <div className="card-h"><span className="card-t">Closed Positions</span></div>
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Scrollable data table">
        <table className="tbl">
            <thead>
              <tr>
                <th>Date</th>
                <th>Ticker</th>
                <th className="tbl-col-hide-sm r">Qty</th>
                <th className="tbl-col-hide-sm r">Sell Price</th>
                <th className="r">Realized P/L</th>
                <th className="r">P/L %</th>
              </tr>
            </thead>
            <tbody>
              {!transactions.length && <tr><td colSpan={6}><Empty variant="investment" msg="Belum ada posisi yang ditutup." sub="Posisi yang telah dijual (closed) akan muncul di sini sebagai riwayat transaksi." /></td></tr>}
              {transactions.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--tx2)" }}>{r.sell_date?.slice(0, 10)}</td>
                  <td className="tkr">{r.ticker}</td>
                  <td className="tbl-col-hide-sm r" style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{r.quantity}</td>
                  <td className="tbl-col-hide-sm r" style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{fmt(r.sell_price)} {r.sell_currency}</td>
                  <td className="r"><PLBadge pl={r.realized_pl_idr} /></td>
                  <td className="r"><span className={`pill ${Number(r.realized_pl_pct || 0) >= 0 ? "g" : "r"}`}>{Number(r.realized_pl_pct || 0) >= 0 ? "+" : ""}{Number(r.realized_pl_pct || 0).toFixed(1)}%</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ── Add Investment Modal ───────────────────────────────────────────────────────
function AddModal({ onClose, onSaved }) {
  const [form, setForm] = useState({ ticker: "", asset_type: "stock", quantity: "", buy_price: "", buy_currency: "IDR", buy_date: today() });
  const [saving, setSaving] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleSave = async () => {
    if (!form.ticker || !form.quantity || !form.buy_price) return;
    setSaving(true);
    try {
      await apiAddInvestment({ ...form, quantity: +form.quantity, buy_price: +form.buy_price });
      onSaved("Investasi berhasil disimpan!");
      onClose();
    } catch (e) { onSaved(e.message, "error"); }
    finally { setSaving(false); }
  };

  return (
    <Modal title="Add Investment" onClose={onClose}
      footer={<><button className="btn btn-g" onClick={onClose}>Cancel</button><button className="btn btn-p" onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save"}</button></>}>
      <FormRow>
        <FormGroup label="Ticker"><input className="fc" placeholder="BBCA.JK / BTC / XAU" value={form.ticker} onChange={set("ticker")} /></FormGroup>
        <FormGroup label="Asset Type">
          <select className="fc sel" value={form.asset_type} onChange={set("asset_type")}>
            <option value="stock">Stock</option>
            <option value="crypto">Crypto</option>
            <option value="gold">Gold</option>
          </select>
        </FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label="Quantity"><input className="fc" type="number" step="any" placeholder="100" value={form.quantity} onChange={set("quantity")} /></FormGroup>
        <FormGroup label="Buy Price / unit"><input className="fc" type="number" step="any" placeholder="9500" value={form.buy_price} onChange={set("buy_price")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label="Currency">
          <select className="fc sel" value={form.buy_currency} onChange={set("buy_currency")}>
            <option value="IDR">IDR (Rupiah)</option>
            <option value="USD">USD (Dollar)</option>
          </select>
        </FormGroup>
        <FormGroup label="Buy Date"><input className="fc" type="date" value={form.buy_date} onChange={set("buy_date")} /></FormGroup>
      </FormRow>
    </Modal>
  );
}

// ── Sell Modal ─────────────────────────────────────────────────────────────────
function SellModal({ inv, onClose, onSaved }) {
  const [form, setForm] = useState({ quantity: "", sell_price: "", sell_currency: "IDR", sell_date: today(), fees: "0" });
  const [saving, setSaving] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const fxRate  = useFxRate();  // sourced from /api/config, not hardcoded
  const buyIdr  = inv.buy_price_idr != null ? Number(inv.buy_price_idr) : (inv.buy_currency === "IDR" ? inv.buy_price : inv.buy_price * fxRate);
  const sellIdr = form.sell_currency === "IDR" ? +form.sell_price : +form.sell_price * fxRate;
  const estPL   = form.quantity && form.sell_price
    ? (sellIdr - buyIdr) * +form.quantity - +form.fees
    : null;
  const estPct  = buyIdr > 0 ? (sellIdr - buyIdr) / buyIdr * 100 : 0;
  const remaining = inv.remaining_quantity ?? inv.quantity;

  const handleSell = async () => {
    if (!form.quantity || !form.sell_price || +form.quantity > remaining) return;
    setSaving(true);
    try {
      const res = await apiSellInvestment(inv.id, {
        quantity: +form.quantity, sell_price: +form.sell_price,
        sell_currency: form.sell_currency, sell_date: form.sell_date, fees: +form.fees,
      });
      onSaved(`Sold ${form.quantity} ${inv.ticker} — P/L: ${fmtS(res.realized_pl)}`, res.realized_pl >= 0 ? "success" : "error");
      onClose();
    } catch (e) { onSaved(e.message, "error"); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={`Sell ${inv.ticker}`} onClose={onClose}
      footer={<><button className="btn btn-g" onClick={onClose}>Cancel</button><button className="btn btn-d" onClick={handleSell} disabled={saving}>{saving ? "Processing…" : "Execute Sell"}</button></>}>
      <div style={{ background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: "var(--r)", padding: "11px 13px", marginBottom: 14, fontFamily: "var(--mono)", fontSize: 12 }}>
        <div style={{ color: "var(--tx2)" }}>You own: <strong style={{ color: "var(--tx)" }}>{remaining} units</strong></div>
        <div style={{ color: "var(--tx2)" }}>Buy price: <strong style={{ color: "var(--tx)" }}>{fmt(inv.buy_price)} {inv.buy_currency}</strong></div>
      </div>
      <FormRow>
        <FormGroup label={`Qty to Sell (max ${remaining} ${inv.asset_type === 'gold' ? 'grams' : 'units'})`}><input className="fc" type="number" step="any" value={form.quantity} onChange={set("quantity")} /></FormGroup>
        <FormGroup label={`Sell Price / ${inv.asset_type === 'gold' ? 'gram' : 'unit'}`}><input className="fc" type="number" step="any" value={form.sell_price} onChange={set("sell_price")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label="Currency">
          <select className="fc sel" value={form.sell_currency} onChange={set("sell_currency")}>
            <option value="IDR">IDR</option>
            <option value="USD">USD</option>
          </select>
        </FormGroup>
        <FormGroup label="Sell Date"><input className="fc" type="date" value={form.sell_date} onChange={set("sell_date")} /></FormGroup>
      </FormRow>
      <FormGroup label="Fees (IDR)"><input className="fc" type="number" placeholder="0" value={form.fees} onChange={set("fees")} /></FormGroup>
      {estPL !== null && (
        <div style={{ background: "var(--ind-d)", border: "1px solid rgba(79,110,247,.25)", borderRadius: "var(--r)", padding: "10px 13px", fontSize: 12, fontFamily: "var(--mono)" }}>
          Est. P/L: <span style={{ color: estPL >= 0 ? "var(--gr)" : "var(--rd)", fontWeight: 700 }}>
            {fmtS(estPL)} ({estPct >= 0 ? "+" : ""}{estPct.toFixed(1)}%)
          </span>
        </div>
      )}
    </Modal>
  );
}

// ── Sub-component: Analysis tab — must be a real component (not IIFE) so hooks obey Rules of Hooks
function AnalysisTab({ investments, active }) {
  const [selectedId, setSelectedId] = useState(active[0]?.id ?? null);
  const selectedInv = active.find(i => i.id === selectedId) ?? active[0] ?? null;
  return (
    <>
      <div className="g2">
        <div className="card">
          <div className="card-h"><span className="card-t">Allocation by Type</span></div>
          <div className="card-b"><AllocationChart investments={investments} /></div>
        </div>
        <div className="card">
          <div className="card-h"><span className="card-t">P/L per Asset</span></div>
          <div className="card-b"><PLChart investments={investments} /></div>
        </div>
      </div>
      <PortfolioTrendChart investments={active} />
      {active.length > 0 && (
        <div className="card">
          <div className="card-h">
            <span className="card-t">Price History</span>
            <select className="fc sel" style={{ width: "fit-content", minWidth: 100, flex: "0 0 auto" }}
              value={selectedId ?? ""} onChange={e => setSelectedId(+e.target.value)}>
              {active.map(inv => <option key={inv.id} value={inv.id}>{inv.ticker}</option>)}
            </select>
          </div>

          <div className="card-b">
            <PriceHistoryChart inv={selectedInv} />
          </div>
        </div>
      )}
    </>
  );
}

// ── Main exported component ───────────────────────────────────────────────────

// ── Main exported component ───────────────────────────────────────────────────

function NetWorthPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/net-worth').then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--tx3)', fontSize: 13 }}>Loading net worth…</div>;
  if (!data) return <Empty variant='expense' msg='No net worth data.' />;

  return (
    <div className='card'>
      <div className='card-h'><span className='card-t'>Net Worth</span></div>
      <div className='card-b'>
        <div className='sg'>
          <div className='sc'><div className='sc-lbl'>Total Assets</div><div className='sc-val n' style={{fontSize:16}}>{fmt(data.total_assets)}</div></div>
          <div className='sc'><div className='sc-lbl'>Total Liabilities</div><div className='sc-val r' style={{fontSize:16}}>{fmt(data.total_liabilities)}</div></div>
          <div className='sc' style={{ borderTop: '2px solid ' + ((data.net_worth ?? 0) >= 0 ? 'var(--gr)' : 'var(--rd)') }}>
            <div className='sc-lbl'>Net Worth</div>
            <div className={'sc-val ' + ((data.net_worth ?? 0) >= 0 ? 'g' : 'r')} style={{fontSize:18}}>{fmt(data.net_worth)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function InvestmentTracker({ onToast }) {
  const [tab, setTab]           = usePersistedTab("investment", "portfolio");
  const [showAdd, setShowAdd]   = useState(false);
  const [sellTarget, setSell]   = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [confirmPrune, setConfirmPrune] = useState(false);
  const [showUSD, setShowUSD]   = useState(false);  // IDR/USD currency toggle
  const fxRate = useFxRate();   // sourced from /api/config — single source of truth

  const { data: invData, loading: invLoading, error: invError, reload: reloadInv } = useInvestments();
  const { data: realData, loading: realLoading, reload: reloadReal } = useRealized();

  /**
   * refreshPrices — calls POST /api/investments/refresh-prices which:
   *   1. Hits live price services (yfinance / LogamMulia / CoinGecko)
   *   2. Writes today's snapshot into historical_prices
   *   3. Returns fresh investments list
   * Runs on mount so the table always shows live prices when the page opens.
   */
  const refreshPrices = useCallback(async (silent = false) => {
    setRefreshing(true);
    try {
      await apiRefreshPrices();
      await reloadInv();
      if (!silent) onToast("Harga diperbarui dari pasar.");
    } catch (e) {
      if (!silent) onToast("Price refresh failed: " + e.message, "error");
    } finally {
      setRefreshing(false);
    }
  }, [reloadInv, onToast]);

  // Auto-refresh live prices after page renders (deferred — don't block initial render)
  useEffect(() => {
    const timer = setTimeout(() => refreshPrices(true), 800);
    return () => clearTimeout(timer);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Phase 4: 5-minute polling for real-time pricing
  useEffect(() => {
    const pollId = setInterval(() => {
      console.log("Phase 4: Auto-refreshing prices (5m polling)...");
      refreshPrices(true);
    }, 300_000); // 300,000ms = 5 minutes
    return () => clearInterval(pollId);
  }, [refreshPrices]);

  const investments = invData || [];
  // API already excludes status="sold"; active is the same list
  const active      = investments.filter(i => i.status !== "sold");

  const handleToggleFavorite = async (id) => {
    try {
      await apiToggleFavorite(id);
      await reloadInv();
    } catch (e) {
      onToast("Gagal mengubah status favorit: " + e.message, "error");
    }
  };

  const totalPL     = active.reduce((s, i) => s + Number(i.pl ?? 0), 0);
  const totalBuy    = active.reduce((s, i) => {
    const qty = Number(i.remaining_quantity ?? i.quantity ?? 0);
    const priceIdr = i.buy_price_idr != null 
      ? Number(i.buy_price_idr) 
      : (i.buy_currency === "IDR" ? Number(i.buy_price || 0) : Number(i.buy_price || 0) * fxRate);
    return s + (priceIdr * qty);
  }, 0);
  const totalCurr   = active.reduce((s, i) => {
    const qty = Number(i.remaining_quantity ?? i.quantity ?? 0);
    const currPriceIdr = i.current_price_idr != null 
      ? Number(i.current_price_idr) 
      : (i.buy_price_idr != null ? Number(i.buy_price_idr) : (i.buy_currency === "IDR" ? Number(i.buy_price || 0) : Number(i.buy_price || 0) * fxRate));
    return s + (currPriceIdr * qty);
  }, 0);

  const handleToast = (msg, type = "success") => { onToast(msg, type); reloadInv(); reloadReal(); };
  const handleDelete = async id => {
    await apiDeleteInvestment(id);
    handleToast("Deleted.");
  };

  const handlePrune = () => setConfirmPrune(true);
  const doPrune = async () => {
    try {
      const res = await apiPrunePortfolio();
      handleToast(`Cleaned: ${res.deleted} removed, ${res.kept_holding} holdings kept.`);
    } catch (e) {
      handleToast("Clean DB failed: " + e.message, "error");
    }
  };

  if (invError) return <ApiError error={invError} onRetry={reloadInv} />;

  return (
    <>
      {confirmPrune && (
        <ConfirmDialog
          message={"Remove all fully-sold (zero remaining) entries from the portfolio DB? All P/L records are kept. Only empty rows are removed."}
          confirmLabel="Clean DB"
          danger
          onConfirm={doPrune}
          onCancel={() => setConfirmPrune(false)}
        />
      )}
    <div>
      <h1 className="sr-only">Investment Tracker — Portfolio, Stocks, Crypto &amp; Gold</h1>
      <Tabs
        tabs={[
          { key: "portfolio", label: "Portfolio",    icon: <IconStock    size={13} /> },
          { key: "analysis",  label: "Analysis",     icon: <IconBarChart size={13} /> },
          { key: "realized",  label: "Realized P/L", icon: <IconCheck    size={13} /> },
          { key: "networth",  label: "Net Worth",    icon: <IconWallet   size={13} /> },
        ]}
        active={tab} onChange={setTab}
      />

      {/* ── PORTFOLIO ── */}
      {tab === "portfolio" && (
        <>
          {invLoading ? <PortfolioSkeleton /> : (
            <>
              <div className="sg inv-stat-grid">
                <div className="sc"><div className="sc-lbl">Total Invested</div><div className="sc-val n" style={{fontSize:16}}>{showUSD ? fmtUSD(totalBuy, fxRate) : fmtShortM(totalBuy)}</div></div>
                <div className="sc inv"><div className="sc-lbl">Current Value</div><div className="sc-val c" style={{fontSize:16}}>{showUSD ? fmtUSD(totalCurr, fxRate) : fmtShortM(totalCurr)}</div></div>
                <div className="sc" style={{ borderTop: `2px solid ${totalPL >= 0 ? "var(--gr)" : "var(--rd)"}` }}>
                  <div className="sc-lbl">Unrealized P/L</div>
                  <div className={`sc-val ${totalPL >= 0 ? "g" : "r"}`} style={{fontSize:15}}>{showUSD ? fmtUSD(totalPL, fxRate) : fmtShortM(totalPL)}</div>
                  <div className="sc-chg nt">{totalBuy > 0 ? (totalPL / totalBuy * 100).toFixed(1) : 0}% overall</div>
                </div>
              </div>

              <div className="tab-toolbar">
                <div className="toggle-group">
                  <button className={`toggle-btn ${!showUSD ? "active primary" : ""}`} onClick={() => setShowUSD(false)}>IDR</button>
                  <button className={`toggle-btn ${showUSD ? "active info" : ""}`} onClick={() => setShowUSD(true)}>USD</button>
                </div>
                <button className="btn btn-g btn-s" onClick={() => refreshPrices(false)} disabled={refreshing}>
                  <IconRefresh size={12} style={{ animation: refreshing ? "comp-spin 1s linear infinite" : "none" }} />
                  {refreshing ? "Refreshing..." : "Refresh Prices"}
                </button>
                <button className="btn btn-g btn-s" onClick={handlePrune} title="Remove fully-sold entries from DB">
                  <IconClean size={12} /> Prune
                </button>
                <button className="btn btn-p btn-s" onClick={() => setShowAdd(true)}>
                  <IconAdd size={12} /> Add Investment
                </button>
              </div>

              <div className="card">
                <div className="card-h">
                  <span className="card-t">Portfolio Holdings</span>
                </div>
                <HoldingsTable
                  investments={active}
                  onSell={setSell}
                  onDelete={handleDelete}
                  onToggleFavorite={handleToggleFavorite}
                  showUSD={showUSD}
                  fxRate={fxRate}
                />
              </div>
            </>
          )}
        </>
      )}


      {/* ── ANALYSIS ── */}
      {tab === "analysis" && (
        invLoading ? <AnalysisSkeleton /> : <AnalysisTab investments={investments} active={active} />
      )}

      {/* ── REALIZED ── */}
      {tab === "realized" && (
        realLoading
          ? <RealizedSkeleton />
          : <RealizedPL data={realData} />
      )}

      {/* ── NET WORTH ── */}
      {tab === "networth" && (
        <NetWorthPanel />
      )}

      {/* Modals */}
      {showAdd && <AddModal onClose={() => setShowAdd(false)} onSaved={(msg, t) => handleToast(msg, t)} />}
      {sellTarget && <SellModal inv={sellTarget} onClose={() => setSell(null)} onSaved={(msg, t) => handleToast(msg, t)} />}
    </div>
    </>
  );
}

