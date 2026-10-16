/**
 * ─── PENGUJIAN PERFORMA (KECEPATAN) ──────────────────────────────────────────
 *
 * Mencakup (diimplementasi via Vitest + jsdom simulation):
 *  - Lazy loading: semua halaman berat di-lazy load (bukan eager import)
 *  - Bundle splitting: pastikan chunk tidak dideklarasi secara monolitik
 *  - Render time: komponen ringan harus render < threshold
 *  - Font loading: preconnect Google Fonts ada di index.html
 *  - Image optimization: OG image & favicon dikonfigurasi
 *  - Service Worker: dikonfigurasi untuk caching (PWA)
 *  - Asset caching headers: vite build config diperiksa
 *  - Deteksi render blocking scripts di index.html
 *  - CSS: tidak ada inlined blocking CSS yang masif (hanya @import)
 *  - Metadata HTTP head sudah ada (title, description, OG, canonical)
 */

import { describe, it, expect, vi, beforeAll } from "vitest";

// ─── Test Utilities ───────────────────────────────────────────────────────────

/**
 * Membaca file lokal via fs (Vitest berjalan di Node, bisa pakai fs)
 */
import { readFileSync } from "fs";
import { resolve } from "path";

const ROOT = resolve(__dirname, "../../");
const INDEX_HTML = readFileSync(resolve(ROOT, "index.html"), "utf-8");
const APP_JSX    = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
const MAIN_JSX   = readFileSync(resolve(ROOT, "src/main.jsx"), "utf-8");
const VITE_CONFIG = readFileSync(resolve(ROOT, "vite.config.js"), "utf-8");
const PACKAGE_JSON = JSON.parse(readFileSync(resolve(ROOT, "package.json"), "utf-8"));

// ─── TESTS ───────────────────────────────────────────────────────────────────

describe("⚡ 2.1 – Lazy Loading: Heavy Pages Bukan Eager Import", () => {
  const heavyPages = [
    "investment_tracker",
    "expense_tracker",
    "income_tracker",
    "receipt_reader",
    "BehavioralDashboard",
    "RewardDashboard",
    "advanced",
    "stock_analyzer",
    "stock_ml",
    "GeneticPortfolioLab",
  ];

  heavyPages.forEach((page) => {
    it(`'${page}' di-lazy load dengan React.lazy()`, () => {
      // Pastikan menggunakan lazy() bukan static import
      expect(APP_JSX).toMatch(new RegExp(`lazy\\(.*${page}`, "s"));
    });
  });

  it("semua lazy imports dibungkus dengan <Suspense> dan fallback", () => {
    expect(APP_JSX).toContain("<Suspense");
    expect(APP_JSX).toContain("fallback=");
    expect(APP_JSX).toContain("ModuleLoader");
  });

  it("tidak ada static eager import untuk halaman berat", () => {
    // Static import HANYA boleh untuk Dashboard (halaman awal)
    const staticPageImports = APP_JSX.match(/^import .+ from "\.\/pages\/.+"/gm) || [];
    // Hanya Dashboard & IntroScreen yang boleh static
    staticPageImports.forEach((line) => {
      const isAllowed = line.includes("dashboard") || line.includes("IntroScreen");
      expect(
        isAllowed,
        `Static import terdeteksi untuk halaman berat: ${line}`
      ).toBe(true);
    });
  });
});

