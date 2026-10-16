// ─── App.jsx ──────────────────────────────────────────────────────────────────
// Root layout: strictly separated Desktop and Mobile experiences.
// Desktop: Restored to original high-fidelity sidebar + topbar.
// Mobile: Isolated shell for dedicated mobile-first UX.

import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useDashboardMetadata, apiFetch, useActiveProfile } from "./finance/useApi.js";
import { fmt, fmtS } from "./finance/constants.js";
import { Toast, ModuleLoader, Modal } from "./components.jsx";
import AppErrorBoundary from "./components/common/ErrorBoundary.jsx";
import { sidebarStyle, PageWrapper } from "./animations.jsx";
import {
  NAV_ICON_JSX,
  IconDashboard,
  IconMenuClose, IconMenuOpen,
  IconRefresh,
  IconBehavioral, IconUp, IconDown,
  IconMoon, IconSun, IconWallet, IconMore,
  IconSettings, IconAdd, IconCheck,
  IconUser, IconBusiness
} from "./icons.jsx";

import Dashboard         from "./pages/dashboard.jsx";

// ── Lazy-loaded heavy modules ─────────────────────────────────────────────────
const InvestmentTracker   = lazy(() => import("./pages/investment_tracker.jsx"));
const ExpenseTracker      = lazy(() => import("./pages/expense_tracker.jsx"));
const IncomeTracker       = lazy(() => import("./pages/income_tracker.jsx"));
const ReceiptReader       = lazy(() => import("./pages/receipt_reader.jsx"));
const BehavioralDashboard = lazy(() => import("./pages/BehavioralDashboard.jsx"));
const RewardDashboard       = lazy(() => import("./pages/RewardDashboard.jsx"));
const AdvancedFeatures    = lazy(() => import("./pages/advanced.jsx"));
const StockAnalyzer       = lazy(() => import("./pages/stock_analyzer.jsx"));
const StockML             = lazy(() => import("./pages/stock_ml.jsx"));
const GeneticPortfolioLab = lazy(() => import("./pages/GeneticPortfolioLab.jsx"));
const BusinessAnalytics   = lazy(() => import("./pages/BusinessAnalytics.jsx"));
const IntroScreen         = lazy(() => import("./IntroScreen.jsx"));

function IntroOverlay({ show, onFinish }) {
  if (!show) return null;
  return (
    <Suspense fallback={null}>
      <IntroScreen onFinish={onFinish} />
    </Suspense>
  );
}

