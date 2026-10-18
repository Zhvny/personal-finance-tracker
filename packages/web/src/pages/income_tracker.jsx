// ─── income_tracker.jsx ──────────────────────────────────────────────────────
// Income Tracker page — reads/writes the same SQLite DB as the CLI.
// High Cohesion  : only income logic lives here.
// Low Coupling   : API calls via useApi.js, UI atoms via components.jsx.

import { useState, useEffect } from "react";
import {
  useIncome, useIncomeSummary, useIncomeTax, useIncomeTrend,
  apiAddIncome, apiUpdateIncome, apiDeleteIncome,
  useDebounce, usePersistedTab, downloadCSV,
} from "../finance/useApi.js";
import { fmt, fmtS, today, thisYear, thisMonth, INC_TYPES, yearRange } from "../finance/constants.js";
import { INC_ICON, IncIcon } from "../finance/icon-maps.jsx";
import {
  Tabs, Modal, ConfirmDialog, LoadingSpinner, ApiError, Empty,
  FormGroup, FormRow, SumBox, Skeleton
} from "../components.jsx";
import { IconRefresh, IconAdd, IconDelete, IconIncome, IconEdit, IconClose, IconCheck,
         IconRecords, IconSummary, IconTax } from "../icons.jsx";
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
      <div className="card">
        <div className="card-h"><Skeleton h={18} w={130} /></div>
        <div className="card-b">
          {[1,2,3,4].map(i => (
            <div key={i} style={{ marginBottom: 16 }}>
              <div style={{ display:"flex", justifyContent:"space-between", marginBottom: 6 }}><Skeleton h={12} w="30%" /><Skeleton h={12} w="20%" /></div>
              <Skeleton h={10} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TaxSkeleton() {
  return (
    <>
      <div className="sg">
        {[1,2,3].map(i => <div key={i} className="sc"><Skeleton h={10} mb={10} w="40%" /><Skeleton h={24} w="70%" /></div>)}
      </div>
      <div className="card">
        <div className="card-h"><Skeleton h={18} w={140} /></div>
        <div className="card-b">
          {[1,2,3,4].map(i => <Skeleton key={i} h={35} mb={12} />)}
          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} h={50} w="20%" />)}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Sub-component: Income records table ───────────────────────────────────────
function RecordsTable({ income, onDelete, onEdit }) {
  const { t } = useI18n();
  if (!income.length) return <Empty variant="income" msg={t("income.empty_records")} sub={t("income.empty_records_sub")} />;
  return (
    <div className="tbl-wrap" tabIndex={0} role="region" aria-label={t("income.table_label")}>
        <table className="tbl">
        <thead>
          <tr>
            <th className="col-date">{t("income.col_date")}</th>
            <th className="col-cat">{t("income.col_type")}</th>
            <th className="tbl-col-hide-sm">{t("income.col_source")}</th>
            <th className="tbl-col-hide-sm">{t("income.col_taxed")}</th>
            <th className="r col-amt">{t("income.col_amount")}</th>
            <th className="col-act"></th>
          </tr>
        </thead>
        <tbody>
          {income.map(i => (
            <tr key={i.id}>
              <td className="col-date" style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--tx2)" }}>{i.date?.slice(0, 10)}</td>
              <td className="col-cat"><span className="pill c" style={{display:'inline-flex',alignItems:'center',gap:4}}>{IncIcon({ type: i.income_type, size: 12 })} {i.income_type}</span></td>
              <td className="tbl-col-hide-sm">{i.source}</td>
              <td className="tbl-col-hide-sm">{i.is_taxed ? <span className="pill g"><IconCheck size={10} /> {t("income.taxed")}</span> : <span className="pill dim">{t("income.no")}</span>}</td>
              <td className="r col-amt" style={{ fontFamily: "var(--mono)", fontWeight: 700, color: "var(--gr)" }}>{fmt(i.amount)}</td>
              <td className="col-act">
                <div style={{ display: "flex", gap: 4 }}>
                  <button className="btn btn-g btn-s" title={t("common.edit")} onClick={() => onEdit(i)}><IconEdit size={12} /></button>
                  <button className="btn btn-g btn-s" title={t("common.delete")} onClick={() => onDelete(i.id)}><IconClose size={12} /></button>
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
  const { data, loading } = useIncomeSummary(year, month);
  if (loading) return <LoadingSpinner />;
  if (!data)   return null;

  const byType   = data.by_type || {};
  const entries  = Object.entries(byType).sort((a, b) => b[1] - a[1]);
  const maxEntry = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h"><span className="card-t">{t("income.by_type", { month, year })}</span></div>
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label={t("income.table_label")}>
        <table className="tbl">
            <thead><tr><th>{t("income.col_type")}</th><th className="r">{t("income.col_total")}</th><th className="r">{t("income.col_pct_income")}</th><th className="r">{t("income.col_records")}</th></tr></thead>
            <tbody>
              {entries.length === 0 && <tr><td colSpan={4}><Empty variant="income" msg={t("income.empty_month")} sub={t("income.empty_month_sub")} /></td></tr>}
              {entries.map(([type, amt]) => (
                <tr key={type}>
                  <td><span className="pill c" style={{display:'inline-flex',alignItems:'center',gap:4}}>{IncIcon({ type, size: 12 })} {type}</span></td>
                  <td className="r" style={{ fontFamily: "var(--mono)", fontWeight: 600, color: "var(--gr)" }}>{fmt(amt)}</td>
                  <td className="r" style={{ color: "var(--tx2)", fontFamily: "var(--mono)" }}>{data.total > 0 ? (amt / data.total * 100).toFixed(1) : 0}%</td>
                  <td className="r" style={{ color: "var(--tx2)" }}>—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <SumBox items={[
          { label: t("income.col_total"), value: fmt(data.total), color: "var(--gr)" },
          { label: t("income.col_records"), value: data.count },
          { label: t("income.average"), value: fmt(data.average || 0), color: "var(--cy)" },
        ]} />
      </div>
      <div className="card">
        <div className="card-h"><span className="card-t">{t("income.distribution")}</span></div>
        <div className="card-b">
          {entries.map(([type, amt]) => (
            <div key={type} className="cat-row" style={{ marginBottom: 14 }}>
              <div className="cat-lbl" style={{display:'flex',alignItems:'center',gap:5}}>{IncIcon({ type, size: 13 })} {type}</div>
              <div className="cat-bw" style={{ height: 10 }}>
                <div className="cat-bf" style={{ width: `${amt / maxEntry * 100}%`, background: "var(--cy)", height: "100%" }} />
              </div>
              <div className="cat-amt" style={{ color: "var(--gr)" }}>{fmt(amt)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Sub-component: PPh 21 Tax Calculator ──────────────────────────────────────
function TaxPanel({ year }) {
  const { t } = useI18n();
  const { data, loading } = useIncomeTax(year);
  if (loading) return <LoadingSpinner />;
  if (!data)   return null;

  const { annual_income, taxable, ptkp, tax, effective_rate, monthly_net } = data;

  // PPh 21 bracket breakdown for display
  const brackets = [
    { range: t("income.bracket_1"), rate: "5%",  applied: Math.min(taxable, 60_000_000),                              taxAmt: Math.min(taxable, 60_000_000) * 0.05 },
    { range: t("income.bracket_2"), rate: "15%", applied: taxable > 60_000_000  ? Math.min(taxable - 60_000_000, 190_000_000)  : 0,
                                                       taxAmt:  taxable > 60_000_000  ? Math.min(taxable - 60_000_000, 190_000_000)  * 0.15 : 0 },
    { range: t("income.bracket_3"), rate: "25%", applied: taxable > 250_000_000 ? Math.min(taxable - 250_000_000, 250_000_000) : 0,
                                                       taxAmt:  taxable > 250_000_000 ? Math.min(taxable - 250_000_000, 250_000_000) * 0.25 : 0 },
    { range: t("income.bracket_4"), rate: "30%", applied: taxable > 500_000_000 ? Math.min(taxable - 500_000_000, 4_500_000_000) : 0,
                                                       taxAmt:  taxable > 500_000_000 ? Math.min(taxable - 500_000_000, 4_500_000_000) * 0.30 : 0 },
  ];

  return (
    <>
      <div className="sg">
        <div className="sc inc"><div className="sc-lbl">{t("income.annual_income", { year })}</div><div className="sc-val g">{fmt(annual_income)}</div></div>
        <div className="sc exp"><div className="sc-lbl">{t("income.est_tax")}</div><div className="sc-val r">{fmt(tax)}</div></div>
        <div className="sc" style={{ borderTop: "2px solid var(--ind)" }}>
          <div className="sc-lbl">{t("income.effective_rate")}</div>
          <div className="sc-val i">{effective_rate.toFixed(1)}%</div>
          <div className="sc-chg nt">{t("income.monthly_net", { amount: fmt(monthly_net) })}</div>
        </div>
      </div>
      <div className="card">
        <div className="card-h"><span className="card-t">{t("income.tax_brackets")}</span></div>
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label={t("income.table_label")}>
        <table className="tbl">
            <thead><tr><th>{t("income.col_bracket")}</th><th>{t("income.col_rate")}</th><th className="r">{t("income.col_taxable_portion")}</th><th className="r">{t("income.col_tax")}</th></tr></thead>
            <tbody>
              {brackets.map(({ range, rate, applied, taxAmt }) => (
                <tr key={range} style={{ opacity: applied > 0 ? 1 : 0.35 }}>
                  <td style={{ color: "var(--tx2)" }}>{range}</td>
                  <td><span className="pill c">{rate}</span></td>
                  <td className="r" style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{fmt(applied)}</td>
                  <td className="r" style={{ fontFamily: "var(--mono)", fontWeight: applied > 0 ? 700 : 400, color: applied > 0 ? "var(--rd)" : "var(--tx3)" }}>{fmt(taxAmt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <SumBox items={[
          { label: t("income.sum_annual"), value: fmt(annual_income), color: "var(--gr)" },
          { label: t("income.sum_ptkp"),   value: fmt(ptkp),          color: "var(--tx2)" },
          { label: t("income.sum_taxable"),value: fmt(taxable),        color: "var(--yl)" },
          { label: t("income.sum_tax"),    value: fmt(tax),            color: "var(--rd)" },
          { label: t("income.sum_net_mo"), value: fmt(monthly_net),    color: "var(--cy)" },
        ]} />
      </div>
    </>
  );
}

// ── Sub-component: Income trend over 12 months ───────────────────────────────
function IncomeTrendSection() {
  const { t } = useI18n();
  const { data: trend, loading } = useIncomeTrend(12);
  if (loading || !trend?.length) return null;
  const active = trend.filter(m => m.total > 0);
  if (active.length < 2) return null;

  const typeColors = { salary: "var(--gr)", freelance: "var(--cy)", investment: "var(--yl)", "side-hustle": "var(--pu)", other: "var(--tx3)" };
  const typeTotals = {};
  active.forEach(m => Object.entries(m.by_type || {}).forEach(([k, v]) => {
    typeTotals[k] = (typeTotals[k] || 0) + v;
  }));
  const topTypes = Object.entries(typeTotals).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => k);

  return (
    <TrendChart
      title={t("income.trend_title")}
      height={155}
      fmt={n => (n === null || n === undefined) ? "—" : `Rp${Math.abs(n).toLocaleString("id-ID")}`}
      series={[
        { key: "total", label: t("income.col_total"), color: "var(--gr)", data: active.map(m => ({ label: m.label, value: m.total })) },
        ...topTypes.map(type => ({
          key: type, label: type,
          color: typeColors[type] || "var(--tx2)",
          data: active.map(m => ({ label: m.label, value: m.by_type?.[type] || 0 })),
        })),
      ]}
    />
  );
}

// ── Add Income Modal ───────────────────────────────────────────────────────────
function AddModal({ onClose, onSaved }) {
  const { t } = useI18n();
  const [form, setForm] = useState({ source: "", amount: "", income_type: "salary", date: today(), is_taxed: false, description: "" });
  const [saving, setSaving] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleSave = async () => {
    if (!form.source || !form.amount) return;
    setSaving(true);
    try {
      await apiAddIncome({ ...form, amount: +form.amount });
      onSaved(t("income.save_success"));
      onClose();
    } catch (e) { onSaved("" + e.message, "error"); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={t("income.add_title")} onClose={onClose}
      footer={<><button className="btn btn-g" onClick={onClose}>{t("common.cancel")}</button><button className="btn btn-p" onClick={handleSave} disabled={saving}>{saving ? t("income.saving") : t("common.save")}</button></>}>
      <FormRow>
        <FormGroup label={t("income.form_source")}><input className="fc" placeholder={t("income.placeholder_source")} value={form.source} onChange={set("source")} /></FormGroup>
        <FormGroup label={t("income.form_amount")}><input className="fc" type="number" placeholder={t("income.placeholder_amount")} value={form.amount} onChange={set("amount")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label={t("income.form_type")}>
          <select className="fc sel" value={form.income_type} onChange={set("income_type")}>
            {INC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </FormGroup>
        <FormGroup label={t("income.form_date")}><input className="fc" type="date" value={form.date} onChange={set("date")} /></FormGroup>
      </FormRow>
      <FormGroup label={t("income.form_description")}>
        <input className="fc" placeholder={t("income.placeholder_desc")} value={form.description} onChange={set("description")} />
      </FormGroup>
      <div className="fg" style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <input type="checkbox" id="taxed" checked={form.is_taxed}
          onChange={e => setForm(p => ({ ...p, is_taxed: e.target.checked }))}
          style={{ width: 15, height: 15, cursor: "pointer", accentColor: "var(--ind)" }} />
        <label htmlFor="taxed" style={{ cursor: "pointer", fontSize: 13, color: "var(--tx2)" }}>
          {t("income.already_taxed")}
        </label>
      </div>
    </Modal>
  );
}

// ── Edit Income Modal ──────────────────────────────────────────────────────────
function EditModal({ income, onClose, onSaved }) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    source:      income.source,
    amount:      income.amount,
    income_type: income.income_type,
    date:        income.date?.slice(0, 10),
    description: income.description || "",
    is_taxed:    income.is_taxed || false,
  });
  const [saving, setSaving] = useState(false);
  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleSave = async () => {
    if (!form.source || !form.amount) return;
    setSaving(true);
    try {
      await apiUpdateIncome(income.id, { ...form, amount: +form.amount });
      onSaved(t("income.update_success"));
      onClose();
    } catch (e) { onSaved("" + e.message, "error"); }
    finally { setSaving(false); }
  };

  return (
    <Modal title={t("income.edit_title")} onClose={onClose}
      footer={<><button className="btn btn-g" onClick={onClose}>{t("common.cancel")}</button><button className="btn btn-p" onClick={handleSave} disabled={saving}>{saving ? t("income.saving") : t("common.save")}</button></>}>
      <FormRow>
        <FormGroup label={t("income.form_source")}><input className="fc" value={form.source} onChange={set("source")} /></FormGroup>
        <FormGroup label={t("income.form_amount")}><input className="fc" type="number" value={form.amount} onChange={set("amount")} /></FormGroup>
      </FormRow>
      <FormRow>
        <FormGroup label={t("income.form_type")}>
          <select className="fc sel" value={form.income_type} onChange={set("income_type")}>
            {INC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </FormGroup>
        <FormGroup label={t("income.form_date")}><input className="fc" type="date" value={form.date} onChange={set("date")} /></FormGroup>
      </FormRow>
      <FormGroup label={t("income.form_description")}>
        <input className="fc" value={form.description} onChange={set("description")} />
      </FormGroup>
      <div className="fg" style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <input type="checkbox" id="taxed-edit" checked={form.is_taxed}
          onChange={e => setForm(p => ({ ...p, is_taxed: e.target.checked }))}
          style={{ width: 15, height: 15, cursor: "pointer", accentColor: "var(--ind)" }} />
        <label htmlFor="taxed-edit" style={{ cursor: "pointer", fontSize: 13, color: "var(--tx2)" }}>
          {t("income.already_taxed")}
        </label>
      </div>
    </Modal>
  );
}

// ── Main exported component ────────────────────────────────────────────────────
export default function IncomeTracker({ onToast, initialYear, initialMonth }) {
  const { t } = useI18n();
  const [tab, setTab]           = usePersistedTab("income", "records");
  const [showAdd, setShowAdd]       = useState(false);
  const [editItem, setEditItem]       = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [year, setYear]         = useState(initialYear  || thisYear());
  const [month, setMonth]       = useState(initialMonth || thisMonth());
  const [page, setPage]         = useState(0);
  const PAGE_SIZE = 50;

  const params = `limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`;
  const { data: rawData, loading, error, reload } = useIncome(params);
  const income     = rawData?.items  ?? [];
  const totalCount = rawData?.total  ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  const total  = income.reduce((s, i) => s + i.amount, 0);
  const byType = income.reduce((acc, i) => { acc[i.income_type] = (acc[i.income_type] || 0) + i.amount; return acc; }, {});

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
    await apiDeleteIncome(confirmDeleteId);
    onToast(t("income.deleted")); reload();
  };
  const handleAdded  = (msg, t = "success") => { onToast(msg, t); reload(); };
  const handleEdited = (msg, t = "success") => { onToast(msg, t); reload(); };

  if (error) return <ApiError error={error} onRetry={reload} />;

  return (
    <>
      {confirmDeleteId !== null && (
        <ConfirmDialog
          message={t("income.delete_confirm")}
          confirmLabel={t("common.delete")}
          danger
          onConfirm={doDelete}
          onCancel={() => setConfirmDeleteId(null)}
        />
      )}
    <div>
      <h1 className="sr-only">{t("income.sr_title")}</h1>
      <Tabs
        tabs={[
          { key: "records", label: t("income.tab_records"), icon: <IconRecords size={13} /> },
          { key: "summary", label: t("income.tab_summary"), icon: <IconSummary size={13} /> },
          { key: "tax",     label: t("income.tab_tax"),     icon: <IconTax     size={13} /> },
        ]}
        active={tab} onChange={setTab}
      />

      {/* ── RECORDS ── */}
      {tab === "records" && (
        <>
          {loading ? <RecordsSkeleton /> : (
            <>
              <div className="sg">
                <div className="sc inc"><div className="sc-lbl">{t("income.total")}</div><div className="sc-val g">{fmt(total)}</div></div>
                <div className="sc"><div className="sc-lbl">{t("income.all_records")}</div><div className="sc-val n">{totalCount}</div></div>
                <div className="sc"><div className="sc-lbl">{t("income.average")}</div><div className="sc-val n" style={{ fontSize: 16 }}>{income.length ? fmt(total / income.length) : "—"}</div></div>
              </div>

              <div className="tab-toolbar">
                <button className="btn btn-g btn-s" onClick={reload} title={t("dashboard.refresh_data")}><IconRefresh size={13} /> {t("income.reload")}</button>
                <button className="btn btn-g btn-s" onClick={() => downloadCSV(`/income/export?year=${year}`, `income_${year}.csv`)} title={t("income.export_csv")}>{t("income.csv")}</button>
                <button className="btn btn-p btn-s" onClick={() => setShowAdd(true)} title={t("income.new")}>{t("income.add")}</button>
              </div>

              <div className="card">
                <div className="card-h">
                  <span className="card-t">{t("income.history")}</span>
                </div>
                <RecordsTable income={income} onDelete={handleDelete} onEdit={setEditItem} />

                {totalPages > 1 && (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 18px 14px", borderTop: "1px solid var(--bdr)" }}>
                    <span style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
                      {t("income.page_of", { from: page * PAGE_SIZE + 1, to: Math.min((page + 1) * PAGE_SIZE, totalCount), total: totalCount })}
                    </span>
                    <div style={{ display: "flex", gap: 5 }}>
                      <button className="btn btn-g btn-s" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>{t("income.prev")}</button>
                      <span style={{ fontSize: 11, color: "var(--tx2)", padding: "4px 8px", fontFamily: "var(--mono)" }}>
                        {page + 1} / {totalPages}
                      </span>
                      <button className="btn btn-g btn-s" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>{t("income.next")}</button>
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
            <span className="tab-toolbar-label">{t("income.summary_toolbar")}</span>
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
              <IncomeTrendSection />
            </>
          )}
        </div>
      )}

      {/* ── TAX ── */}
      {tab === "tax" && (
        <div>
          <div className="tab-toolbar">
            <span className="tab-toolbar-label">{t("income.tax_toolbar")}</span>
            <select className="fc sel" value={year} onChange={e => setYear(+e.target.value)}>
              {yearRange().map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          {loading ? <TaxSkeleton /> : <TaxPanel year={year} />}
        </div>
      )}


      {showAdd  && <AddModal  onClose={() => setShowAdd(false)}  onSaved={handleAdded}  />}
      {editItem && <EditModal onClose={() => setEditItem(null)}  onSaved={handleEdited} income={editItem} />}
    </div>
    </>
  );
}
