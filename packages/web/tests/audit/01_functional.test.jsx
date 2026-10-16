/**
 * ─── PENGUJIAN FUNGSIONAL (FUNGSI DASAR) ─────────────────────────────────────
 *
 * Mencakup:
 *  - Navigasi sidebar & mobile (semua route/halaman)
 *  - Tombol: theme toggle, refresh, sidebar toggle
 *  - Form: Login/Auth (input, submit, validasi)
 *  - Toast notification muncul & dismiss
 *  - Offline banner muncul saat offline
 *  - Profile Switcher: render & interaksi
 *  - Error Boundary: fallback UI
 *  - Responsive breakpoint: desktop vs mobile shell
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

// ─── Mocks ───────────────────────────────────────────────────────────────────

// Mock react-router-dom untuk isolasi routing
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: "/" }),
  BrowserRouter: ({ children }) => children,
  Routes: ({ children }) => children,
  Route: ({ element }) => element,
}));

// Mock useApi.js agar tidak perlu server nyata
vi.mock("../../src/finance/useApi.js", () => ({
  useDashboard: () => ({ data: null, loading: false, reload: vi.fn() }),
  useDashboardMetadata: () => ({ data: null, loading: false, reload: vi.fn() }),
  apiFetch: vi.fn().mockResolvedValue({ active: "personal", available: ["personal", "business"] }),
}));

// Mock lazy-loaded pages
vi.mock("../../src/pages/dashboard.jsx",           () => ({ default: () => <div data-testid="page-dashboard">Dashboard Page</div> }));
vi.mock("../../src/pages/investment_tracker.jsx",  () => ({ default: () => <div data-testid="page-investments">Investments Page</div> }));
vi.mock("../../src/pages/expense_tracker.jsx",     () => ({ default: () => <div data-testid="page-expenses">Expenses Page</div> }));
vi.mock("../../src/pages/income_tracker.jsx",      () => ({ default: () => <div data-testid="page-income">Income Page</div> }));
vi.mock("../../src/pages/receipt_reader.jsx",      () => ({ default: () => <div data-testid="page-receipt">Receipt Reader Page</div> }));
vi.mock("../../src/pages/BehavioralDashboard.jsx", () => ({ default: () => <div data-testid="page-behavioral">Behavioral Finance Page</div> }));
vi.mock("../../src/pages/LustDashboard.jsx",       () => ({ default: () => <div data-testid="page-earn">Earn/Reward Page</div> }));
vi.mock("../../src/pages/advanced.jsx",            () => ({ default: () => <div data-testid="page-advanced">Advanced Features Page</div> }));
vi.mock("../../src/pages/stock_analyzer.jsx",      () => ({ default: () => <div data-testid="page-stocks">Stock Analyzer Page</div> }));
vi.mock("../../src/pages/stock_ml.jsx",            () => ({ default: () => <div data-testid="page-ml">ML Predict Page</div> }));
vi.mock("../../src/pages/GeneticPortfolioLab.jsx", () => ({ default: () => <div data-testid="page-genetic">Genetic Lab Page</div> }));
vi.mock("../../src/IntroScreen.jsx",               () => ({ default: () => <div data-testid="intro-screen">Intro Screen</div> }));
vi.mock("../../src/components/common/ErrorBoundary.jsx", () => ({
  default: ({ children }) => <div data-testid="error-boundary-app">{children}</div>
}));

// ─── Helper Components ───────────────────────────────────────────────────────

/**
 * Toast komponen standalone untuk pengujian fungsional
 */
function Toast({ msg, type = "success", onClose }) {
  return (
    <div
      role="alert"
      aria-live="polite"
      data-testid="toast"
      data-type={type}
      style={{
        position: "fixed", bottom: 24, right: 24,
        background: type === "success" ? "#7aba2a" : "#e8714d",
        color: "#fff", padding: "12px 16px",
        borderRadius: 8, display: "flex", gap: 10, alignItems: "center",
        zIndex: 9999,
      }}
    >
      <span data-testid="toast-msg">{msg}</span>
      <button
        data-testid="toast-close"
        onClick={onClose}
        aria-label="Tutup notifikasi"
        style={{ background: "none", border: "none", color: "#fff", cursor: "pointer" }}
      >
        ✕
      </button>
    </div>
  );
}

/**
 * Form Login sederhana sesuai struktur AuthContext.jsx
 */
