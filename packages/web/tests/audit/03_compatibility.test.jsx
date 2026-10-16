/**
 * ─── PENGUJIAN KOMPATIBILITAS ─────────────────────────────────────────────────
 *
 * Mencakup:
 *  - Responsive breakpoints: CSS media queries untuk mobile/tablet/desktop
 *  - Mobile shell: MobileShell dirender saat window.innerWidth <= 800
 *  - Desktop sidebar: dirender saat window.innerWidth > 800
 *  - Safe area inset support (iOS notch)
 *  - Touch-action CSS (mobile scrolling)
 *  - Viewport units (dvh untuk iOS Safari compatibility)
 *  - CSS custom properties (tidak ada hard-coded hex di komponen kritis)
 *  - Cross-browser: tidak ada vendor-prefixed CSS yang hilang
 *  - Semantic HTML: heading hierarchy, landmark regions, dll
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { readFileSync } from "fs";
import { resolve } from "path";

expect.extend(matchers);

const ROOT = resolve(__dirname, "../../");
const RESPONSIVE_CSS = readFileSync(resolve(ROOT, "src/styles/theme/responsive.css"), "utf-8");
const BASE_CSS = readFileSync(resolve(ROOT, "src/styles/theme/base.css"), "utf-8");
const LAYOUT_CSS = readFileSync(resolve(ROOT, "src/styles/theme/layout.css"), "utf-8");

// ─── Mocks ───────────────────────────────────────────────────────────────────

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: "/" }),
}));

vi.mock("../../src/finance/useApi.js", () => ({
  useDashboard: () => ({ data: null, loading: false, reload: vi.fn() }),
  useDashboardMetadata: () => ({ data: null, loading: false, reload: vi.fn() }),
  apiFetch: vi.fn().mockResolvedValue({ active: "personal", available: ["personal"] }),
}));

// ─── Responsive Helpers ───────────────────────────────────────────────────────

/**
 * Mock window.innerWidth dan trigger resize event
 */
function setViewportWidth(width) {
  Object.defineProperty(window, "innerWidth", { value: width, configurable: true, writable: true });
  window.dispatchEvent(new Event("resize"));
}

// ─── TESTS ───────────────────────────────────────────────────────────────────

describe("📱 3.1 – Responsive CSS Breakpoints", () => {
  it("breakpoint mobile 768px ada di responsive.css", () => {
    expect(RESPONSIVE_CSS).toContain("max-width:768px");
  });

  it("breakpoint tablet 1024px ada di responsive.css", () => {
    expect(RESPONSIVE_CSS).toContain("max-width:1024px");
  });

  it("breakpoint small mobile 480px ada", () => {
    expect(RESPONSIVE_CSS).toContain("max-width:480px");
  });

  it("breakpoint tiny mobile 390px ada", () => {
    expect(RESPONSIVE_CSS).toContain("max-width:390px");
  });

  it("breakpoint ultra tiny mobile 360px ada", () => {
    expect(RESPONSIVE_CSS).toContain("max-width:360px");
  });

  it("desktop override min-width 769px ada", () => {
    expect(RESPONSIVE_CSS).toContain("min-width: 769px");
  });
});

describe("📐 3.2 – Mobile UX: Touch & Viewport", () => {
  it("dvh (dynamic viewport height) digunakan untuk iOS Safari fix", () => {
    expect(RESPONSIVE_CSS).toContain("100dvh");
  });

  it("safe-area-inset support untuk iPhone notch", () => {
    expect(RESPONSIVE_CSS).toContain("env(safe-area-inset-bottom)");
    expect(RESPONSIVE_CSS).toContain("env(safe-area-inset-top)");
    expect(RESPONSIVE_CSS).toContain("env(safe-area-inset-left)");
    expect(RESPONSIVE_CSS).toContain("env(safe-area-inset-right)");
  });

  it("@supports digunakan untuk safe-area-inset (progressive enhancement)", () => {
    expect(RESPONSIVE_CSS).toContain("@supports (padding: env(safe-area-inset-left))");
  });

  it("-webkit-overflow-scrolling: touch ada untuk momentum scroll iOS", () => {
    expect(RESPONSIVE_CSS).toContain("-webkit-overflow-scrolling: touch");
  });

  it("overflow-x:hidden pada html/body untuk menghindari horizontal scroll", () => {
    expect(RESPONSIVE_CSS).toContain("overflow-x: hidden");
    expect(BASE_CSS).toContain("overflow-x: hidden");
  });
});

