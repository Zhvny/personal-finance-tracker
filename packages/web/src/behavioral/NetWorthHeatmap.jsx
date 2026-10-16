// ─── NetWorthHeatmap.jsx ──────────────────────────────────────────────────────
// Feature 1 — Balance Editing Rules:
//   Only Emergency Fund is editable. Cash, Physical Cash, Bank Savings, and
//   Crypto cannot be manually entered. Cash on Hand is computed.
//
// Feature 2 — Physical Cash & Bank Savings Accounting:
//   Total Credit = Net Current = Income − Expense (this month) from /balances/total-credit.
//   Bank Savings is just how cash is allocated — if bankSav = 0 user can't transfer,
//   but Total Credit itself is always the net position, independent of allocation.
//   Users can transfer value between Physical Cash ↔ Bank Savings.
//   Transfers never change Total Credit.
//
// Feature 3 — Crypto from portfolio.db (READ-ONLY):
//   Crypto values are always loaded from portfolio.db, never editable.
//
// Theory: [PT] Prospect Theory — red cells use 1.8× intensity.
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from "react";
import { createPortal } from "react-dom";
import { useBalances, apiSetEmergencyFund, apiTransferBalance } from "../finance/useApi.js";
import { fmtRp } from "../finance/constants.js";
import {
  IconCash, IconBank, IconStock, IconCrypto, IconGold,
  IconShield, IconDebt, IconAnalysis, IconWallet,
} from "../icons.jsx";
const sign   = v => v >= 0 ? "+" : "";

// Icon map: label → React icon component
const CELL_ICON_MAP = {
  "Cash":           IconCash,
  "Bank Savings":   IconBank,
  "Stocks":         IconStock,
  "Crypto":         IconCrypto,
  "Gold":           IconGold,
  "Emergency Fund": IconShield,
  "Debt":           IconDebt,
  "Net Worth":      IconAnalysis,
  "Other":          IconWallet,
};

// ── Live pulse dot ─────────────────────────────────────────────────────────────
function PulseDot({ color }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 10, height: 10, alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <span style={{
        position: "absolute", width: "100%", height: "100%", borderRadius: "50%",
        background: color, opacity: 0.35,
        animation: "hm-pulse 2.2s cubic-bezier(.4,0,.6,1) infinite",
      }} />
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "block" }} />
    </span>
  );
}

// ── Heatmap cell ──────────────────────────────────────────────────────────────
function HeatCell({ cell, large = false }) {
  const [hov, setHov] = useState(false);
  const CellIcon  = CELL_ICON_MAP[cell.label] ?? IconWallet;
  const hasChange = cell.pct != null && Math.abs(cell.pct) > 0.001;

  const bgAlpha = (str) => {
    if (!hov) return str;
    return str.replace(/[\d.]+\)$/, v => {
      const n = parseFloat(v);
      return `${Math.min(1, n + 0.1)})`;
    });
  };

  return (
    <div
      className="heatmap-cell"
      data-large={large ? "true" : undefined}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: bgAlpha(cell.color),
        border: `1px solid ${cell.borderColor}`,
        borderRadius: "var(--rl)",
        padding: large ? "20px 22px" : "16px 16px",
        cursor: "default",
        transition: "background .2s, transform .15s, box-shadow .15s",
        transform: hov ? "translateY(-2px)" : "none",
        boxShadow: hov ? `0 8px 28px ${cell.borderColor}` : "none",
        position: "relative",
        overflow: "hidden",
        // gridColumn handled by wrapper div for large cells
      }}
    >
      {hasChange && (
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none",
          background: cell.isNegative
            ? `radial-gradient(ellipse at 50% 0%, rgba(248,113,113,${cell.intensity * 0.12}) 0%, transparent 65%)`
            : `radial-gradient(ellipse at 50% 0%, rgba(52,211,153,${cell.intensity  * 0.12}) 0%, transparent 65%)`,
        }} />
      )}

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: large ? 10 : 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <CellIcon size={large ? 16 : 13} color="rgba(255,255,255,.75)" style={{ flexShrink:0 }} />
          <span style={{ fontSize: large ? 13 : 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".7px", color: "rgba(255,255,255,.65)" }}>
            {cell.label}
          </span>
        </div>
        <PulseDot color={hasChange ? cell.textColor : "rgba(255,255,255,.25)"} />
      </div>

      <div className="hm-value" style={{
        fontFamily: "'Space Mono', monospace",
        fontSize: large ? 22 : 16,
        fontWeight: 700,
        color: "rgba(255,255,255,.95)",
        marginBottom: 5,
        lineHeight: 1,
      }}>
        {fmtRp(cell.current)}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, minHeight: 16 }}>
        {hasChange ? (
          <>
            <span style={{ fontFamily: "'Space Mono', monospace", fontSize: large ? 13 : 11, fontWeight: 700, color: cell.textColor }}>
              {sign(cell.pct)}{cell.pctDisplay}%
            </span>
            <span style={{ fontSize: large ? 10 : 9, color: "rgba(255,255,255,.35)" }}>
              vs {fmtRp(cell.previous)}
            </span>
          </>
        ) : (
          <span style={{ fontSize: 9, color: "rgba(255,255,255,.25)" }}>{cell.current != null ? "No change" : "Data pending"}</span>
        )}
      </div>

      {hasChange && (
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0, height: 3,
          background: cell.borderColor,
          transformOrigin: "left",
          transform: `scaleX(${cell.intensity})`,
          transition: "transform .7s cubic-bezier(.4,0,.2,1)",
        }} />
      )}
    </div>
  );
}