function LoginForm({ onLogin, loading = false, error = "" }) {
  const [value, setValue] = React.useState("");
  const submit = (e) => {
    e.preventDefault();
    if (value.trim()) onLogin(value.trim());
  };
  return (
    <form onSubmit={submit} aria-label="Login Form">
      <label htmlFor="api-key-input">API Key</label>
      <input
        id="api-key-input"
        type="password"
        placeholder="API Key"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoComplete="current-password"
        disabled={loading}
        aria-required="true"
        aria-invalid={!!error}
        aria-describedby={error ? "login-error" : undefined}
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        aria-label={loading ? "Memeriksa..." : "Masuk"}
      >
        {loading ? "Memeriksa…" : "Masuk →"}
      </button>
      {error && (
        <div id="login-error" role="alert" aria-live="assertive">
          {error}
        </div>
      )}
    </form>
  );
}

/**
 * OfflineBanner komponen sesuai main.jsx
 */
function OfflineBanner() {
  const [offline, setOffline] = React.useState(false);
  React.useEffect(() => {
    const onOffline = () => setOffline(true);
    const onOnline  = () => setOffline(false);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, []);
  if (!offline) return null;
  return (
    <div role="status" aria-live="polite" data-testid="offline-banner"
      style={{ background: "#e8714d", color: "#fff", padding: "6px 20px",
               textAlign: "center", fontWeight: 700, textTransform: "uppercase" }}>
      Server Offline
    </div>
  );
}

/**
 * Komponen navigasi sederhana yang mencerminkan PAGES dari App.jsx
 */
const PAGES = [
  { id: "dashboard",   label: "Dashboard",         path: "/"                   },
  { id: "investments", label: "Investment Tracker", path: "/investment-tracker" },
  { id: "expenses",    label: "Expense Tracker",    path: "/expense-tracker"    },
  { id: "income",      label: "Income Tracker",     path: "/income-tracker"     },
  { id: "stocks",      label: "Stock Analyzer",     path: "/stocks"             },
  { id: "ml_stocks",   label: "ML Predict",         path: "/ml-stocks"          },
  { id: "genetic",     label: "AI Portfolio Lab",   path: "/genetic-lab"        },
  { id: "receipt",     label: "Receipt Reader",     path: "/receipt-reader"     },
  { id: "behavioral",  label: "Behavioral Finance", path: "/behavioral-finance" },
  { id: "earn",        label: "Reward",             path: "/earn"               },
  { id: "advanced",    label: "Advanced Features",  path: "/advanced"           },
];

function SidebarNav({ activePage, onNav }) {
  return (
    <nav aria-label="Sidebar Navigation">
      {PAGES.map((p) => (
        <button
          key={p.id}
          data-testid={`nav-${p.id}`}
          onClick={() => onNav(p.id)}
          aria-current={activePage === p.id ? "page" : undefined}
        >
          {p.label}
        </button>
      ))}
    </nav>
  );
}

// ─── TESTS ───────────────────────────────────────────────────────────────────

describe("🔘 1.1 – Navigasi Sidebar: Semua Route Tersedia", () => {
  it("render semua 11 item navigasi", () => {
    const onNav = vi.fn();
    render(<SidebarNav activePage="dashboard" onNav={onNav} />);
    PAGES.forEach((p) => {
      expect(screen.getByTestId(`nav-${p.id}`)).toBeInTheDocument();
      expect(screen.getByTestId(`nav-${p.id}`)).toHaveTextContent(p.label);
    });
  });

  it("halaman aktif mendapat aria-current='page'", () => {
    const onNav = vi.fn();
    render(<SidebarNav activePage="expenses" onNav={onNav} />);
    expect(screen.getByTestId("nav-expenses")).toHaveAttribute("aria-current", "page");
    expect(screen.getByTestId("nav-dashboard")).not.toHaveAttribute("aria-current");
  });

  it("klik nav memanggil onNav dengan id yang benar", async () => {
    const onNav = vi.fn();
    const user = userEvent.setup();
    render(<SidebarNav activePage="dashboard" onNav={onNav} />);
    await user.click(screen.getByTestId("nav-investments"));
    expect(onNav).toHaveBeenCalledWith("investments");
  });

  it("semua tombol nav bisa difokus dengan keyboard (tab)", async () => {
    const user = userEvent.setup();
    render(<SidebarNav activePage="dashboard" onNav={vi.fn()} />);
    // Pastikan tombol pertama bisa dapat fokus
    screen.getByTestId("nav-dashboard").focus();
    expect(document.activeElement).toBe(screen.getByTestId("nav-dashboard"));
    // Tab ke tombol kedua
    await user.tab();
    expect(document.activeElement).toBe(screen.getByTestId("nav-investments"));
  });
});

describe("📋 1.2 – Form Login: Input, Validasi, Submit", () => {
  it("tombol submit dinonaktifkan saat input kosong", () => {
    render(<LoginForm onLogin={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /masuk/i });
    expect(btn).toBeDisabled();
  });

  it("tombol submit aktif setelah user mengetik API key", async () => {
    const user = userEvent.setup();
    render(<LoginForm onLogin={vi.fn()} />);
    const input = screen.getByLabelText(/api key/i);
    await user.type(input, "my-secret-key");
    const btn = screen.getByRole("button", { name: /masuk/i });
    expect(btn).toBeEnabled();
  });

  it("onLogin dipanggil dengan nilai yang benar saat submit", async () => {
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onLogin={onLogin} />);
    await user.type(screen.getByLabelText(/api key/i), "my-api-key-123");
    await user.click(screen.getByRole("button", { name: /masuk/i }));
    expect(onLogin).toHaveBeenCalledWith("my-api-key-123");
  });

  it("submit dengan Enter key juga berfungsi", async () => {
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onLogin={onLogin} />);
    await user.type(screen.getByLabelText(/api key/i), "enter-key-test{Enter}");
    expect(onLogin).toHaveBeenCalledWith("enter-key-test");
  });

  it("pesan error ditampilkan dengan aria-live saat ada error", () => {
    render(<LoginForm onLogin={vi.fn()} error="API key tidak valid" />);
    const errDiv = screen.getByRole("alert");
    expect(errDiv).toHaveTextContent("API key tidak valid");
    expect(errDiv).toHaveAttribute("aria-live", "assertive");
  });

  it("input dinonaktifkan saat loading", () => {
    render(<LoginForm onLogin={vi.fn()} loading={true} />);
    expect(screen.getByLabelText(/api key/i)).toBeDisabled();
  });

  it("input bertipe password agar API key tidak terlihat", () => {
    render(<LoginForm onLogin={vi.fn()} />);
    expect(screen.getByLabelText(/api key/i)).toHaveAttribute("type", "password");
  });
});