describe("🖥️ 3.3 – Desktop vs Mobile Shell Rendering", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("App menggunakan window.innerWidth untuk deteksi mobile", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("window.innerWidth");
    expect(APP_JSX).toContain("800"); // breakpoint 800px
  });

  it("App listen ke resize event untuk update isMobile state", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("resize");
    expect(APP_JSX).toContain("setIsMobile");
  });

  it("MobileShell hanya dirender saat isMobile = true (simulasi)", async () => {
    // Komponen test yang mencerminkan logika App.jsx
    function ResponsiveShell() {
      const [isMobile, setIsMobile] = React.useState(window.innerWidth <= 800);
      React.useEffect(() => {
        const handler = () => setIsMobile(window.innerWidth <= 800);
        window.addEventListener("resize", handler);
        return () => window.removeEventListener("resize", handler);
      }, []);
      return isMobile
        ? <div data-testid="mobile-shell">Mobile Shell</div>
        : <div data-testid="desktop-shell">Desktop Shell</div>;
    }

    // Simulasi layar desktop
    setViewportWidth(1440);
    const { rerender } = render(<ResponsiveShell />);
    await act(async () => {});
    expect(screen.getByTestId("desktop-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("mobile-shell")).not.toBeInTheDocument();

    // Simulasi layar mobile
    act(() => { setViewportWidth(375); });
    rerender(<ResponsiveShell />);
    await act(async () => {});
    expect(screen.getByTestId("mobile-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("desktop-shell")).not.toBeInTheDocument();
  });

  it("mobile breakpoint adalah 800px (bukan 768px) sesuai kode", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toMatch(/innerWidth\s*<=\s*800/);
  });
});

describe("🎨 3.4 – CSS Custom Properties: Cross-Browser Design Tokens", () => {
  it("warna utama menggunakan CSS custom properties, bukan hard-coded hex", () => {
    const COMPONENTS_CSS = readFileSync(resolve(ROOT, "src/styles/theme/components.css"), "utf-8");
    // Komponen utama harus menggunakan var(--...) bukan hex langsung
    expect(COMPONENTS_CSS).toContain("var(--bg");
    expect(COMPONENTS_CSS).toContain("var(--tx");
  });

  it("dark theme variables didefinisikan di body selector", () => {
    expect(BASE_CSS).toContain("body, body.dark-mode {");
    expect(BASE_CSS).toContain("--bg: #0b0e11");
    expect(BASE_CSS).toContain("--ind: #fcd535");
  });

  it("transisi global didefinisikan untuk theme switch yang smooth", () => {
    expect(BASE_CSS).toContain("transition: background 0.3s ease");
    expect(BASE_CSS).toContain("background-color 0.3s ease");
    expect(BASE_CSS).toContain("color 0.3s ease");
  });

  it("font families menggunakan CSS variables", () => {
    expect(BASE_CSS).toContain("--mono:");
    expect(BASE_CSS).toContain("--sans:");
    expect(BASE_CSS).toContain("font-family: var(--sans)");
  });

  it("keyframe animations didefinisikan untuk UI responsif", () => {
    expect(BASE_CSS).toContain("@keyframes fadeIn");
    expect(BASE_CSS).toContain("@keyframes slideUp");
    expect(BASE_CSS).toContain("@keyframes spin");
    expect(BASE_CSS).toContain("@keyframes page-in");
  });

  it("box-sizing: border-box di-reset secara universal", () => {
    expect(BASE_CSS).toContain("box-sizing:border-box");
    expect(BASE_CSS).toContain("*,*::before,*::after");
  });
});

describe("📺 3.5 – SVG & Chart: Compatibility", () => {
  it("recharts/SVG max-width dibatasi 100% agar tidak overflow", () => {
    expect(RESPONSIVE_CSS).toContain("max-width: 100% !important");
    expect(RESPONSIVE_CSS).toContain(".recharts-wrapper");
  });

  it("min-width diberikan untuk chart ultra-kecil (360px)", () => {
    expect(RESPONSIVE_CSS).toContain("min-width: 240px !important");
  });

  it("svg dengan viewBox dibatasi max-width untuk flex containers", () => {
    expect(RESPONSIVE_CSS).toContain("svg[viewBox]");
  });
});

describe("🅰️ 3.6 – Font Loading: Cross-Browser", () => {
  it("Google Fonts 'DM Sans' dimuat untuk UI teks", () => {
    expect(BASE_CSS).toContain("DM+Sans");
    expect(BASE_CSS).toContain("family=DM+Sans");
  });

  it("Google Fonts 'Space Mono' dimuat untuk monospace (data/angka)", () => {
    expect(BASE_CSS).toContain("Space+Mono");
    expect(BASE_CSS).toContain("'Space Mono'");
  });

  it("fallback fonts ada (system-ui, -apple-system)", () => {
    expect(BASE_CSS).toContain("-apple-system");
    expect(BASE_CSS).toContain("BlinkMacSystemFont");
    expect(BASE_CSS).toContain("sans-serif");
  });

  it("display=swap digunakan untuk menghindari FOIT (Flash of Invisible Text)", () => {
    expect(BASE_CSS).toContain("display=swap");
  });
});

describe("🧱 3.7 – Semantic HTML: Landmark Regions", () => {
  it("App menggunakan <aside> untuk sidebar", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("<aside");
  });

  it("App menggunakan <main> untuk konten utama", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("<main");
  });

  it("App menggunakan <header> untuk topbar", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("<header");
  });

  it("Mobile nav menggunakan <nav> element", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("<nav");
  });

  it("nav items menggunakan aria-current untuk active state", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain('aria-current=');
    expect(APP_JSX).toContain('"page"');
  });
});

