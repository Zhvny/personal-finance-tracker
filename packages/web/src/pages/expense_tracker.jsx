// ─── expense_tracker.jsx ─────────────────────────────────────────────────────
// Expense Tracker page — reads/writes the same SQLite DB as the CLI.
// High Cohesion  : only expense logic lives here.
// Low Coupling   : API calls via useApi.js, UI atoms via components.jsx.

import { useState, useEffect, useCallback } from "react";
import {
  useExpenses, useExpenseSummary, useExpenseBudget, useExpenseTrend,
  useRecurringExpenses, apiApplyRecurring, apiFetch,
  apiAddExpense, apiUpdateExpense, apiDeleteExpense,
  usePersistedTab, downloadCSV,
} from "../finance/useApi.js";
import { fmt, fmtS, today, thisYear, thisMonth, CATEGORIES, PAY_LIST, yearRange } from "../finance/constants.js";
import { CatIcon } from "../finance/icon-maps.jsx";
import {
  Tabs, Modal, ConfirmDialog, LoadingSpinner, ApiError, Empty,
  FormGroup, FormRow, SumBox, Skeleton
} from "../components.jsx";
import { IconRefresh, IconAdd, IconDelete, IconExpense, IconEdit, IconClose, IconCheck,
         IconRecords, IconSummary, IconTax, IconRepeat, IconWallet } from "../icons.jsx";
import TrendChart from "../finance/TrendChart.jsx";
import { useI18n } from "../i18n/context.js";

// ── Skeletons ───────────────────────────────────────────────────────────────
function RecordsSkeleton() {
  return (
    <>
      <div className="sg">
        {[1,2,3].map(i => <div key={i} className="sc"><Skeleton h={10} mb={10} w="40%" /><Skeleton h={24} w="70%" /></div>)}
      </div>
      <div className="card">
        <div className="card-h"><Skeleton h={18} w={120} /></div>
        <div className="card-b">
          {[1,2,3,4,5].map(i => <Skeleton key={i} h={40} mb={12} />)}
        </div>
      </div>
    </>
  );
}

function SummarySkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="card">
        <div className="card-h"><Skeleton h={18} w={150} /></div>
        <div className="card-b">
          {[1,2,3].map(i => <Skeleton key={i} h={35} mb={12} />)}
          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            {[1,2,3].map(i => <Skeleton key={i} h={60} w="33%" />)}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-component: Expense records table ──────────────────────────────────────