// ── Profile Switcher & Creator ────────────────────────────────────────────────
const ProfileSwitcher = () => {
  const [profiles, setProfiles]   = useState({ active: "personal", active_type: "personal", available: [], types: {} });
  const [switching, setSwitching] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName]       = useState("");
  const [newType, setNewType]       = useState("business"); // "personal" | "business"
  const [error, setError]           = useState(null);

  const loadProfiles = useCallback(async () => {
    try {
      const data = await apiFetch("/profile/");
      setProfiles(data);
    } catch (e) {
      console.error("Failed to load profiles", e);
    }
  }, []);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  const handleSwitch = async (name) => {
    if (name === profiles.active) return;
    setSwitching(true);
    try {
      await apiFetch("/profile/switch", {
        method: "POST",
        body: JSON.stringify({ profile: name })
      });
      window.location.reload();
    } catch (e) {
      console.error("Switch failed", e);
      setSwitching(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.strip()) {
      setError("Nama profile tidak boleh kosong.");
      return;
    }
    setSwitching(true);
    setError(null);
    try {
      const res = await apiFetch("/profile/create", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), type: newType })
      });
      if (res.status === "success") {
        await apiFetch("/profile/switch", {
          method: "POST",
          body: JSON.stringify({ profile: newName.trim() })
        });
        window.location.reload();
      }
    } catch (e) {
      setError(e.message || "Gagal membuat profile.");
      setSwitching(false);
    }
  };

  if (profiles.available.length === 0) return null;

  return (
    <div style={{ margin: "0 20px 20px 20px", padding: "16px", background: "var(--bg3)", borderRadius: "12px", border: "1px solid var(--bdr)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
         <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
           <IconSettings size={14} color="var(--cy)" />
           <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".8px" }}>Active Profile</div>
         </div>
         <button className="btn btn-g btn-s" style={{ padding: "3px 8px", fontSize: 10 }} onClick={() => setShowCreate(true)}>
           <IconAdd size={11} /> New
         </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {profiles.available.map(name => {
          const type = profiles.types?.[name] || (name.includes("business") ? "business" : "personal");
          const isBiz = type === "business";
          return (
            <button
              key={name}
              onClick={() => handleSwitch(name)}
              disabled={switching}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 12px",
                background: profiles.active === name ? "var(--bg4)" : "transparent",
                border: "1px solid",
                borderColor: profiles.active === name ? "var(--cy)" : "transparent",
                borderRadius: "8px",
                cursor: switching ? "not-allowed" : "pointer",
                transition: "all 0.2s ease"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: profiles.active === name ? 800 : 500, color: profiles.active === name ? "var(--tx)" : "var(--tx2)", textTransform: "uppercase" }}>
                   {name}
                </span>
                <span style={{
                  fontSize: 9, padding: "2px 4px", borderRadius: 99, fontWeight: 700,
                  display: "inline-flex", alignItems: "center",
                  background: isBiz ? "rgba(167,139,250,.18)" : "rgba(52,211,153,.15)",
                  color: isBiz ? "var(--pu)" : "var(--gr)",
                  border: `1px solid ${isBiz ? "rgba(167,139,250,.3)" : "rgba(52,211,153,.3)"}`
                }}>
                  {isBiz ? <IconBusiness size={10} /> : <IconUser size={10} />}
                </span>
              </div>
              {profiles.active === name && <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--cy)" }} />}
            </button>
          );
        })}
      </div>

      {switching && (
        <div style={{ fontSize: 9, color: "var(--tx3)", marginTop: 8, textAlign: "center", fontStyle: "italic" }}>
           Switching environment...
        </div>
      )}

      {/* Modal Pembuatan Profile Baru */}
      {showCreate && (
        <Modal
          title="Buat Profile Baru"
          onClose={() => setShowCreate(false)}
          footer={
            <>
              <button className="btn btn-g" onClick={() => setShowCreate(false)}>Batal</button>
              <button className="btn btn-p" onClick={handleCreate} disabled={switching}>
                {switching ? "Membuat..." : "Buat Profile"}
              </button>
            </>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label htmlFor="ft-profile-name" style={{ fontSize: 12, fontWeight: 600, color: "var(--tx2)", display: "block", marginBottom: 6 }}>Nama Profile</label>
              <input
                id="ft-profile-name"
                className="fc"
                placeholder="e.g. pt_kreatif, client_consulting, household"
                value={newName}
                onChange={e => setNewName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
              />
              <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 4 }}>Gunakan huruf kecil, angka, atau garis bawah (_).</div>
            </div>

            <div role="group" aria-labelledby="ft-profile-type-label">
              <span id="ft-profile-type-label" style={{ fontSize: 12, fontWeight: 600, color: "var(--tx2)", display: "block", marginBottom: 8 }}>Tipe Penggunaan (Usage Type)</span>
              
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={{
                  display: "flex", alignItems: "flex-start", gap: 10, padding: 12, borderRadius: 10,
                  background: newType === "personal" ? "rgba(52,211,153,.08)" : "var(--bg3)",
                  border: `1px solid ${newType === "personal" ? "var(--gr)" : "var(--bdr)"}`, cursor: "pointer"
                }}>
                  <input
                    id="ft-profile-type-personal"
                    type="radio"
                    name="profile_type"
                    aria-label="Personal-Use (Penggunaan Pribadi)"
                    checked={newType === "personal"}
                    onChange={() => setNewType("personal")}
                    style={{ accentColor: "var(--gr)", marginTop: 3 }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: newType === "personal" ? "var(--gr)" : "var(--tx)" }}>
                      👤 Personal-Use (Penggunaan Pribadi)
                    </div>
                    <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 2 }}>
                      Untuk keuangan pribadi, rumah tangga, tabungan, dan gaya hidup. Menampilkan fitur personal sederhana tanpa BI/BA dashboard.
                    </div>
                  </div>
                </label>

                <label style={{
                  display: "flex", alignItems: "flex-start", gap: 10, padding: 12, borderRadius: 10,
                  background: newType === "business" ? "rgba(167,139,250,.08)" : "var(--bg3)",
                  border: `1px solid ${newType === "business" ? "var(--pu)" : "var(--bdr)"}`, cursor: "pointer"
                }}>
                  <input
                    id="ft-profile-type-business"
                    type="radio"
                    name="profile_type"
                    aria-label="Business-Use (Penggunaan Bisnis / UMKM)"
                    checked={newType === "business"}
                    onChange={() => setNewType("business")}
                    style={{ accentColor: "var(--pu)", marginTop: 3 }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: newType === "business" ? "var(--pu)" : "var(--tx)" }}>
                      💼 Business-Use (Penggunaan Bisnis / UMKM)
                    </div>
                    <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 2 }}>
                      Untuk operasional bisnis, B2B, OpEx, COGS, invoice, dan proyek. Membuka **BI/BA Cockpit Dashboard** dan istilah bisnis di seluruh tracker.
                    </div>
                  </div>
                </label>
              </div>
            </div>

            {error && (
              <div style={{ fontSize: 12, color: "var(--rd)", background: "rgba(248,113,113,.1)", padding: "8px 12px", borderRadius: 8 }}>
                {error}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};

// ── Page registry ─────────────────────────────────────────────────────────────
const PAGES = [
  { id: "dashboard",   label: "Dashboard",          section: "overview", path: "/"                    },
  { id: "investments", label: "Investment Tracker",  section: "modules",  path: "/investment-tracker"  },
  { id: "expenses",    label: "Expense Tracker",     section: "modules",  path: "/expense-tracker"     },
  { id: "income",      label: "Income Tracker",      section: "modules",  path: "/income-tracker"      },
  { id: "stocks",      label: "Stock Analyzer",      section: "modules",  path: "/stocks"              },
  { id: "ml_stocks",   label: "ML Predict",          section: "modules",  path: "/ml-stocks"           },
  { id: "genetic",     label: "AI Portfolio Lab",    section: "modules",  path: "/genetic-lab"         },
  { id: "receipt",     label: "Receipt Reader",      section: "modules",  path: "/receipt-reader"      },
  { id: "behavioral",  label: "Behavioral Finance",  section: "insights", path: "/behavioral-finance"  },
  { id: "analytics",   label: "BI/BA Dashboard",     section: "insights", path: "/analytics"           },
  { id: "earn",        label: "Reward",              section: "insights", path: "/earn"                },
  { id: "advanced",    label: "Advanced Features",   section: "insights", path: "/advanced"            },
];

// ─── MOBILE SHELL ────────────────────────────────────────────────────────────

const MobileShell = ({ children, active, onNav, loading, light, onTheme, onReload, isOffline }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleReload = () => {
    onReload();
    setSuccess(true);
    setTimeout(() => setSuccess(false), 1000);
  };

  const isMoreActive = menuOpen || !PAGES.slice(0, 5).some(p => p.id === active);

  return (
    <div className="mobile-app">
      <header className="m-header">
        <div className="m-brand">Alpha</div>
        <div className="m-actions">
           <button onClick={onTheme} className="m-act-btn">{light ? <IconMoon size={18}/> : <IconSun size={18}/>}</button>
           <button onClick={handleReload} className={`m-act-btn ${loading ? 'spin' : ''} ${success ? 'success' : ''}`}><IconRefresh size={18}/></button>
        </div>
      </header>

      {isOffline && (
        <div style={{ background: "var(--rd)", color: "var(--bg2)", padding: "6px 15px", fontSize: 10, fontWeight: 900, textAlign: "center", textTransform: "uppercase", letterSpacing: "1px" }}>
          Server Offline
        </div>
      )}

      <main className="m-content">
        {children}
      </main>

      <nav className="m-bottom-nav">
        {PAGES.slice(0, 5).map((p, i) => {
          const Icon = NAV_ICON_JSX[p.id];
          return (
            <button key={p.id} className={active === p.id ? 'active' : ''} style={{ animationDelay: `${i * 45}ms` }} onClick={() => onNav(p.id)}>
              <Icon size={20} />
              <span>{p.label.split(' ')[0]}</span>
            </button>
          );
        })}
        <button className={isMoreActive ? 'active' : ''} style={{ animationDelay: '225ms' }} onClick={() => setMenuOpen(true)}>
          <IconMore size={20} />
          <span>More</span>
        </button>
      </nav>

      {/* Full Menu Overlay */}
      {menuOpen && (
        <div className="m-overlay" onClick={() => setMenuOpen(false)}>
           <div className="m-menu-card" onClick={e => e.stopPropagation()}>
              <div className="m-menu-title">Menu</div>
              <ProfileSwitcher />
              <div className="m-menu-grid">
                {PAGES.map((p, i) => {
                  const Icon = NAV_ICON_JSX[p.id];
                  return (
                    <div key={p.id} className="m-menu-item" style={{ animationDelay: `${i * 28}ms` }} onClick={() => { onNav(p.id); setMenuOpen(false); }}>
                      <div className="m-menu-ico"><Icon size={22} /></div>
                      <label>{p.label}</label>
                    </div>
                  );
                })}
              </div>
              <button className="m-close-btn" onClick={() => setMenuOpen(false)}>Kembali</button>
           </div>
        </div>
      )}
    </div>
  );
};

// ─── MAIN APP COMPONENT ──────────────────────────────────────────────────────

export default function App() {
  const navigate    = useNavigate();
  const location    = useLocation();
  const [showIntro, setShowIntro] = useState(false);
  const [isMobile,  setIsMobile]  = useState(window.innerWidth <= 800);
  const [isOffline, setIsOffline] = useState(!!window.__FT_OFFLINE__);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 800);
    window.addEventListener("resize", handleResize);

    const onOffline = () => setIsOffline(true);
    const onOnline  = () => setIsOffline(false);
    window.addEventListener("ft:offline", onOffline);
    window.addEventListener("ft:online",  onOnline);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("ft:offline", onOffline);
      window.removeEventListener("ft:online",  onOnline);
    };
  }, []);

  const currentPage = PAGES.find(p => p.path === location.pathname) ?? PAGES[0];
  const page        = location.pathname === "/admin" ? "admin" : currentPage.id;

  const setPage = (id) => {
    const target = PAGES.find(p => p.id === id);
    if (target) navigate(target.path);
    setSbOpen(false);
  };

  const [toast,      setToast]     = useState(null);
  const [sbHidden,   setSbHidden]  = useState(false);
  const [sbOpen,     setSbOpen]    = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [light,      setLight]     = useState(() => {
    try { return localStorage.getItem("ft:theme") === "light"; } catch { return false; }
  });
  const [success,    setSuccess]    = useState(false);

  useEffect(() => {
    document.body.classList.toggle("light-mode", light);
    try { localStorage.setItem("ft:theme", light ? "light" : "dark"); } catch {}
  }, [light]);

  const { data: meta, loading: metaLoading, reload: reloadMeta } = useDashboardMetadata({ intervalMs: 30_000 });

  const handleReload = () => {
    reloadMeta();
    window.dispatchEvent(new CustomEvent("ft:reload"));
    setSuccess(true);
    setTimeout(() => setSuccess(false), 1000);
  };

  const onToast = useCallback((msg, type = "success") => {
    setToast({ msg, type });
    reloadMeta();
    window.dispatchEvent(new CustomEvent("ft:reload"));
  }, [reloadMeta]);

  const net = meta?.net ?? null;

  // Use metadata for shell-first labels, fall back to current date
  const displayMonthLabel = meta?.month_label || "";
  const resolvedDate  = displayMonthLabel ? new Date(displayMonthLabel + " 01") : new Date();
  const resolvedYear  = resolvedDate.getFullYear();
  const resolvedMonth = resolvedDate.getMonth() + 1;

  const renderContent = () => (
    <Suspense fallback={<ModuleLoader pageKey={page} />}>
      <PageWrapper pageKey={page}>
        {page === "dashboard"   && <Dashboard onNav={setPage} />}
        {page === "investments" && <InvestmentTracker onToast={onToast} />}
        {page === "expenses"    && <ExpenseTracker    key={refreshKey} onToast={onToast} initialYear={resolvedYear} initialMonth={resolvedMonth} />}
        {page === "income"      && <IncomeTracker     key={refreshKey} onToast={onToast} initialYear={resolvedYear} initialMonth={resolvedMonth} />}
        {page === "stocks"      && <StockAnalyzer />}
        {page === "ml_stocks"   && <StockML />}
        {page === "genetic"     && <GeneticPortfolioLab onToast={onToast} />}
        {page === "receipt"     && <ReceiptReader     onToast={onToast} />}
        {page === "behavioral"  && <BehavioralDashboard />}
        {page === "analytics"   && <BusinessAnalytics />}
        {page === "earn"        && <RewardDashboard />}
        {page === "advanced"    && <AdvancedFeatures year={resolvedYear} month={resolvedMonth} />}
        {page === "admin"       && <AdminPage onToast={onToast} />}
      </PageWrapper>
    </Suspense>
  );

  if (isMobile) {
    return (
      <AppErrorBoundary>
        <IntroOverlay show={showIntro} onFinish={() => setShowIntro(false)} />
        <MobileShell
          active={page} onNav={setPage}
          loading={metaLoading}
          light={light} onTheme={() => setLight(!light)} onReload={handleReload}
          isOffline={isOffline}
        >
          {renderContent()}
        </MobileShell>
        {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
        <style>{`
          .offline-banner {
            background: var(--rd);
            color: var(--bg2);
            padding: 8px 20px;
            font-size: 11px;
            font-weight: 800;
            display: flex;
            align-items: center;
            justify-content: center;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          .mobile-app { display: flex; flex-direction: column; height: 100vh; background: var(--bg); color: var(--tx); overflow: hidden; }
          .m-header { height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; background: var(--bg2); border-bottom: 1px solid var(--bdr); flex-shrink: 0; }
          .m-brand { font-weight: 900; letter-spacing: -0.5px; font-size: 18px; color: var(--ind-b); }
          .m-actions { display: flex; gap: 15px; }
          .m-act-btn { background: none; border: none; color: var(--tx2); padding: 5px; cursor: pointer; }
          .m-content { flex: 1; overflow-y: auto; padding: 16px; padding-bottom: 100px; }
          .m-bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; height: 75px; background: var(--bg2); border-top: 1px solid var(--bdr); display: flex; padding: 0 10px; padding-bottom: env(safe-area-inset-bottom); z-index: 2000; box-shadow: var(--sh); gap: 12px; }
          .m-bottom-nav button { flex: 1; position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; background: none; border: none; color: var(--tx3); gap: 4px; transition: color .2s, transform .2s; animation: m-nav-in .45s cubic-bezier(.4,0,.2,1) both; }
          .m-bottom-nav button::after { content: ""; position: absolute; bottom: 7px; left: 50%; width: 22px; height: 3px; border-radius: 99px; background: var(--cy); transform: translateX(-50%) scaleX(0); transform-origin: center; transition: transform .28s cubic-bezier(.68,-0.55,.265,1.55); }
          .m-bottom-nav button.active { color: var(--cy); transform: translateY(-3px); }
          .m-bottom-nav button.active::after { transform: translateX(-50%) scaleX(1); }
          .m-bottom-nav button.active svg { animation: m-tab-pop .35s cubic-bezier(.68,-0.55,.265,1.55); }
          .m-bottom-nav span { font-size: 9px; font-weight: 800; text-transform: uppercase; }
          .m-overlay { position: fixed; inset: 0; background: var(--mo-bg); z-index: 3000; display: flex; align-items: flex-end; }
          .m-menu-card { width: 100%; max-height: 88vh; overflow-y: auto; background: var(--bg2); border-radius: 24px 24px 0 0; padding: 24px 24px 32px; animation: m-slide-up .32s cubic-bezier(.4,0,.2,1); display: flex; flex-direction: column; }
          .m-menu-title { font-size: 17px; font-weight: 900; letter-spacing: -0.3px; color: var(--tx); margin-bottom: 16px; }
          .m-menu-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 18px 0 30px; }
          .m-menu-item { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--tx2); cursor: pointer; animation: m-item-in .38s cubic-bezier(.4,0,.2,1) both; }
          @keyframes m-item-in { from { opacity: 0; transform: translateY(16px) scale(.92); } to { opacity: 1; transform: translateY(0) scale(1); } }
          @keyframes m-nav-in { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
          @keyframes m-tab-pop { 0% { transform: scale(1); } 45% { transform: scale(1.28); } 100% { transform: scale(1); } }
          .m-menu-item label { font-size: 10px; font-weight: 700; text-align: center; }
          .m-menu-ico { width: 44px; height: 44px; border-radius: 12px; background: var(--bg3); display: flex; align-items: center; justify-content: center; color: var(--ind-b); }
          .m-menu-ico svg { display: block; }
          .m-close-btn { width: 100%; height: 50px; border-radius: 12px; background: var(--bg3); border: 1px solid var(--bdr); color: var(--tx); font-weight: 900; cursor: pointer; }
          @keyframes m-slide-up { from { transform: translateY(100%); } to { transform: translateY(0); } }
          .spin { animation: m-spin 1s linear infinite; }
          .m-act-btn.success { color: var(--gr); transform: scale(1.2); transition: 0.3s; }
          @keyframes m-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
          .loading-center { display: flex; height: 100%; align-items: center; justifyContent: center; color: var(--tx3); font-size: 13px; }
        `}</style>
      </AppErrorBoundary>
    );
  }

  // ─── FULL ORIGINAL DESKTOP UI (RESTORED) ──────────────────────────────────
  return (
    <AppErrorBoundary>
      <IntroOverlay show={showIntro} onFinish={() => setShowIntro(false)} />
      <div className="app">
        <div className={`sb-backdrop${sbOpen ? " visible" : ""}`} onClick={() => setSbOpen(false)} />
        <aside className={`sb${sbHidden ? " sb-hidden" : ""}${sbOpen ? " sb-open" : ""}`} style={sidebarStyle(sbHidden)}>
          <div className="sb-logo">
            <div className="sb-logo-icon">
              <IconWallet size={20} color="#fff" />
            </div>
            <div>
              <div className="sb-logo-name">Alpha</div>
              <div className="sb-logo-sub">By Zhvny</div>
            </div>
            <button className="sb-toggle" onClick={() => setSbHidden(h => !h)} title="Toggle sidebar">
              {sbHidden ? <IconMenuOpen size={18} /> : <IconMenuClose size={18} />}
            </button>
          </div>

          <div className="sb-net">
            <div className="sb-net-lbl">Net This Month</div>
            {meta === null && metaLoading
              ? <div style={{ fontSize: 11, color: "var(--tx3)", display:"flex", alignItems:"center", gap:5 }}>
                  <IconRefresh size={11} className="spin" /> Loading...
                </div>
              : <>
                  <div className="sb-net-val" style={{ color: (net ?? 0) >= 0 ? "var(--gr)" : "var(--rd)" }}>{fmtS(net)}</div>
                  <div className="sb-net-sub" style={{ display:"flex", alignItems:"center", gap:4 }}>
                    {(net ?? 0) >= 0 ? <IconUp size={10} color="var(--gr)" /> : <IconDown size={10} color="var(--rd)" />}
                    <span>— {displayMonthLabel || "—"}</span>
                  </div>
                </>
            }
          </div>

          {["overview", "modules", "insights"].map(section => (
            <div key={section}>
              <div className="sb-sec">
                <div className="sb-sec-lbl">{section}</div>
                {PAGES.filter(p => p.section === section).map(p => {
                  const IconComp = NAV_ICON_JSX[p.id];
                  return (
                  <div
                    key={p.id}
                    className={`nav-it${page === p.id ? " active" : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-current={page === p.id ? "page" : undefined}
                    onClick={() => {
                      setPage(p.id);
                      setSbOpen(false);
                    }}
                    onKeyDown={e => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setPage(p.id);
                        setSbOpen(false);
                      }
                    }}
                  >
                    <span className="ico">{IconComp ? <IconComp size={16} /> : "•"}</span>
                    <span>{p.label}</span>
                  </div>
                  );
                })}
              </div>
              {section !== "insights" && <div className="sb-div" />}
            </div>
          ))}

          <div className="sb-stats-card" style={{ marginTop: "auto", margin: "20px", padding: "16px", background: "var(--bg3)", borderRadius: "12px" }}>
            <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".8px", marginBottom: 10 }}>Live Stats</div>
            <div className="sb-qs-row" style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 12 }}>
              <span style={{ color: "var(--tx2)" }}>Expenses</span>
              <span style={{ color: "var(--rd)", fontWeight: 700 }}>{fmt(meta?.expense_total ?? null)}</span>
            </div>
            <div className="sb-qs-row" style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span style={{ color: "var(--tx2)" }}>Income</span>
              <span style={{ color: "var(--gr)", fontWeight: 700 }}>{fmt(meta?.income_total ?? null)}</span>
            </div>
          </div>

          <ProfileSwitcher />

        </aside>

        <main className="main">
          {isOffline && (
            <div className="offline-banner">
              <IconRefresh size={14} className="spin" style={{ marginRight: 10 }} />
              API Server Offline — Sebagian data mungkin sudah usang
            </div>
          )}
          <header className="topbar">
            <div className="tb-title">
              <button
                className="btn-icon"
                onClick={(e) => {
                  e.preventDefault();
                  if (isMobile) {
                    setSbOpen(o => !o);
                  } else {
                    setSbHidden(h => !h);
                  }
                }}
                title="Toggle Sidebar"
                style={{ marginRight: 8 }}
              >
                <IconDashboard size={18} />
              </button>
              <button className="tb-hamburger" onClick={() => setSbOpen(o => !o)}><IconMenuOpen size={18} /></button>
              {NAV_ICON_JSX[page] && <span style={{ color: "var(--ind-b)" }}>{NAV_ICON_JSX[page]({ size: 18 })}</span>}
              <span style={{ marginLeft: 10 }}>{PAGES.find(p => p.id === page)?.label}</span>
            </div>
            <div className="tb-right">
              <button className="btn-icon" onClick={() => setLight(!light)} title="Ganti Tema">{light ? <IconMoon size={16} /> : <IconSun size={16} />}</button>
              <button className={`btn-icon ${metaLoading ? 'spin' : ''} ${success ? 'success' : ''}`} onClick={handleReload} title="Refresh Data"><IconRefresh size={16} /></button>
              <div className="tb-date">{new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</div>
            </div>
          </header>
          <div className="content">
            {renderContent()}
          </div>
        </main>
      </div>
      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </AppErrorBoundary>
  );
}