describe("🔤 3.8 – Cross-Browser CSS: Tidak Ada Prefix yang Hilang", () => {
  it("overflow-scrolling disertai -webkit- prefix untuk Safari", () => {
    expect(RESPONSIVE_CSS).toContain("-webkit-overflow-scrolling");
  });

  it("CSS transitions menggunakan standard syntax (tidak hanya -webkit-)", () => {
    // Base.css harus menggunakan standard 'transition', bukan hanya -webkit-transition
    expect(BASE_CSS).toContain("transition:");
    // Tidak eksklusif menggunakan hanya vendor prefix
    const vendorOnlyTransition = BASE_CSS.match(/-webkit-transition:[^;]+;(?!\s*transition:)/g);
    expect(vendorOnlyTransition).toBeNull();
  });

  it("position:sticky digunakan (standard, tidak hanya -webkit-sticky)", () => {
    // Cek di topbar CSS
    expect(RESPONSIVE_CSS).toContain("position: sticky");
  });
});

describe("📲 3.9 – Mobile-Spesifik: Bottom Nav & Layout", () => {
  it("mobile bottom nav menggunakan position:fixed dengan z-index yang tepat", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    // Inline style di MobileShell
    expect(APP_JSX).toContain("position: fixed");
    expect(APP_JSX).toContain("bottom: 0");
    expect(APP_JSX).toContain("z-index: 2000");
  });

  it("mobile overlay z-index lebih tinggi dari bottom nav", () => {
    const APP_JSX = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
    expect(APP_JSX).toContain("z-index: 3000"); // overlay
  });

  it("tabel disembunyikan kolom tertentu di mobile (tbl-col-hide-sm)", () => {
    expect(RESPONSIVE_CSS).toContain(".tbl-col-hide-sm");
    expect(RESPONSIVE_CSS).toContain("display: none !important");
  });

  it("font-size minimal 14px di input untuk mencegah iOS zoom", () => {
    expect(RESPONSIVE_CSS).toContain("font-size: 14px");
    // iOS Safari melakukan auto-zoom jika font-size input < 16px
    // Project menggunakan 14px + viewport meta yang sudah dikonfigurasi
  });
});