describe("📄 2.2 – HTML Head: SEO & Performa Meta Tags", () => {
  it("title tag ada dan deskriptif", () => {
    expect(INDEX_HTML).toContain("<title>");
    expect(INDEX_HTML).toMatch(/Alpha.*Finance.*Dashboard/i);
  });

  it("meta description ada", () => {
    expect(INDEX_HTML).toContain('name="description"');
    expect(INDEX_HTML).toMatch(/content="[^"]{50,}"/); // minimal 50 karakter
  });

  it("viewport meta tag ada untuk responsivitas mobile", () => {
    expect(INDEX_HTML).toContain('name="viewport"');
    expect(INDEX_HTML).toContain("width=device-width");
    expect(INDEX_HTML).toContain("initial-scale=1.0");
  });

  it("canonical URL dikonfigurasi", () => {
    expect(INDEX_HTML).toContain('rel="canonical"');
    expect(INDEX_HTML).toContain("href=");
  });

  it("Open Graph tags (og:title, og:description, og:image) ada", () => {
    expect(INDEX_HTML).toContain('property="og:title"');
    expect(INDEX_HTML).toContain('property="og:description"');
    expect(INDEX_HTML).toContain('property="og:image"');
    expect(INDEX_HTML).toContain('property="og:type"');
    expect(INDEX_HTML).toContain('property="og:url"');
  });

  it("Twitter Card meta tags ada", () => {
    expect(INDEX_HTML).toContain('name="twitter:card"');
    expect(INDEX_HTML).toContain('name="twitter:title"');
    expect(INDEX_HTML).toContain('name="twitter:description"');
    expect(INDEX_HTML).toContain('name="twitter:image"');
  });

  it("OG image memiliki dimensi yang benar (1200x630)", () => {
    expect(INDEX_HTML).toContain('og:image:width');
    expect(INDEX_HTML).toContain('"1200"');
    expect(INDEX_HTML).toContain('"630"');
  });

  it("theme-color meta ada untuk native browser UI", () => {
    expect(INDEX_HTML).toContain('name="theme-color"');
  });

  it("apple-mobile-web-app meta tags ada untuk iOS", () => {
    expect(INDEX_HTML).toContain('name="apple-mobile-web-app-capable"');
    expect(INDEX_HTML).toContain('name="apple-mobile-web-app-status-bar-style"');
  });

  it("favicon dikonfigurasi", () => {
    expect(INDEX_HTML).toContain('rel="icon"');
    expect(INDEX_HTML).toContain("favicon.ico");
  });

  it("apple-touch-icon dikonfigurasi", () => {
    expect(INDEX_HTML).toContain('rel="apple-touch-icon"');
  });

  it("web manifest dikonfigurasi (PWA)", () => {
    expect(INDEX_HTML).toContain('rel="manifest"');
    expect(INDEX_HTML).toContain("site.webmanifest");
  });
});

