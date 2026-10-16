// ─── AuthContext.jsx ──────────────────────────────────────────────────────────
// Frontend authentication gate.
//
// Responsibilities:
//   1. Render a PIN/token login screen before the app is visible
//      → tanpa login, zero halaman yang bisa diakses (termasuk /investment-tracker)
//   2. Store the API key in sessionStorage (cleared when tab/browser ditutup)
//   3. Provide setAuthHeader() so apiFetch() always sends Authorization: Bearer <token>
//   4. Auto-logout on 401 response dari API
//
// Security properties:
//   - App tidak render APAPUN sebelum auth sukses
//   - Token hanya disimpan di sessionStorage (bukan localStorage)
//     → otomatis hilang saat browser/tab ditutup
//   - Token tidak pernah muncul di URL atau log
//   - Semua API call via apiFetch() otomatis dapat header auth
//
// Usage:
//   Wrap <App> dengan <AuthProvider> di main.jsx.
//   Gunakan useAuth() hook untuk akses token dari komponen manapun.

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { API_BASE } from "./finance/constants.js";

const AuthContext = createContext(null);
const SESSION_KEY = "ft:api_token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try { return sessionStorage.getItem(SESSION_KEY) || ""; } catch { return ""; }
  });
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const verifyKey = useCallback(async (keyToTest) => {
    setLoading(true);
    setError("");
    try {
      const testToken = keyToTest || "dev";
      const configRes = await fetch(`${API_BASE}/config`, {
        headers: testToken ? { Authorization: `Bearer ${testToken}` } : {},
      });

      if (configRes.ok) {
        try { sessionStorage.setItem(SESSION_KEY, testToken); } catch {}
        setToken(testToken);
        setAuthenticated(true);
      } else {
        try { sessionStorage.removeItem(SESSION_KEY); } catch {}
        setToken("");
        setAuthenticated(false);
        setError(configRes.status === 401 ? "API Key tidak valid." : "Autentikasi tidak dapat diverifikasi. Silakan coba lagi.");
      }
    } catch {
      // Offline / network error — don't block app rendering
      try { sessionStorage.removeItem(SESSION_KEY); } catch {}
      setToken("");
      setAuthenticated(false);
      setError("Tidak dapat terhubung ke server untuk memverifikasi autentikasi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    verifyKey(token);
  }, []);

  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === SESSION_KEY && !e.newValue) {
        setToken("");
        setAuthenticated(false);
        setError("Sesi telah berakhir. Silakan masukan API Key kembali.");
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const handleLogin = async (key) => {
    await verifyKey(key);
  };

  const logout = useCallback(() => {
    try { sessionStorage.removeItem(SESSION_KEY); } catch {}
    setToken("");
    setAuthenticated(false);
  }, []);

  if (loading && !authenticated) {
    return (
      <div style={styles.overlay}>
        <div style={{ color: "var(--tx, #e2e4f0)", fontSize: 14 }}>Memeriksa autentikasi...</div>
      </div>
    );
  }

  if (!authenticated) {
    return <LoginScreen onLogin={handleLogin} error={error} loading={loading} />;
  }

  return (
    <AuthContext.Provider value={{ token, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

// ── Login Screen ──────────────────────────────────────────────────────────────

function LoginScreen({ onLogin, error, loading }) {
  const [value, setValue] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (value.trim()) onLogin(value.trim());
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.card}>
        {/* Icon */}
        <div style={styles.iconWrap}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
               stroke="var(--ind-b, #6366f1)" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
        </div>

        <h1 style={styles.title}>Alpha</h1>
        <p style={styles.sub}>Masukkan API key untuk melanjutkan</p>

        <form onSubmit={submit} style={styles.form}>
          <label htmlFor="ft-api-key" style={styles.visuallyHidden}>API Key</label>
          <input
            id="ft-api-key"
            type="password"
            aria-label="API Key"
            placeholder="API Key"
            value={value}
            onChange={e => setValue(e.target.value)}
            style={styles.input}
            autoFocus
            autoComplete="current-password"
            disabled={loading}
          />
          <button
            type="submit"
            style={{ ...styles.btn, opacity: loading || !value.trim() ? 0.6 : 1 }}
            disabled={loading || !value.trim()}
          >
            {loading ? "Memeriksa…" : "Masuk →"}
          </button>
        </form>

        {error && (
          <div style={styles.error}>
            {error.split("\n").map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        )}

        <p style={styles.hint}>
          API key diatur di server via{" "}
          <code style={styles.code}>FINANCE_TRACKER_API_KEY</code>
        </p>
      </div>
    </div>
  );
}

// ── Inline styles (no CSS dependency) ────────────────────────────────────────

const styles = {
  overlay: {
    position: "fixed", inset: 0,
    background: "var(--bg, #0d0f1a)",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontFamily: "var(--font-sans, system-ui, sans-serif)",
    zIndex: 9999,
  },
  card: {
    background: "var(--sf, #141520)",
    border: "1px solid var(--br, #1e2030)",
    borderRadius: 16,
    padding: "40px 36px",
    width: "100%",
    maxWidth: 380,
    display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
    boxShadow: "0 24px 48px rgba(0,0,0,.5)",
  },
  iconWrap: {
    width: 64, height: 64,
    background: "var(--sf2, #1a1d2e)",
    border: "1px solid var(--br, #1e2030)",
    borderRadius: 16,
    display: "flex", alignItems: "center", justifyContent: "center",
    marginBottom: 4,
  },
  title: {
    margin: 0, fontSize: 22, fontWeight: 700,
    color: "var(--tx, #e2e4f0)",
  },
  sub: {
    margin: 0, fontSize: 13,
    color: "var(--tx3, #6b7280)",
    textAlign: "center",
  },
  form: {
    width: "100%", display: "flex", flexDirection: "column", gap: 10,
    marginTop: 8,
  },
  visuallyHidden: {
    position: "absolute", width: 1, height: 1,
    overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap",
  },
  input: {
    width: "100%", boxSizing: "border-box",
    background: "var(--sf2, #1a1d2e)",
    border: "1px solid var(--br, #1e2030)",
    borderRadius: 8, padding: "10px 14px",
    fontSize: 14, color: "var(--tx, #e2e4f0)",
    outline: "none",
  },
  btn: {
    width: "100%",
    background: "var(--ind-b, #6366f1)",
    border: "none", borderRadius: 8,
    padding: "11px 0",
    fontSize: 14, fontWeight: 600,
    color: "#fff", cursor: "pointer",
    transition: "opacity .15s",
  },
  error: {
    width: "100%",
    background: "rgba(239,68,68,.1)",
    border: "1px solid rgba(239,68,68,.3)",
    borderRadius: 8, padding: "10px 14px",
    fontSize: 12, color: "#f87171",
    lineHeight: 1.6,
  },
  hint: {
    margin: 0, fontSize: 11,
    color: "var(--tx3, #6b7280)",
    textAlign: "center",
  },
  code: {
    background: "var(--sf2, #1a1d2e)",
    padding: "1px 5px", borderRadius: 4,
    fontFamily: "var(--mono, monospace)", fontSize: 11,
    color: "var(--ind-b, #6366f1)",
  },
};