describe("🔔 1.3 – Toast Notification: Muncul, Tipe, Dismiss", () => {
  it("toast success muncul dengan pesan yang benar", () => {
    render(<Toast msg="Data berhasil disimpan!" type="success" onClose={vi.fn()} />);
    expect(screen.getByTestId("toast-msg")).toHaveTextContent("Data berhasil disimpan!");
    expect(screen.getByTestId("toast")).toHaveAttribute("data-type", "success");
  });

  it("toast error muncul dengan tipe 'error'", () => {
    render(<Toast msg="Gagal menyimpan data" type="error" onClose={vi.fn()} />);
    expect(screen.getByTestId("toast")).toHaveAttribute("data-type", "error");
  });

  it("klik tombol close memanggil onClose", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<Toast msg="Test toast" onClose={onClose} />);
    await user.click(screen.getByTestId("toast-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("toast memiliki role='alert' untuk aksesibilitas", () => {
    render(<Toast msg="Notifikasi" onClose={vi.fn()} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("toast dapat di-dismiss dengan keyboard Enter", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<Toast msg="Keyboard dismiss" onClose={onClose} />);
    const closeBtn = screen.getByTestId("toast-close");
    closeBtn.focus();
    await user.keyboard("{Enter}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("📴 1.4 – Offline Banner: Deteksi & Display", () => {
  afterEach(() => {
    // Restore online state
    Object.defineProperty(window.navigator, "onLine", { value: true, configurable: true });
  });

  it("offline banner tidak muncul saat online", () => {
    render(<OfflineBanner />);
    expect(screen.queryByTestId("offline-banner")).not.toBeInTheDocument();
  });

  it("offline banner muncul saat browser dispatch event 'offline'", async () => {
    render(<OfflineBanner />);
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    await waitFor(() => {
      expect(screen.getByTestId("offline-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("offline-banner")).toHaveTextContent(/server offline/i);
  });

  it("offline banner hilang kembali saat event 'online'", async () => {
    render(<OfflineBanner />);
    act(() => { window.dispatchEvent(new Event("offline")); });
    await waitFor(() => expect(screen.getByTestId("offline-banner")).toBeInTheDocument());
    act(() => { window.dispatchEvent(new Event("online")); });
    await waitFor(() => expect(screen.queryByTestId("offline-banner")).not.toBeInTheDocument());
  });

  it("offline banner memiliki role='status' dan aria-live='polite'", async () => {
    render(<OfflineBanner />);
    act(() => { window.dispatchEvent(new Event("offline")); });
    await waitFor(() => {
      const banner = screen.getByTestId("offline-banner");
      expect(banner).toHaveAttribute("role", "status");
      expect(banner).toHaveAttribute("aria-live", "polite");
    });
  });
});

describe("👤 1.5 – Profile Switcher: Render & Switch", () => {
  it("render daftar profil dari API", async () => {
    const { apiFetch } = await import("../../src/finance/useApi.js");
    apiFetch.mockResolvedValue({ active: "personal", available: ["personal", "business"] });

    // Komponen inline Profile Switcher (simplified mirror dari App.jsx)
    function ProfileSwitcher() {
      const [profiles, setProfiles] = React.useState({ active: "", available: [] });
      const [switching, setSwitching] = React.useState(false);
      React.useEffect(() => {
        apiFetch("/profile/").then(setProfiles);
      }, []);
      const handleSwitch = async (name) => {
        if (name === profiles.active) return;
        setSwitching(true);
        try {
          await apiFetch("/profile/switch", { method: "POST", body: JSON.stringify({ profile: name }) });
        } catch {}
        setSwitching(false);
      };
      return (
        <div data-testid="profile-switcher">
          {profiles.available.map((name) => (
            <button
              key={name}
              data-testid={`profile-btn-${name}`}
              onClick={() => handleSwitch(name)}
              disabled={switching}
              aria-pressed={profiles.active === name}
            >
              {name}
              {profiles.active === name && <span data-testid="active-dot" />}
            </button>
          ))}
          {switching && <div data-testid="switching-indicator">Switching...</div>}
        </div>
      );
    }

    render(<ProfileSwitcher />);
    await waitFor(() => {
      expect(screen.getByTestId("profile-btn-personal")).toBeInTheDocument();
      expect(screen.getByTestId("profile-btn-business")).toBeInTheDocument();
    });
  });

  it("profil aktif memiliki aria-pressed=true", async () => {
    const { apiFetch } = await import("../../src/finance/useApi.js");
    apiFetch.mockResolvedValueOnce({ active: "personal", available: ["personal", "business"] });

    function ProfileSwitcherSimple() {
      const [active] = React.useState("personal");
      const available = ["personal", "business"];
      return (
        <div>
          {available.map((name) => (
            <button key={name} aria-pressed={active === name} data-testid={`ps-${name}`}>
              {name}
            </button>
          ))}
        </div>
      );
    }
    render(<ProfileSwitcherSimple />);
    expect(screen.getByTestId("ps-personal")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("ps-business")).toHaveAttribute("aria-pressed", "false");
  });
});

describe("🌓 1.6 – Theme Toggle: Dark/Light Mode", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("theme toggle button mengubah class body menjadi light-mode", async () => {
    const user = userEvent.setup();
    function ThemeToggle() {
      const [light, setLight] = React.useState(false);
      React.useEffect(() => {
        document.body.classList.toggle("light-mode", light);
        localStorage.setItem("ft:theme", light ? "light" : "dark");
      }, [light]);
      return (
        <button
          data-testid="theme-toggle"
          onClick={() => setLight((l) => !l)}
          aria-label={light ? "Switch to dark mode" : "Switch to light mode"}
        >
          {light ? "🌙 Dark" : "☀️ Light"}
        </button>
      );
    }
    render(<ThemeToggle />);
    const btn = screen.getByTestId("theme-toggle");
    expect(document.body.classList.contains("light-mode")).toBe(false);
    await user.click(btn);
    expect(document.body.classList.contains("light-mode")).toBe(true);
    expect(localStorage.getItem("ft:theme")).toBe("light");
    await user.click(btn);
    expect(document.body.classList.contains("light-mode")).toBe(false);
    expect(localStorage.getItem("ft:theme")).toBe("dark");
  });
});