// ── Legend ─────────────────────────────────────────────────────────────────────
function Legend() {
  return (
    <div style={{
      display: "flex", alignItems: "center", flexWrap: "wrap", gap: 10,
      padding: "8px 12px", background: "var(--bg3)",
      borderRadius: 8, border: "1px solid var(--bdr)",
      fontSize: 10, color: "var(--tx3)",
    }}>
      <span style={{ fontWeight: 600, color: "var(--tx2)" }}>Intensity:</span>
      {[
        { label: "Growth",  from: "rgba(52,211,153,.12)", to: "rgba(52,211,153,.72)" },
        { label: "Decline", from: "rgba(248,113,113,.12)", to: "rgba(248,113,113,.92)" },
      ].map(({ label, from, to }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 48, height: 4, borderRadius: 99, background: `linear-gradient(90deg, ${from}, ${to})` }} />
          <span style={{ color: "var(--tx2)" }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── ReadOnly field ─────────────────────────────────────────────────────────────
function ReadOnlyField({ icon, label, value, hint, badge }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--tx2)", marginBottom: 5, display: "flex", alignItems: "center", gap: 5 }}>
        <span>{icon}</span>{label}
        {badge && (
          <span style={{ marginLeft: "auto", fontSize: 9, padding: "2px 6px", borderRadius: 99, background: "rgba(99,102,241,.18)", color: "rgba(165,180,252,1)", border: "1px solid rgba(99,102,241,.35)" }}>
            {badge}
          </span>
        )}
      </div>
      <div style={{
        width: "100%", boxSizing: "border-box",
        background: "rgba(255,255,255,.04)", border: "1px solid rgba(255,255,255,.08)", borderRadius: 8,
        color: "rgba(255,255,255,.4)", fontSize: 13, padding: "8px 12px", fontFamily: "var(--mono)",
        cursor: "not-allowed", userSelect: "none",
      }}>
        {fmtRp(value)}
      </div>
      <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 3 }}>{hint}</div>
    </div>
  );
}