function RecordsTable({ expenses, onDelete, onEdit }) {
  const { t } = useI18n();
  if (!expenses.length) return <Empty variant="expense" msg={t("expense.empty_records")} sub={t("expense.empty_records_sub")} />;
  return (
    <div className="tbl-wrap" tabIndex={0} role="region" aria-label={t("expense.table_label")}>
        <table className="tbl">
        <thead>
          <tr>
            <th className="col-date">{t("expense.col_date")}</th>
            <th className="col-cat">{t("expense.col_category")}</th>
            <th className="tbl-col-hide-sm">{t("expense.col_method")}</th>
            <th className="tbl-col-hide-sm">{t("expense.col_description")}</th>
            <th className="r col-amt">{t("expense.col_amount")}</th>
            <th className="col-act"></th>
          </tr>
        </thead>
        <tbody>
          {expenses.map(e => (
            <tr key={e.id}>
              <td className="col-date" style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--tx2)" }}>{e.date?.slice(0, 10)}</td>
              <td className="col-cat"><span className="pill c" style={{display:'inline-flex',alignItems:'center',gap:4}}><CatIcon cat={e.category} size={12} /> {e.category}</span></td>
              <td className="tbl-col-hide-sm">{e.payment_method}</td>
              <td className="tbl-col-hide-sm" style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.description}</td>
              <td className="r col-amt" style={{ fontFamily: "var(--mono)", fontWeight: 700, color: "var(--rd)" }}>{fmt(e.amount)}</td>
              <td className="col-act">
                <div style={{ display: "flex", gap: 4 }}>
                  <button className="btn btn-g btn-s" title={t("common.edit")} onClick={() => onEdit(e)}><IconEdit size={12} /></button>
                  <button className="btn btn-g btn-s" title={t("common.delete")} onClick={() => onDelete(e.id)}><IconClose size={12} /></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Sub-component: Monthly Summary ────────────────────────────────────────────
function MonthlySummary({ year, month }) {
  const { t } = useI18n();
  const { data, loading } = useExpenseSummary(year, month);
  if (loading) return <LoadingSpinner />;
  if (!data)   return null;

  const byCat    = data.by_category || {};
  const entries  = Object.entries(byCat).sort((a, b) => b[1] - a[1]);
  const maxEntry = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h"><span className="card-t">{t("expense.by_category", { month, year })}</span></div>
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label={t("expense.table_label")}>
        <table className="tbl">
            <thead><tr><th>{t("expense.col_category")}</th><th className="r">{t("expense.col_total")}</th><th className="r">{t("expense.col_pct_spend")}</th><th className="r">{t("expense.col_records")}</th></tr></thead>
            <tbody>
              {entries.length === 0 && <tr><td colSpan={4}><Empty variant="expense" msg={t("expense.empty_month")} sub={t("expense.empty_month_sub")} /></td></tr>}
              {entries.map(([cat, amt]) => (
                <tr key={cat}>
                  <td><span className="pill c" style={{display:'inline-flex',alignItems:'center',gap:4}}><CatIcon cat={cat} size={12} /> {cat}</span></td>
                  <td className="r" style={{ fontFamily: "var(--mono)", fontWeight: 600, color: "var(--rd)" }}>{fmt(amt)}</td>
                  <td className="r" style={{ color: "var(--tx2)", fontFamily: "var(--mono)" }}>{data.total > 0 ? (amt / data.total * 100).toFixed(1) : 0}%</td>
                  <td className="r" style={{ color: "var(--tx2)" }}>—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <SumBox items={[
          { label: t("expense.col_total"), value: fmt(data.total), color: "var(--rd)" },
          { label: t("expense.col_records"), value: data.count },
          { label: t("expense.average"), value: fmt(data.average || 0), color: "var(--cy)" },
        ]} />
      </div>
      <div className="card">
        <div className="card-h"><span className="card-t">{t("expense.distribution")}</span></div>
        <div className="card-b">
          {entries.map(([cat, amt]) => (
            <div key={cat} className="cat-row" style={{ marginBottom: 14 }}>
              <div className="cat-lbl" style={{display:'flex',alignItems:'center',gap:5}}><CatIcon cat={cat} size={13} /> {cat}</div>
              <div className="cat-bw" style={{ height: 10 }}>
                <div className="cat-bf" style={{ width: `${amt / maxEntry * 100}%`, background: "var(--rd)", opacity: 0.7, height: "100%" }} />
              </div>
              <div className="cat-amt" style={{ color: "var(--rd)" }}>{fmt(amt)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Sub-component: Budget Status ──────────────────────────────────────────────
function BudgetPanel({ year, month }) {
  const { t } = useI18n();
  const { data, loading } = useExpenseBudget(year, month);
  if (loading) return <LoadingSpinner />;
  if (!data)   return null;

  const budgets = data.budgets || [];

  return (
    <div className="card">
      <div className="card-h"><span className="card-t">{t("expense.budget_tracking", { month, year })}</span></div>
      <div className="card-b">
        {budgets.length === 0 && <Empty msg={t("expense.no_budget")} />}
        {budgets.map(b => {
          const pct = Math.min(100, (b.actual / b.limit) * 100);
          const color = pct >= 90 ? "var(--rd)" : pct >= 75 ? "var(--yl)" : "var(--gr)";
          return (
            <div key={b.category} style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <CatIcon cat={b.category} size={14} />
                  <span style={{ fontWeight: 700, fontSize: 13 }}>{b.category}</span>
                </div>
                <div style={{ fontSize: 12 }}>
                  <span style={{ fontWeight: 800, color }}>{fmt(b.actual)}</span>
                  <span style={{ color: "var(--tx3)", margin: "0 4px" }}>/</span>
                  <span style={{ color: "var(--tx2)" }}>{fmt(b.limit)}</span>
                </div>
              </div>
              <div className="cat-bw" style={{ height: 8 }}>
                <div className="cat-bf" style={{ width: `${pct}%`, background: color, height: "100%" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 10, color: "var(--tx3)" }}>
                 <span>{t("expense.pct_used", { pct: pct.toFixed(0) })}</span>
                 <span>{t("expense.remaining", { amount: fmt(Math.max(0, b.limit - b.actual)) })}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Sub-component: Expense trend over 12 months ──────────────────────────────
function ExpenseTrendSection() {
  const { t } = useI18n();
  const { data: trend, loading } = useExpenseTrend(12);
  if (loading || !trend?.length) return null;
  const active = trend.filter(m => m.total > 0);
  if (active.length < 2) return null;

  const cats = ["Food & Drink", "transport", "housing", "shopping"];
  const catColors = { "Food & Drink": "var(--yl)", transport: "var(--cy)", housing: "var(--bl)", shopping: "var(--rd)" };

  return (
    <TrendChart
      title={t("expense.trend_title")}
      height={155}
      fmt={n => (n === null || n === undefined) ? "—" : `Rp${Math.abs(n).toLocaleString("id-ID")}`}
      series={[
        { key: "total", label: t("expense.col_total"), color: "var(--rd)", data: active.map(m => ({ label: m.label, value: m.total })) },
        ...cats.map(cat => ({
          key: cat, label: cat,
          color: catColors[cat] || "var(--tx2)",
          data: active.map(m => ({ label: m.label, value: m.by_category?.[cat] || 0 })),
        })),
      ]}
    />
  );
}

// ── Add Expense Modal ──────────────────────────────────────────────────────────
function AddModal({ onClose, onSaved }) {
  const { t } = useI18n();
  const [form, setForm] = useState({ description: "", amount: "", category: "Food & Drink", date: today(), payment_method: "cash", is_recurring: false });
  const [saving, setSaving] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleSave = async () => {
    if (!form.description || !form.amount) return;
    setSaving(true);
    try {
      await apiAddExpense({ ...form, amount: +form.amount });
      onSaved(t("expense.save_success"));
      onClose();
    } catch (e) { onSaved("" + e.message, "error"); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={t("expense.add_title")} onClose={onClose}
      footer={<><button className="btn btn-g" onClick={onClose}>{t("common.cancel")}</button><button className="btn btn-p" onClick={handleSave} disabled={saving}>{saving ? t("expense.saving") : t("common.save")}</button></>}>
      <FormRow>
        <FormGroup label={t("expense.form_description")}><input className="fc" placeholder={t("expense.placeholder_desc")} value={form.description} onChange={set("description")} /></FormGroup>
        <FormGroup label={t("expense.form_amount")}><input className="fc" type="number" placeholder={t("expense.placeholder_amount")} value={form.amount} onChange={set("amount")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label={t("expense.form_category")}>
          <select className="fc sel" value={form.category} onChange={set("category")}>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </FormGroup>
        <FormGroup label={t("expense.form_date")}><input className="fc" type="date" value={form.date} onChange={set("date")} /></FormGroup>
      </FormRow>
      <FormGroup label={t("expense.form_payment")}>
        <select className="fc sel" value={form.payment_method} onChange={set("payment_method")}>
          {PAY_LIST.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </FormGroup>
    </Modal>
  );
}

// ── Edit Expense Modal ─────────────────────────────────────────────────────────
function EditModal({ expense, onClose, onSaved }) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    description:    expense.description,
    amount:         expense.amount,
    category:       expense.category,
    date:           expense.date?.slice(0, 10),
    payment_method: expense.payment_method,
  });
  const [saving, setSaving] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleSave = async () => {
    if (!form.description || !form.amount) return;
    setSaving(true);
    try {
      await apiUpdateExpense(expense.id, { ...form, amount: +form.amount });
      onSaved(t("expense.update_success"));
      onClose();
    } catch (e) { onSaved("" + e.message, "error"); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={t("expense.edit_title")} onClose={onClose}
      footer={<><button className="btn btn-g" onClick={onClose}>{t("common.cancel")}</button><button className="btn btn-p" onClick={handleSave} disabled={saving}>{saving ? t("expense.saving") : t("common.save")}</button></>}>
      <FormRow>
        <FormGroup label={t("expense.form_description")}><input className="fc" value={form.description} onChange={set("description")} /></FormGroup>
        <FormGroup label={t("expense.form_amount")}><input className="fc" type="number" value={form.amount} onChange={set("amount")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label={t("expense.form_category")}>
          <select className="fc sel" value={form.category} onChange={set("category")}>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </FormGroup>
        <FormGroup label={t("expense.form_date")}><input className="fc" type="date" value={form.date} onChange={set("date")} /></FormGroup>
      </FormRow>
      <FormGroup label={t("expense.form_payment")}>
        <select className="fc sel" value={form.payment_method} onChange={set("payment_method")}>
          {PAY_LIST.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </FormGroup>
    </Modal>
  );
}

// ── Recurring Panel ─────────────────────────────────────────────────────────────

function RecurringPanel({ year, month }) {
  const { t } = useI18n();
  const { data, loading, error, reload } = useRecurringExpenses({ intervalMs: 0 });
  const items = data?.items || data || [];

  if (error) return <ApiError error={error} onRetry={reload} />;
  if (!loading && !items.length) return <Empty variant="expense" msg={t("expense.recurring_empty")} />;

  return (
    <div className="card">
      <div className="card-h"><span className="card-t">{t("expense.recurring_title")}</span></div>
      <div className="card-b">
        <table className="tbl">
          <thead><tr><th>{t("expense.col_description")}</th><th>{t("expense.col_amount")}</th><th>{t("expense.recurring_col_frequency")}</th><th>{t("expense.recurring_col_next")}</th></tr></thead>
          <tbody>
            {items.map(r => (
              <tr key={r.id}>
                <td>{r.description || r.name || "—"}</td>
                <td style={{ fontFamily: "var(--mono)" }}>{fmt(r.amount)}</td>
                <td>{r.frequency || "monthly"}</td>
                <td>{r.next_date || r.nextRun || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Merchant Panel ─────────────────────────────────────────────────────────────

function MerchantPanel() {
  const { t } = useI18n();
  const [merchants, setMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch("/merchant-map");
      setMerchants(Array.isArray(d) ? d : []);
    } catch { setMerchants([]); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!name.trim()) return;
    await apiFetch("/merchant-map/remember", { method: "POST", body: JSON.stringify({ merchant_name: name.trim() }) });
    setName("");
    load();
  };

  const handleDel = async (m) => {
    await apiFetch(`/merchant-map/${encodeURIComponent(m)}`, { method: "DELETE" });
    load();
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="card">
      <div className="card-h"><span className="card-t">{t("expense.merchant_title")}</span></div>
      <div className="card-b">
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input className="fc" placeholder={t("expense.merchant_placeholder")} value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === "Enter" && handleAdd()} />
          <button className="btn btn-p btn-s" onClick={handleAdd} disabled={!name.trim()}>{t("expense.merchant_add")}</button>
        </div>
        {merchants.length === 0 && <div style={{ color: "var(--tx3)", fontSize: 13 }}>{t("expense.merchant_empty")}</div>}
        <table className="tbl">
          <thead><tr><th>{t("expense.merchant_col_merchant")}</th><th>{t("expense.merchant_col_action")}</th></tr></thead>
          <tbody>
            {merchants.map(m => (
              <tr key={m}>
                <td>{m}</td>
                <td><button className="btn btn-g btn-s" onClick={() => handleDel(m)}><IconDelete size={12} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main exported component ────────────────────────────────────────────────────
export default function ExpenseTracker({ onToast, initialYear, initialMonth }) {
  const { t } = useI18n();
  const [tab, setTab]           = usePersistedTab("expenses", "records");
  const [showAdd, setShowAdd]       = useState(false);
  const [editItem, setEditItem]       = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [year, setYear]         = useState(initialYear  || thisYear());
  const [month, setMonth]       = useState(initialMonth || thisMonth());
  const [page, setPage]         = useState(0);
  const PAGE_SIZE = 50;

  const params = `limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`;
  const { data: rawData, loading, error, reload } = useExpenses(params);
  const expenses   = rawData?.items  ?? [];
  const totalCount = rawData?.total  ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  const total  = expenses.reduce((s, e) => s + e.amount, 0);

  // Keyboard shortcut: N → open Add modal
  useEffect(() => {
    const handler = e => {
      if (e.key === "n" && !showAdd && !editItem &&
          e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA" && e.target.tagName !== "SELECT") {
        e.preventDefault(); setShowAdd(true);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [showAdd, editItem]);

  const handleDelete = id => setConfirmDeleteId(id);
  const doDelete = async () => {
    await apiDeleteExpense(confirmDeleteId);
    onToast(t("expense.deleted")); reload();
  };
  const handleAdded  = (msg, t = "success") => { onToast(msg, t); reload(); };
  const handleEdited = (msg, t = "success") => { onToast(msg, t); reload(); };

  if (error) return <ApiError error={error} onRetry={reload} />;

  return (
    <>
      {confirmDeleteId !== null && (
        <ConfirmDialog
          message={t("expense.delete_confirm")}
          confirmLabel={t("common.delete")}
          danger
          onConfirm={doDelete}
          onCancel={() => setConfirmDeleteId(null)}
        />
      )}
    <div>
      <h1 className="sr-only">{t("expense.sr_title")}</h1>
      <Tabs
        tabs={[
          { key: "records",   label: t("expense.tab_records"),   icon: <IconRecords size={13} /> },
          { key: "summary",   label: t("expense.tab_summary"),   icon: <IconSummary size={13} /> },
          { key: "budget",    label: t("expense.tab_budget"),    icon: <IconTax     size={13} /> },
          { key: "recurring", label: t("expense.tab_recurring"), icon: <IconRepeat  size={13} /> },
          { key: "merchant",  label: t("expense.tab_merchant"),  icon: <IconWallet  size={13} /> },
        ]}
        active={tab} onChange={setTab}
      />

      {/* ── RECORDS ── */}
      {tab === "records" && (
        <>
          {loading ? <RecordsSkeleton /> : (
            <>
              <div className="sg">
                <div className="sc exp"><div className="sc-lbl">{t("expense.total")}</div><div className="sc-val r">{fmt(total)}</div></div>
                <div className="sc"><div className="sc-lbl">{t("expense.all_records")}</div><div className="sc-val n">{totalCount}</div></div>
                <div className="sc"><div className="sc-lbl">{t("expense.average")}</div><div className="sc-val n" style={{ fontSize: 16 }}>{expenses.length ? fmt(total / expenses.length) : "—"}</div></div>
              </div>

              <div className="tab-toolbar">
                <button className="btn btn-g btn-s" onClick={reload} title={t("dashboard.refresh_data")}><IconRefresh size={13} /> {t("expense.reload")}</button>
                <button className="btn btn-g btn-s" onClick={() => downloadCSV(`/expenses/export?year=${year}`, `expenses_${year}.csv`)} title={t("expense.export_csv")}>{t("expense.csv")}</button>
                <button className="btn btn-p btn-s" onClick={() => setShowAdd(true)} title={t("expense.new")}>{t("expense.add")}</button>
              </div>

              <div className="card">
                <div className="card-h">
                  <span className="card-t">{t("expense.history")}</span>
                </div>
                <RecordsTable expenses={expenses} onDelete={handleDelete} onEdit={setEditItem} />

                {totalPages > 1 && (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 18px 14px", borderTop: "1px solid var(--bdr)" }}>
                    <span style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
                      {t("expense.page_of", { from: page * PAGE_SIZE + 1, to: Math.min((page + 1) * PAGE_SIZE, totalCount), total: totalCount })}
                    </span>
                    <div style={{ display: "flex", gap: 5 }}>
                      <button className="btn btn-g btn-s" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>{t("expense.prev")}</button>
                      <span style={{ fontSize: 11, color: "var(--tx2)", padding: "4px 8px", fontFamily: "var(--mono)" }}>
                        {page + 1} / {totalPages}
                      </span>
                      <button className="btn btn-g btn-s" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>{t("expense.next")}</button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* ── SUMMARY ── */}
      {tab === "summary" && (
        <div>
          <div className="tab-toolbar">
            <span className="tab-toolbar-label">{t("expense.summary_toolbar")}</span>
            <select className="fc sel" value={month} onChange={e => setMonth(+e.target.value)}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
              ))}
            </select>
            <select className="fc sel" value={year} onChange={e => setYear(+e.target.value)}>
              {yearRange().map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          {loading ? <SummarySkeleton /> : (
            <>
              <MonthlySummary year={year} month={month} />
              <ExpenseTrendSection />
            </>
          )}
        </div>
      )}

      {/* ── BUDGET ── */}
      {tab === "budget" && (
        <div>
          <div className="tab-toolbar">
            <span className="tab-toolbar-label">{t("expense.budget_toolbar")}</span>
            <select className="fc sel" value={month} onChange={e => setMonth(+e.target.value)}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
              ))}
            </select>
            <select className="fc sel" value={year} onChange={e => setYear(+e.target.value)}>
              {yearRange().map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          {loading ? <LoadingSpinner /> : <BudgetPanel year={year} month={month} />}
        </div>
      )}

      {/* ── RECURRING ── */}
      {tab === "recurring" && (
        <div>
          <div className="tab-toolbar">
            <span className="tab-toolbar-label">{t("expense.recurring_toolbar")}</span>
            <button className="btn btn-p btn-s" onClick={async () => { await apiFetch("/expenses/recurring/apply", { method: "POST" }); onToast(t("expense.recurring_applied")); reload(); }}>
              <IconRefresh size={12} /> {t("expense.apply_recurring")}
            </button>
          </div>
          {loading ? <LoadingSpinner /> : <RecurringPanel year={year} month={month} />}
        </div>
      )}

      {/* ── MERCHANT ── */}
      {tab === "merchant" && (
        <div>
          <div className="tab-toolbar">
            <span className="tab-toolbar-label">{t("expense.merchant_title")}</span>
          </div>
          {loading ? <LoadingSpinner /> : <MerchantPanel />}
        </div>
      )}

      {showAdd  && <AddModal  onClose={() => setShowAdd(false)}  onSaved={handleAdded}  />}
      {editItem && <EditModal onClose={() => setEditItem(null)}  onSaved={handleEdited} expense={editItem} />}
    </div>
    </>
  );
}