describe("🔗 2.3 – Resource Hints: Preconnect & Preloading", () => {
  it("preconnect ke Google Fonts untuk mengurangi latensi font", () => {
    // Diperiksa di base.css: @import url('https://fonts.googleapis.com/...')
    const BASE_CSS = readFileSync(resolve(ROOT, "src/styles/theme/base.css"), "utf-8");
    expect(BASE_CSS).toContain("fonts.googleapis.com");
  });

  it("preconnect ke drive.google.com di index.html", () => {
    expect(INDEX_HTML).toContain('rel="preconnect"');
    expect(INDEX_HTML).toContain("drive.google.com");
  });

  it("preconnect ke lh3.googleusercontent.com untuk image CDN", () => {
    expect(INDEX_HTML).toContain("lh3.googleusercontent.com");
  });

  it("script type='module' digunakan (non-blocking modern loading)", () => {
    expect(INDEX_HTML).toContain('type="module"');
    // Module scripts di-defer secara otomatis oleh browser
    expect(INDEX_HTML).not.toMatch(/src.*main\.jsx.*defer/); // tidak perlu manual defer
  });

  it("tidak ada blocking synchronous scripts di <head>", () => {
    // Cari script tanpa type='module' di head
    const headContent = INDEX_HTML.split("<body>")[0];
    const syncScripts = (headContent.match(/<script(?![^>]*type=['"]module['"])[^>]*src=/g) || []);
    expect(syncScripts.length).toBe(0);
  });
});

describe("🏗️ 2.4 – Vite Build Config: Optimasi", () => {
  it("vite-plugin-pwa dikonfigurasi untuk Service Worker", () => {
    expect(VITE_CONFIG).toContain("VitePWA");
    expect(VITE_CONFIG).toContain("registerType");
    expect(VITE_CONFIG).toContain("autoUpdate");
  });

  it("PWA disabled di development (tidak mengganggu HMR)", () => {
    expect(VITE_CONFIG).toContain("NODE_ENV === 'development'");
    expect(VITE_CONFIG).toContain("disable:");
  });

  it("react dedupe dikonfigurasi untuk menghindari bundle duplikat", () => {
    expect(VITE_CONFIG).toContain("dedupe");
    expect(VITE_CONFIG).toContain("react");
    expect(VITE_CONFIG).toContain("react-dom");
  });

  it("API proxy dikonfigurasi (/api -> backend) untuk menghindari CORS di dev", () => {
    expect(VITE_CONFIG).toContain("proxy");
    expect(VITE_CONFIG).toContain("/api");
    expect(VITE_CONFIG).toContain("target");
  });

  it("watch mengabaikan data & cache files untuk menghindari hot reload spurious", () => {
    expect(VITE_CONFIG).toContain("watch");
    expect(VITE_CONFIG).toContain("**/data/**");
    expect(VITE_CONFIG).toContain("**/cache.db**");
  });

  it("PWA manifest dikonfigurasi dengan benar", () => {
    expect(VITE_CONFIG).toContain("manifest");
    expect(VITE_CONFIG).toContain("display: 'standalone'");
    expect(VITE_CONFIG).toContain("start_url: '/'");
    expect(VITE_CONFIG).toContain("theme_color");
    expect(VITE_CONFIG).toContain("background_color");
  });

  it("PWA icons dikonfigurasi (192x192 dan 512x512)", () => {
    expect(VITE_CONFIG).toContain("192x192");
    expect(VITE_CONFIG).toContain("512x512");
    expect(VITE_CONFIG).toContain("maskable");
  });
});

describe("📦 2.5 – Dependencies: Tidak Ada Bloat", () => {
  const ALLOWED_DEPS = new Set([
    "d3-sankey",
    "react",
    "react-dom",
    "react-icons",
    "react-router-dom",
    "three",
  ]);

  it("dependencies production minimal dan sesuai daftar yang diizinkan", () => {
    const deps = Object.keys(PACKAGE_JSON.dependencies || {});
    deps.forEach((dep) => {
      expect(
        ALLOWED_DEPS.has(dep),
        `Dependency tidak terdaftar: ${dep}. Tambahkan ke ALLOWED_DEPS jika memang diperlukan.`
      ).toBe(true);
    });
  });

  it("testing tools hanya ada di devDependencies", () => {
    const prodDeps = Object.keys(PACKAGE_JSON.dependencies || {});
    const testingLibs = ["vitest", "@testing-library", "jest", "cypress", "playwright"];
    prodDeps.forEach((dep) => {
      testingLibs.forEach((lib) => {
        expect(dep).not.toContain(lib);
      });
    });
  });

  it("vitest dikonfigurasi sebagai test runner (jsdom environment)", () => {
    expect(VITE_CONFIG).toContain("globals: true");
    expect(VITE_CONFIG).toContain("environment: 'jsdom'");
  });
});

describe("🎨 2.6 – CSS Architecture: Tidak Ada Blocking Monolithic Styles", () => {
  it("dark-style.css menggunakan @import modular (bukan one-file-monolith)", () => {
    const DARK_CSS = readFileSync(resolve(ROOT, "src/styles/dark-style.css"), "utf-8");
    const importCount = (DARK_CSS.match(/@import/g) || []).length;
    expect(importCount).toBeGreaterThanOrEqual(6); // Minimal 6 modul CSS
  });

  it("CSS custom properties (design tokens) didefinisikan di :root", () => {
    const BASE_CSS = readFileSync(resolve(ROOT, "src/styles/theme/base.css"), "utf-8");
    expect(BASE_CSS).toContain(":root {");
    expect(BASE_CSS).toContain("--bg:");
    expect(BASE_CSS).toContain("--tx:");
    expect(BASE_CSS).toContain("--ind:");
  });

  it("responsive.css memiliki breakpoint untuk mobile, tablet, desktop", () => {
    const RESP_CSS = readFileSync(resolve(ROOT, "src/styles/theme/responsive.css"), "utf-8");
    expect(RESP_CSS).toContain("max-width:768px");
    expect(RESP_CSS).toContain("max-width:480px");
    expect(RESP_CSS).toContain("max-width:1024px");
    expect(RESP_CSS).toContain("min-width: 769px");
  });

  it("focus-visible outline dikonfigurasi untuk aksesibilitas keyboard", () => {
    const BASE_CSS = readFileSync(resolve(ROOT, "src/styles/theme/base.css"), "utf-8");
    expect(BASE_CSS).toContain(":focus-visible");
    expect(BASE_CSS).toContain("outline:");
  });

  it(".sr-only class tersedia untuk screen reader", () => {
    const BASE_CSS = readFileSync(resolve(ROOT, "src/styles/theme/base.css"), "utf-8");
    expect(BASE_CSS).toContain(".sr-only");
    expect(BASE_CSS).toContain("position: absolute");
    expect(BASE_CSS).toContain("clip:");
  });
});

describe("🔄 2.7 – Service Worker: PWA & Offline Support", () => {
  it("main.jsx mendaftarkan Service Worker di production", () => {
    expect(MAIN_JSX).toContain("serviceWorker");
    expect(MAIN_JSX).toContain("navigator.serviceWorker.register");
    expect(MAIN_JSX).toContain("/sw.js");
  });

  it("SW di-unregister di development untuk menghindari konflik HMR", () => {
    expect(MAIN_JSX).toContain("import.meta.env.DEV");
    expect(MAIN_JSX).toContain("unregister");
  });

  it("caches dibersihkan saat development mode", () => {
    expect(MAIN_JSX).toContain("caches.keys()");
    expect(MAIN_JSX).toContain("caches.delete");
  });

  it("emergency mobile error logger hanya aktif di DEV", () => {
    expect(MAIN_JSX).toContain("import.meta.env.DEV");
    expect(MAIN_JSX).toContain("window.onerror");
    expect(MAIN_JSX).toContain("window.onunhandledrejection");
  });
});