// ── Transfer Sub-Modal ────────────────────────────────────────────────────────
function TransferModal({ balances, onClose, onSaved }) {
  const [direction, setDirection] = useState("physical_to_bank");
  const [amount, setAmount]       = useState("");
  const [note, setNote]           = useState("");
  const [saving, setSaving]       = useState(false);
  const [err, setErr]             = useState(null);

  const physCash  = balances?.physical_cash  ?? 0;
  const bankSav   = balances?.bank_savings   ?? 0;
  const totalCred = bankSav; // Total Credit = Bank Savings
  const maxAmount = direction === "physical_to_bank" ? physCash : bankSav;

  const handleTransfer = async () => {
    const amt = parseFloat(amount.replace(/[^0-9.]/g, "")) || 0;
    if (amt <= 0) { setErr("Enter a valid amount."); return; }
    if (amt > maxAmount) { setErr(`Insufficient balance (max ${fmtRp(maxAmount)}).`); return; }
    setSaving(true); setErr(null);
    try {
      await apiTransferBalance(direction, amt, note);
      onSaved();
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.72)", zIndex: 1100, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }} onClick={onClose}>
      <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr2)", borderRadius: "var(--rl)", padding: 24, width: "100%", maxWidth: 360, maxHeight: "90vh", overflowY: "auto", boxSizing: "border-box", boxShadow: "0 24px 64px rgba(0,0,0,.6)" }} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--tx1)", marginBottom: 4 }}>Transfer Funds</div>
        <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 16 }}>Move value between Physical Cash and Bank Savings. Total Credit stays unchanged.</div>

        <div style={{ display: "flex", justifyContent: "space-between", background: "var(--bg3)", borderRadius: 8, padding: "8px 12px", marginBottom: 16, border: "1px solid var(--bdr)" }}>
          <span style={{ fontSize: 11, color: "var(--tx3)" }}>Total Credit</span>
          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--grn)", fontFamily: "var(--mono)" }}>{fmtRp(totalCred)}</span>
        </div>

        {/* Current split */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
          {[
            { label: "Physical Cash", value: physCash },
            { label: "Bank Savings",  value: bankSav },
          ].map(({ label, value }) => (
            <div key={label} style={{ background: "var(--bg3)", borderRadius: 8, padding: "8px 10px", border: "1px solid var(--bdr)", textAlign: "center" }}>
              <div style={{ fontSize: 10, color: "var(--tx3)", marginBottom: 3 }}>{label}</div>
              <div style={{ fontSize: 12, fontWeight: 700, fontFamily: "var(--mono)", color: "var(--tx1)" }}>{fmtRp(value)}</div>
            </div>
          ))}
        </div>

        {/* Direction selector */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--tx2)", marginBottom: 6 }}>Direction</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {[
              { val: "physical_to_bank", label: "Cash → Bank" },
              { val: "bank_to_physical", label: "Bank → Cash" },
            ].map(({ val, label }) => (
              <button key={val}
                onClick={() => setDirection(val)}
                style={{
                  padding: "7px 10px", borderRadius: 8, fontSize: 11, fontWeight: 600,
                  border: direction === val ? "1px solid var(--acc)" : "1px solid var(--bdr)",
                  background: direction === val ? "rgba(99,102,241,.18)" : "var(--bg3)",
                  color: direction === val ? "var(--acc)" : "var(--tx2)", cursor: "pointer",
                }}>{label}</button>
            ))}
          </div>
        </div>

        {/* Amount */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--tx2)", marginBottom: 5 }}>Amount (IDR)</div>
          <input type="number" min="0" max={maxAmount} value={amount}
            onChange={e => setAmount(e.target.value)} placeholder="0"
            style={{ width: "100%", boxSizing: "border-box", background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 8, color: "var(--tx1)", fontSize: 16, padding: "10px 12px", minHeight: 44, fontFamily: "var(--mono)", outline: "none" }} />
          <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 3 }}>Max: {fmtRp(maxAmount)}</div>
        </div>

        {/* Note */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--tx2)", marginBottom: 5 }}>Note (optional)</div>
          <input type="text" value={note} onChange={e => setNote(e.target.value)}
            placeholder="e.g. ATM withdrawal"
            style={{ width: "100%", boxSizing: "border-box", background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 8, color: "var(--tx1)", fontSize: 16, padding: "10px 12px", minHeight: 44, outline: "none" }} />
        </div>

        {err && <div style={{ fontSize: 11, color: "var(--rd)", marginBottom: 12 }}>{err}</div>}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn btn-g btn-s" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-grn btn-s" onClick={handleTransfer} disabled={saving}>
            {saving ? "Transferring…" : "Transfer"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

// ── Balance Editor Modal ──────────────────────────────────────────────────────
// Feature 1: Only Emergency Fund is editable.
// Feature 2: Physical Cash / Bank Savings shown read-only with transfer button.
// Feature 3: Crypto shown as read-only, badge "Synced from portfolio.db".
function BalanceEditorModal({ balances, onClose, onSaved }) {
  const [efVal,        setEfVal]        = useState(String(balances?.emergency_fund ?? 0));
  const [saving,       setSaving]       = useState(false);
  const [err,          setErr]          = useState(null);
  const [showTransfer, setShowTransfer] = useState(false);

  const physCash    = balances?.physical_cash  ?? 0;
  const bankSav     = balances?.bank_savings   ?? 0;
  // totalCredit = bank_savings (net current position).
  // Bank Savings = where the net current lives. If bankSav = 0, transfer is impossible.
  // physCash + bankSav is just internal allocation split, NOT the source of truth.
  const totalCredit = bankSav;
  const efNum       = parseFloat(efVal.replace(/[^0-9.]/g, "")) || 0;

  const handleSave = async () => {
    if (efNum < 0) { setErr("Emergency Fund cannot be negative."); return; }
    if (efNum > totalCredit) {
      setErr(`Emergency Fund cannot exceed total cash (${fmtRp(totalCredit)}).`);
      return;
    }
    setSaving(true); setErr(null);
    try {
      await apiSetEmergencyFund(efNum);
      onSaved();
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (showTransfer) {
    return <TransferModal balances={balances} onClose={() => setShowTransfer(false)} onSaved={onSaved} />;
  }

  return createPortal(
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.65)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }} onClick={onClose}>
      <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr2)", borderRadius: "var(--rl)", padding: 24, width: "100%", maxWidth: 400, maxHeight: "90vh", overflowY: "auto", boxSizing: "border-box", boxShadow: "0 24px 64px rgba(0,0,0,.6)" }} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--tx1)", marginBottom: 16 }}>Edit Balances</div>

        {/* Physical Cash + Bank Savings — read-only, with transfer button */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
          <ReadOnlyField icon={<IconCash size={12} />}  label="Physical Cash" value={physCash} hint="" />
          <ReadOnlyField icon={<IconBank size={12} />}  label="Bank Savings"  value={bankSav}  hint="" />
        </div>

        <button
          className="btn btn-g btn-s"
          style={{ width: "100%", marginBottom: 16, fontSize: 11 }}
          onClick={() => setShowTransfer(true)}
        >
          ⇄ Transfer Between Physical Cash & Bank
        </button>

        {/* Emergency Fund — editable */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--tx2)", marginBottom: 5, display: "flex", alignItems: "center", gap: 5 }}>
            Emergency Fund
            <span style={{ marginLeft: "auto", fontSize: 9, padding: "2px 6px", borderRadius: 99, background: "rgba(52,211,153,.15)", color: "rgba(52,211,153,1)", border: "1px solid rgba(52,211,153,.3)" }}>
              Editable
            </span>
          </div>
          <input type="number" min="0" max={totalCredit}
            value={efVal}
            onChange={e => setEfVal(e.target.value)}
            placeholder="0"
            style={{ width: "100%", boxSizing: "border-box", background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 8, color: "var(--tx1)", fontSize: 16, padding: "10px 12px", minHeight: 44, fontFamily: "var(--mono)", outline: "none" }} />
          <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 3 }}>
            Max: {fmtRp(totalCredit)} · Must not exceed Bank Savings
          </div>
        </div>

        {err && <div style={{ fontSize: 11, color: "var(--rd)", marginBottom: 12 }}>{err}</div>}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn btn-g btn-s" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-grn btn-s" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save Emergency Fund"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function NetWorthHeatmap({ data, onReload }) {
  const [showEditor, setShowEditor] = useState(false);
  const { data: balances, reload: reloadBalances } = useBalances();

  if (!data || !data.netWorth) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--tx3)" }}>
        <IconAnalysis size={32} style={{ marginBottom: 12, opacity: 0.5 }} />
        <div>Belum ada data Net Worth untuk periode ini.</div>
      </div>
    );
  }

  const { cells = [], netWorth, monthLabel, prevLabel } = data;

  const handleSaved = () => {
    reloadBalances();
    if (onReload) onReload();
  };

  return (
    <div>
      {/* Period label + edit button (NO Refresh button — hidden per UX feedback) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <div style={{ fontSize: 11, color: "var(--tx3)" }}>
          <span style={{ color: "var(--tx2)", fontWeight: 600 }}>{monthLabel}</span>
          {" "}vs{" "}
          <span style={{ color: "var(--tx2)", fontWeight: 600 }}>{prevLabel || "—"}</span>
        </div>
        <div style={{ display: "flex", gap: 5, alignItems: "center", flexWrap: "wrap" }}>
          <button className="btn btn-g btn-s" onClick={() => setShowEditor(true)} style={{ fontSize: 10 }}>
            Edit Balances
          </button>
          {["Loss Aversion", "Prospect Theory", "Mental Accounting"].map(t => (
            <span key={t} className="nw-theory-tag" style={{
              fontSize: 9, padding: "2px 7px", borderRadius: 99,
              background: "var(--bg3)", color: "var(--tx3)", border: "1px solid var(--bdr)",
            }}>{t}</span>
          ))}
        </div>
      </div>

      {/* Net Worth hero cell */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr" }}>
          <HeatCell cell={netWorth} large />
        </div>
      </div>

      {/* Asset grid — sorted by value desc (biggest = most important = first) */}
      <div className="heatmap-scroll" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 12 }}>
        {(() => {
          const assetCells = cells
            .filter(c => c.label !== "Emergency Fund")
            .sort((a, b) => Math.abs(b.current ?? b.value ?? 0) - Math.abs(a.current ?? a.value ?? 0));
          const efCells    = cells.filter(c => c.label === "Emergency Fund");
          const isOdd      = assetCells.length % 2 !== 0;
          return (
            <>
              {assetCells.map((cell, idx) => (
                <div key={cell.label} style={isOdd && idx === assetCells.length - 1 ? { gridColumn: "1 / -1" } : {}}>
                  <HeatCell cell={cell} />
                </div>
              ))}
              {efCells.map(cell => (
                <div key={cell.label} style={{ gridColumn: "1 / -1" }}>
                  <HeatCell cell={cell} large />
                </div>
              ))}
            </>
          );
        })()}
      </div>

      <Legend />

      {showEditor && (
        <BalanceEditorModal
          balances={balances}
          onClose={() => setShowEditor(false)}
          onSaved={handleSaved}
        />
      )}

      <style>{`
        @keyframes hm-pulse {
          0%, 100% { transform: scale(1);   opacity: 0.35; }
          50%       { transform: scale(2.4); opacity: 0;    }
        }
      `}</style>
    </div>
  );
}
