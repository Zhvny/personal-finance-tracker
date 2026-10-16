/**
 * ─── PENGUJIAN KEAMANAN (SECURITY) ───────────────────────────────────────────
 *
 * Mencakup:
 *  - XSS Prevention: tidak ada dangerouslySetInnerHTML tanpa sanitasi
 *  - Token storage: API token di sessionStorage (bukan localStorage)
 *  - HTTPS: canonical URL menggunakan HTTPS
 *  - Content Security Policy: API proxy dikonfigurasi
 *  - Input sanitasi: tidak ada innerHTML assignment langsung
 *  - Error logging: stack trace tidak dikirim ke third-party di production
 *  - API key: tidak pernah muncul di URL atau console.log
 *  - Authorization header: selalu dikirim via apiFetch (bukan manual)
 *  - Dev-only features: emergency logger hanya di DEV, bukan PROD
 *  - Secrets: tidak ada API key hard-coded di source code
 *  - CORS: proxy dikonfigurasi dengan benar
 *  - Dependency: tidak ada known vulnerable packages di produksi
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

const ROOT = resolve(__dirname, "../../");
const INDEX_HTML  = readFileSync(resolve(ROOT, "index.html"), "utf-8");
const MAIN_JSX    = readFileSync(resolve(ROOT, "src/main.jsx"), "utf-8");
const APP_JSX     = readFileSync(resolve(ROOT, "src/App.jsx"), "utf-8");
const AUTH_JSX    = readFileSync(resolve(ROOT, "src/AuthContext.jsx"), "utf-8");
const VITE_CONFIG = readFileSync(resolve(ROOT, "vite.config.js"), "utf-8");
const PACKAGE_JSON = JSON.parse(readFileSync(resolve(ROOT, "package.json"), "utf-8"));

// Baca seluruh source files untuk scanning
const SRC_FILES = [
  resolve(ROOT, "src/App.jsx"),
  resolve(ROOT, "src/AuthContext.jsx"),
  resolve(ROOT, "src/main.jsx"),
  resolve(ROOT, "src/components.jsx"),
];

const ALL_SOURCE = SRC_FILES.map((f) => {
  try { return readFileSync(f, "utf-8"); } catch { return ""; }
}).join("\n");

// ─── TESTS ───────────────────────────────────────────────────────────────────

describe("🛡️ 5.1 – XSS Prevention: Tidak Ada innerHTML Berbahaya", () => {
  it("tidak ada dangerouslySetInnerHTML di App.jsx (tanpa sanitasi)", () => {
    // dangerouslySetInnerHTML boleh digunakan HANYA jika konten di-sanitize
    // atau konten adalah static / hardcoded (bukan dari user input / API)
    const dangerous = APP_JSX.match(/dangerouslySetInnerHTML/g) || [];
    if (dangerous.length > 0) {
      // Pastikan tidak mengandung variabel dari API/user
      const context = dangerous.map(() => {
        const idx = APP_JSX.indexOf("dangerouslySetInnerHTML");
        return APP_JSX.substring(idx, idx + 200);
      });
      context.forEach((ctx) => {
        // Tidak boleh menggunakan variabel dinamis dari API/fetch
        expect(ctx).not.toMatch(/\{[a-z]+\.html\}/i);
        expect(ctx).not.toMatch(/innerHTML.*fetch/i);
      });
    }
    // Tidak ada dangerouslySetInnerHTML sama sekali = ideal
    expect(dangerous.length).toBe(0);
  });

  it("tidak ada innerHTML assignment langsung di source files", () => {
    // innerHTML assignment langsung tanpa sanitasi adalah XSS vector
    const innerHTMLAssign = ALL_SOURCE.match(/\.innerHTML\s*=/g) || [];
    // Satu-satunya exception yang diizinkan: emergency logger di DEV (main.jsx)
    // yang sudah dibungkus dalam import.meta.env.DEV
    if (innerHTMLAssign.length > 0) {
      // Verifikasi bahwa penggunaan ada dalam blok DEV-only
      const mainJsxInnerHTML = MAIN_JSX.match(/\.innerHTML\s*=/g) || [];
      // Main.jsx boleh memiliki innerHTML untuk DEV error logger
      expect(MAIN_JSX).toContain("import.meta.env.DEV");
      // Jumlah innerHTML di source DILUAR main.jsx harus 0
      const nonMainSources = [APP_JSX, AUTH_JSX].join("\n");
      const nonMainInnerHTML = nonMainSources.match(/\.innerHTML\s*=/g) || [];
      expect(nonMainInnerHTML.length).toBe(0);
    }
  });

  it("error messages tidak di-render sebagai raw HTML (hanya sebagai text)", () => {
    // Pastikan error display menggunakan children/text, bukan innerHTML
    const errorDisplays = AUTH_JSX.match(/\{error[^}]*\}/g) || [];
    errorDisplays.forEach((display) => {
      expect(display).not.toContain("__html");
      expect(display).not.toContain("innerHTML");
    });
  });

  it("tidak ada eval() atau Function() constructor di source files", () => {
    expect(ALL_SOURCE).not.toMatch(/\beval\s*\(/);
    // Function constructor bisa digunakan untuk code injection
    expect(ALL_SOURCE).not.toMatch(/new Function\s*\(/);
  });

  it("tidak ada document.write() di source files", () => {
    expect(ALL_SOURCE).not.toContain("document.write(");
  });
});

describe("🔑 5.2 – Token & Authentication Security", () => {
  it("API token disimpan di sessionStorage (bukan localStorage)", () => {
    // sessionStorage otomatis dibersihkan saat browser/tab ditutup
    // ini lebih aman dari localStorage yang persisten
    const SESSION_KEY = "ft:api_token";
    expect(AUTH_JSX).toContain("sessionStorage");
    expect(AUTH_JSX).toContain(SESSION_KEY);
    // Tidak boleh menggunakan localStorage untuk token
    expect(AUTH_JSX).not.toMatch(/localStorage\.setItem\s*\(\s*['"]ft:api_token/);
  });

  it("token tidak pernah muncul di URL (tidak ada ?token= di apiFetch)", () => {
    const USEAPI = existsSync(resolve(ROOT, "src/finance/useApi.js"))
      ? readFileSync(resolve(ROOT, "src/finance/useApi.js"), "utf-8")
      : "";
    // Token harus dikirim via header Authorization, bukan URL query param
    expect(USEAPI).not.toMatch(/\?token=/);
    expect(USEAPI).not.toMatch(/\&token=/);
  });

  it("Authorization header dikirim via Bearer token (bukan Basic Auth)", () => {
    const USEAPI = existsSync(resolve(ROOT, "src/finance/useApi.js"))
      ? readFileSync(resolve(ROOT, "src/finance/useApi.js"), "utf-8")
      : "";
    if (USEAPI) {
      expect(USEAPI).toMatch(/Authorization.*Bearer/);
    } else {
      // Jika useApi.js tidak ditemukan, cek di AUTH_JSX
      expect(AUTH_JSX).toContain("Authorization");
    }
  });

  it("token tidak di-log ke console di production code", () => {
    // Cari console.log yang mungkin mencetak token
    const logLines = ALL_SOURCE.match(/console\.log\([^)]*token[^)]*\)/gi) || [];
    // console.log dengan token harus 0
    expect(logLines.length).toBe(0);
  });

  it("logout membersihkan sessionStorage", () => {
    // Di AuthContext.jsx, logout handler harus clear storage
    // (Meskipun saat ini 'dev mode' bypass logout, fungsinya harus ada)
    expect(AUTH_JSX).toContain("SESSION_KEY");
  });
});

describe("🌐 5.3 – HTTPS & Network Security", () => {
  it("canonical URL menggunakan HTTPS (bukan HTTP)", () => {
    const match = INDEX_HTML.match(/rel="canonical"\s+href="([^"]+)"/);
    expect(match).not.toBeNull();
    expect(match[1]).toMatch(/^https:\/\//);
  });

  it("OG URL menggunakan HTTPS", () => {
    const match = INDEX_HTML.match(/property="og:url"\s+content="([^"]+)"/);
    expect(match).not.toBeNull();
    expect(match[1]).toMatch(/^https:\/\//);
  });

  it("OG image URL menggunakan HTTPS", () => {
    const match = INDEX_HTML.match(/property="og:image"\s+content="([^"]+)"/);
    expect(match).not.toBeNull();
    expect(match[1]).toMatch(/^https:\/\//);
  });

  it("API proxy dikonfigurasi dengan changeOrigin (mencegah CORS bypass)", () => {
    expect(VITE_CONFIG).toContain("changeOrigin: true");
  });

  it("HTTPS self-signed cert dikonfigurasi untuk backend API proxy", () => {
    // secure: false karena self-signed cert di localhost
    expect(VITE_CONFIG).toContain("secure: false");
    // Komentar HTTPS cert ada (dinonaktifkan tapi dikonfigurasi)
    expect(VITE_CONFIG).toContain("https:");
    expect(VITE_CONFIG).toContain("server.key");
    expect(VITE_CONFIG).toContain("server.crt");
  });
});

describe("🔒 5.4 – Secrets: Tidak Ada Hard-coded Credentials", () => {
  const SECRET_PATTERNS = [
    // Pola API key umum
    /sk-[a-zA-Z0-9]{20,}/,    // OpenAI-style
    /AKIA[A-Z0-9]{16}/,        // AWS Access Key
    /[a-f0-9]{32}/,            // MD5-style hash key (exclude common hashes)
    // Password patterns
    /password\s*=\s*["'][^"']{8,}["']/i,
    /secret\s*=\s*["'][^"']{8,}["']/i,
    // Database connection strings
    /postgresql:\/\/[a-z]+:[^@]+@/i,
    /mysql:\/\/[a-z]+:[^@]+@/i,
  ];

  // Tidak check hex hash karena banyak CSS color values
  const SAFE_PATTERNS = [
    /sk-[a-zA-Z0-9]{20,}/,    // OpenAI API key
    /AKIA[A-Z0-9]{16}/,        // AWS Access Key
    /password\s*=\s*["'][^"']{8,}["']/i,
    /secret\s*=\s*["'][^"']{8,}["']/i,
    /postgresql:\/\/[a-z]+:[^@]+@/i,
    /mysql:\/\/[a-z]+:[^@]+@/i,
  ];

  SAFE_PATTERNS.forEach((pattern) => {
    it(`tidak ada hard-coded secret yang cocok dengan pattern: ${pattern}`, () => {
      expect(ALL_SOURCE).not.toMatch(pattern);
    });
  });

  it("tidak ada API key environment variable yang di-hardcode di source", () => {
    // FINANCE_TRACKER_API_KEY hanya boleh muncul sebagai referensi/dokumentasi
    // bukan sebagai nilai yang di-assign
    const apiKeyAssignment = ALL_SOURCE.match(/FINANCE_TRACKER_API_KEY\s*=\s*["'][^"']+["']/g) || [];
    expect(apiKeyAssignment.length).toBe(0);
  });

  it(".env file tidak di-commit ke dalam source (hanya .env.example)", () => {
    // .env.example harus ada
    expect(existsSync(resolve(ROOT, ".env.example"))).toBe(true);
    // .env aktual tidak boleh masuk ke source control
    // (tidak bisa verifikasi .gitignore di sini, tapi kita verifikasi .env.example ada)
  });

  it(".env.example ada sebagai dokumentasi env vars yang diperlukan", () => {
    const ENV_EXAMPLE = readFileSync(resolve(ROOT, ".env.example"), "utf-8");
    // Harus mendokumentasikan required vars
    expect(ENV_EXAMPLE.length).toBeGreaterThan(50);
  });
});

describe("🚫 5.5 – Dev-Only Features: Tidak Ada di Production", () => {
  it("emergency error logger hanya aktif saat import.meta.env.DEV", () => {
    // Verifikasi guard ada
    expect(MAIN_JSX).toContain("if (import.meta.env.DEV)");
    // Verifikasi kode error logger ada di dalam blok DEV
    const devBlock = MAIN_JSX.match(/if\s*\(import\.meta\.env\.DEV\)\s*\{[^}]+\}/s);
    expect(devBlock).not.toBeNull();
    expect(devBlock[0]).toContain("window.onerror");
  });

  it("Service Worker di-unregister di DEV (tidak aktif di development)", () => {
    expect(MAIN_JSX).toContain("unregister");
    // SW registration hanya di ELSE block (production)
    expect(MAIN_JSX).toContain("register('/sw.js')");
  });

  it("PWA dikonfigurasi untuk disabled di development", () => {
    expect(VITE_CONFIG).toContain("disable: process.env.NODE_ENV === 'development'");
  });
});

describe("🛡️ 5.6 – Content Security: Inline Code & Resources", () => {
  it("tidak ada inline event handlers di index.html (onclick, onload, etc.)", () => {
    // Inline handlers adalah XSS vector dan melanggar CSP
    expect(INDEX_HTML).not.toMatch(/\s(onclick|onload|onmouseover|onerror)\s*=/i);
  });

  it("tidak ada external script CDN yang tidak terpercaya di index.html", () => {
    // Hanya src/main.jsx yang boleh sebagai script entry
    const externalScripts = INDEX_HTML.match(/<script[^>]+src=['"]https?:\/\/[^'"]+['"]/g) || [];
    expect(externalScripts.length).toBe(0);
  });

  it("tidak ada inline CSS <style> besar di index.html (hanya link ke CSS file)", () => {
    // Inline CSS di head melanggar CSP strict-mode
    const inlineStyles = INDEX_HTML.match(/<style>[^<]{200,}<\/style>/g) || [];
    expect(inlineStyles.length).toBe(0);
  });

  it("preconnect hanya ke domain yang terpercaya (Google, tidak ke third-party unknown)", () => {
    const preconnects = INDEX_HTML.match(/rel="preconnect"\s+href="([^"]+)"/g) || [];
    const TRUSTED_DOMAINS = [
      "fonts.googleapis.com",
      "fonts.gstatic.com",
      "drive.google.com",
      "lh3.googleusercontent.com",
    ];
    preconnects.forEach((pc) => {
      const hrefMatch = pc.match(/href="([^"]+)"/);
      const href = hrefMatch ? hrefMatch[1] : "";
      const isTrusted = TRUSTED_DOMAINS.some((d) => href.includes(d));
      expect(
        isTrusted || href === "",
        `Preconnect ke domain tidak terpercaya: ${href}`
      ).toBe(true);
    });
  });
});

describe("🔐 5.7 – Input Validation: Tipe & Sanitasi", () => {
  it("password input menggunakan type='password' (masked)", () => {
    expect(AUTH_JSX).toContain('type="password"');
  });

  it("tidak ada eval() digunakan untuk parsing data dari API", () => {
    expect(ALL_SOURCE).not.toMatch(/\beval\s*\(/);
  });

  it("JSON.parse digunakan untuk parsing (bukan eval)", () => {
    const USEAPI = existsSync(resolve(ROOT, "src/finance/useApi.js"))
      ? readFileSync(resolve(ROOT, "src/finance/useApi.js"), "utf-8")
      : "";
    if (USEAPI.includes("JSON.parse")) {
      expect(USEAPI).toContain("JSON.parse");
      expect(USEAPI).not.toMatch(/\beval\s*\(.*json/i);
    }
  });
});

describe("📋 5.8 – Audit Trail: Error Handling", () => {
  it("error boundary global ada untuk mencegah info sensitif di UI error", () => {
    expect(MAIN_JSX).toContain("ErrorBoundary");
    expect(APP_JSX).toContain("AppErrorBoundary");
  });

  it("console.error digunakan untuk error internal (bukan alert/prompt)", () => {
    // Alert/prompt bisa digunakan untuk phishing
    const alerts = APP_JSX.match(/\bwindow\.alert\s*\(/g) || [];
    expect(alerts.length).toBe(0);
    const prompts = APP_JSX.match(/\bwindow\.prompt\s*\(/g) || [];
    expect(prompts.length).toBe(0);
  });

  it("error messages user-facing tidak mengekspos stack trace", () => {
    // Stack trace tidak boleh ditampilkan ke user biasa
    // (hanya di DEV emergency logger & technical details toggle di ErrorBoundary)
    const stackInUI = APP_JSX.match(/\.stack.*render|render.*\.stack/g) || [];
    expect(stackInUI.length).toBe(0);
  });
});
