// ─── useApi.js ────────────────────────────────────────────────────────────────
// Abstraction layer: ALL HTTP calls to the Python API bridge live here.
// Page components never call fetch() directly — they use these hooks/functions.
//
// High Cohesion  : only API call definitions here, zero rendering.
// Low Coupling   : only depends on constants.js, nothing else.
// Abstraction    : callers don't know if data is remote, cached, or mocked.

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { API_BASE } from "./constants.js";

// ── Auth token accessor ───────────────────────────────────────────────────────
// apiFetch() reads token from sessionStorage directly — avoids prop-drilling
// and works outside React component tree (e.g. event handlers, CSV download).
// Token is written there by AuthContext on login.
export function _getToken() {
  try { return sessionStorage.getItem("ft:api_token") || ""; } catch { return ""; }
}

// ── Generic fetch helper ──────────────────────────────────────────────────────
export async function apiFetch(path, options = {}, retries = 0) {
  const { signal, ...fetchOptions } = options;
  const token = _getToken();
  
  // If we know we're offline and this is a GET request, fail early to prevent spam
  const isGET = !fetchOptions.method || fetchOptions.method === "GET";
  if (window.__FT_OFFLINE__ && isGET && retries === 0) {
    throw new Error("API Offline (skipped)");
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(fetchOptions.headers || {}),
      },
    });

    // Success! Ensure offline flag is cleared
    if (window.__FT_OFFLINE__) {
      window.__FT_OFFLINE__ = false;
      window.dispatchEvent(new CustomEvent("ft:online"));
    }

    // 401 → token expired / invalid → trigger auto-logout via storage event
    if (res.status === 401) {
      try { sessionStorage.removeItem("ft:api_token"); } catch {}
      // Dispatch a storage event so AuthContext re-renders the login screen
      window.dispatchEvent(new StorageEvent("storage", {
        key: "ft:api_token", newValue: null, storageArea: sessionStorage,
      }));
      throw new Error("Sesi berakhir. Silakan login ulang.");
    }

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({ detail: res.statusText }));
      const error = new Error(errJson.detail || `HTTP ${res.status}`);
      error.status = res.status;
      error.url = `${API_BASE}${path}`;
      if (res.status >= 500) {
        error.type = (res.status === 502 || res.status === 504) ? "OFFLINE" : "INTERNAL";
      }
      throw error;
    }
    return res.json();
  } catch (e) {
    // Silent catch for AbortError — prevents error UI flickering during rapid navigation
    if (e.name === "AbortError") {
      return { __aborted: true };
    }

    // Retry only for GET requests and only for Network Errors (not HTTP errors like 404/500)
    // and only 1 retry instead of 2 to reduce spam.
    const isNetworkError = e instanceof TypeError || e.message === "Failed to fetch";
    
    if (isNetworkError) {
      e.type = "OFFLINE";
      e.url = `${API_BASE}${path}`;
    }

    if (isNetworkError && isGET && retries < 1) {

      console.warn(`Retrying API call (${retries + 1}/1): ${path}`);
      // Backoff: 2s
      await new Promise(resolve => setTimeout(resolve, 2000));
      return apiFetch(path, options, retries + 1);
    }
    
    // If it still fails after retries, set offline flag and start recovery watcher
    if (isNetworkError && isGET) {
      if (!window.__FT_OFFLINE__) {
        window.__FT_OFFLINE__ = true;
        window.dispatchEvent(new CustomEvent("ft:offline"));

        // Auto-recovery: poll /api/health every 10s until server is back
        if (!window.__FT_OFFLINE_WATCHER__) {
          window.__FT_OFFLINE_WATCHER__ = setInterval(async () => {
            try {
              const r = await fetch("/api/health", { method: "GET" });
              if (r.ok || r.status === 401) {
                // Server is reachable (even 401 = auth issue, not network issue)
                window.__FT_OFFLINE__ = false;
                window.dispatchEvent(new CustomEvent("ft:online"));
                clearInterval(window.__FT_OFFLINE_WATCHER__);
                window.__FT_OFFLINE_WATCHER__ = null;
              }
            } catch {
              // Still offline, keep polling
            }
          }, 10_000);
        }
      }
    }
    
    throw e;
  }
}

// ── Debounce hook ─────────────────────────────────────────────────────────────────────────────
export function useDebounce(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

// ── Persisted tab hook — remembers active tab across navigation ───────────────
export function usePersistedTab(key, defaultTab) {
  const [tab, setTabState] = useState(() => {
    try { return localStorage.getItem(`ft:tab:${key}`) || defaultTab; } catch { return defaultTab; }
  });
  const setTab = useCallback((t) => {
    setTabState(t);
    try { localStorage.setItem(`ft:tab:${key}`, t); } catch {}
  }, [key]);
  return [tab, setTab];
}

// ── Generic auto-refresh hook ─────────────────────────────────────────────────
/**
 * useAutoFetch: fetch `url` every `intervalMs` (default: on mount only).
 * Re-fetches whenever `deps` change or component becomes visible.
 */
export function useAutoFetch(url, { intervalMs = 0, deps = [] } = {}) {
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [error,      setError]      = useState(null);

  const dataRef = useRef(data);
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const prevUrlRef = useRef(url);
  useEffect(() => {
    if (prevUrlRef.current !== url) {
      prevUrlRef.current = url;
      setData(null);
      dataRef.current = null;
    }
  }, [url]);

  const reload = useCallback(async (signal, isBackground = false) => {
    if (!url) return;
    setIsFetching(true);
    if (!dataRef.current && !isBackground) {
      setLoading(true);
    }
    setError(null);
    try {
      const json = await apiFetch(url, { signal });
      if (json?.__aborted) return; // Ignore aborted requests
      setData(json);
      dataRef.current = json;
    } catch (e) {
      setError(e);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
        setIsFetching(false);
      }
    }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  // Run on mount and whenever deps change
  useEffect(() => {
    const controller = new AbortController();
    reload(controller.signal);
    return () => controller.abort();
  }, [reload]);

  // Optional background polling
  useEffect(() => {
    if (!intervalMs) return;
    const id = setInterval(() => reload(null, true), intervalMs);
    return () => clearInterval(id);
  }, [reload, intervalMs]);

  // Re-fetch when window/tab regains focus without triggering skeleton UI
  useEffect(() => {
    const onFocus = () => reload(null, true);
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [reload]);

  // Re-fetch when ft:reload event is emitted (e.g. mutation done elsewhere)
  useEffect(() => {
    const onFtReload = () => reload(null, true);
    window.addEventListener("ft:reload", onFtReload);
    return () => window.removeEventListener("ft:reload", onFtReload);
  }, [reload]);

  return { data, loading, isFetching, error, reload };
}

// ── SWR hook with localStorage persistence ────────────────────────────────────
/**
 * useCacheFetch: same as useAutoFetch but with Stale-While-Revalidate logic.
 * Reads from localStorage on mount, then background-fetches fresh data.
 */
export function useCacheFetch(url, { intervalMs = 0, deps = [] } = {}) {
  const cacheKey = `ft:cache:${url}`;
  const [data, setData] = useState(() => {
    if (!url) return null;
    try {
      const cached = localStorage.getItem(cacheKey);
      return cached ? JSON.parse(cached).data : null;
    } catch { return null; }
  });

  const [loading,    setLoading]    = useState(!data);
  const [isFetching, setIsFetching] = useState(false);
  const [error,      setError]      = useState(null);
  const [isStale,    setIsStale]    = useState(!!data);

  const dataRef = useRef(data);
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const reload = useCallback(async (signal, isBackground = false) => {
    if (!url) return;
    setIsFetching(true);
    if (!dataRef.current && !isBackground) {
      setLoading(true);
    }
    setError(null);
    try {
      const json = await apiFetch(url, { signal });
      if (json?.__aborted) return;
      
      setData(json);
      dataRef.current = json;
      setIsStale(false);
      try {
        localStorage.setItem(cacheKey, JSON.stringify({ data: json, ts: Date.now() }));
      } catch {}
    } catch (e) {
      setError(e);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
        setIsFetching(false);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  useEffect(() => {
    const controller = new AbortController();
    reload(controller.signal);
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!intervalMs) return;
    const id = setInterval(() => reload(null, true), intervalMs);
    return () => clearInterval(id);
  }, [reload, intervalMs]);

  useEffect(() => {
    const onFocus = () => reload(null, true);
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [reload]);

  useEffect(() => {
    const onFtReload = () => reload(null, true);
    window.addEventListener("ft:reload", onFtReload);
    return () => window.removeEventListener("ft:reload", onFtReload);
  }, [reload]);

  return { data, loading, isFetching, error, isStale, reload };
}

// ── Shared WebSocket Manager ──────────────────────────────────────────────────
// Singleton registry to ensure only one connection per URL exists.
const wsRegistry = new Map(); // url -> { socket, listeners: Set }

export function useWebSocket(path) {
  const [lastMessage, setLastMessage] = useState(null);
  const [status, setStatus] = useState("connecting");
  const [retry, setRetry] = useState(0);

  const url = useMemo(() => {
    if (!path) return null;
    if (path.startsWith("ws://") || path.startsWith("wss://")) return path;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // Auto-prefix relative paths with /api/ws/
    const fullPath = path.startsWith("/") ? path : `/api/ws/${path}`;
    return `${protocol}//${host}${fullPath}`;
  }, [path]);

  useEffect(() => {
    if (!url) return;

    let entry = wsRegistry.get(url);
    if (!entry) {
      const socket = new WebSocket(url);
      entry = { socket, listeners: new Set() };
      wsRegistry.set(url, entry);

      socket.onopen = () => entry.listeners.forEach(l => l.onStatus("open"));
      socket.onclose = () => {
        entry.listeners.forEach(l => l.onStatus("closed"));
        wsRegistry.delete(url);
        // Exponential backoff or simple delay retry
        entry.listeners.forEach(l => l.onRetry());
      };
      socket.onerror = () => entry.listeners.forEach(l => l.onStatus("error"));
      socket.onmessage = (e) => {
        let data = e.data;
        try { data = JSON.parse(e.data); } catch {}
        entry.listeners.forEach(l => l.onMessage(data));
      };
    }

    const listener = {
      onMessage: setLastMessage,
      onStatus: setStatus,
      onRetry: () => setTimeout(() => setRetry(r => r + 1), 5000)
    };
    entry.listeners.add(listener);
    
    // Sync status immediately
    const statusMap = ["connecting", "open", "closing", "closed"];
    setStatus(statusMap[entry.socket.readyState] || "closed");

    return () => {
      entry.listeners.delete(listener);
      if (entry.listeners.size === 0) {
        if (entry.socket.readyState <= 1) entry.socket.close();
        wsRegistry.delete(url);
      }
    };
  }, [url, retry]);

  const send = useCallback((data) => {
    const entry = wsRegistry.get(url);
    if (entry?.socket.readyState === 1) {
      entry.socket.send(typeof data === "string" ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }, [url]);

  return { send, lastMessage, status };
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export const useDashboard = (opts = {}) => useAutoFetch("/dashboard", { intervalMs: 30_000, ...opts });
export const useDashboardMetadata = (opts = {}) => useAutoFetch("/dashboard/metadata", opts);

// ─── Sankey Cashflow ──────────────────────────────────────────────────────────
export function useSankeyData(opts = {}) {
  const { data, loading, error, reload } = useDashboard(opts);

  const processedData = useMemo(() => {
    if (!data) return null;

    const nodes = [];
    const links = [];
    const income = data.income?.by_type || {};
    const expenses = data.expense?.by_category || {};
    
    // Nodes
    const totalNodeName = "Total Cash";
    
    let totalIn = 0;
    Object.entries(income).forEach(([type, amt]) => {
      nodes.push({ name: type, type: 'income' });
      links.push({ source: type, target: totalNodeName, value: amt });
      totalIn += amt;
    });

    let totalOut = 0;
    Object.entries(expenses).forEach(([cat, amt]) => {
      nodes.push({ name: cat, type: 'expense' });
      links.push({ source: totalNodeName, target: cat, value: amt });
      totalOut += amt;
    });

    // Central Node
    nodes.push({ name: totalNodeName, type: 'pivot' });

    // Balancing
    if (totalOut > totalIn) {
      const diff = totalOut - totalIn;
      nodes.push({ name: "Savings/Credit", type: 'source' });
      links.push({ source: "Savings/Credit", target: totalNodeName, value: diff });
    } else if (totalIn > totalOut) {
      const diff = totalIn - totalOut;
      nodes.push({ name: "Savings", type: 'sink' });
      links.push({ source: totalNodeName, target: "Savings", value: diff });
    }

    return { nodes, links };
  }, [data]);

  return { data: processedData, loading, error, reload };
}

// ─── Stock & Ticker Analysis (Granular Hooks for Lazy Loading) ────────────────
export const useTickerBase = (symbol, opts = {}) => 
  useAutoFetch(symbol ? `/stocks/analyze/${symbol}/base` : null, opts);

export const useChartData = (symbol, opts = {}) => 
  useAutoFetch(symbol ? `/stocks/analyze/${symbol}/chart` : null, opts);

export const useSentiment = (symbol, opts = {}) => 
  useAutoFetch(symbol ? `/stocks/analyze/${symbol}/sentiment` : null, opts);

export const useTechnicals = (symbol, opts = {}) => 
  useAutoFetch(symbol ? `/stocks/analyze/${symbol}/technicals` : null, opts);

// ─── App Config (FX rate etc.) ────────────────────────────────────────────────
// Single source of truth: value comes from /api/config set in api_server.py.
// Frontend never hardcodes FX_RATE — always reads from this hook.
export const useAppConfig = (opts = {}) => useAutoFetch("/config", opts);
// Convenience: returns a numeric FX rate, falling back to 16500 while loading.
export function useFxRate() {
  const { data } = useAppConfig();
  return data?.fx_rate ?? 16_500;
}

// ─── Expenses ─────────────────────────────────────────────────────────────────
// Returns { items, total, limit, offset } — paginated
export const useExpenses = (params = "", opts = {}) =>
  useAutoFetch(`/expenses${params ? `?${params}` : ""}`, opts);

export const useExpenseSummary = (year, month) =>
  useAutoFetch(`/expenses/summary/${year}/${month}`);

export const useExpenseBudget  = (year, month) =>
  useAutoFetch(`/expenses/budget/${year}/${month}`);

export const useExpenseTrend   = (months = 12) =>
  useAutoFetch(`/expenses/trend?months=${months}`);

export const useIncomeTrend    = (months = 12) =>
  useAutoFetch(`/income/trend?months=${months}`);

export async function apiAddExpense(body)          { return apiFetch("/expenses",      { method: "POST",   body: JSON.stringify(body) }); }
export async function apiUpdateExpense(id, body)   { return apiFetch(`/expenses/${id}`, { method: "PUT",    body: JSON.stringify(body) }); }
export async function apiDeleteExpense(id)         { return apiFetch(`/expenses/${id}`, { method: "DELETE" }); }
export const useRecurringExpenses = (opts = {}) => useAutoFetch("/expenses/recurring", opts);
export async function apiApplyRecurring()          { return apiFetch("/expenses/recurring/apply", { method: "POST" }); }

// Download CSV — triggers browser file save (with auth header)
export async function downloadCSV(endpoint, filename) {
  const token = _getToken();
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Income ───────────────────────────────────────────────────────────────────
// Returns { items, total, limit, offset } — paginated
export const useIncome = (params = "", opts = {}) =>
  useAutoFetch(`/income${params ? `?${params}` : ""}`, opts);
export const useIncomeSummary = (year, month) =>
  useAutoFetch(`/income/summary/${year}/${month}`);
export const useIncomeTax     = year => useAutoFetch(`/income/tax/${year}`);

export async function apiAddIncome(body)    { return apiFetch("/income",       { method: "POST",   body: JSON.stringify(body) }); }
export async function apiUpdateIncome(id, body) { return apiFetch(`/income/${id}`, { method: "PUT",    body: JSON.stringify(body) }); }
export async function apiDeleteIncome(id)  { return apiFetch(`/income/${id}`,  { method: "DELETE" }); }

// ─── Investments ──────────────────────────────────────────────────────────────
export const useInvestments = (opts = {}) => useAutoFetch("/investments", opts);
export const useRealized    = (opts = {}) => useAutoFetch("/investments/realized", opts);
export const useInvHistory  = id         => useAutoFetch(`/investments/${id}/history`);

export async function apiRefreshPrices()            { return apiFetch("/investments/refresh-prices",{ method: "POST" }); }
export async function apiPrunePortfolio()           { return apiFetch("/investments/prune",           { method: "POST" }); }
export async function apiAddInvestment(body)       { return apiFetch("/investments",           { method: "POST", body: JSON.stringify(body) }); }
export async function apiSellInvestment(id, body)  { return apiFetch(`/investments/${id}/sell`, { method: "POST", body: JSON.stringify(body) }); }
export async function apiDeleteInvestment(id)      { return apiFetch(`/investments/${id}`,      { method: "DELETE" }); }
export async function apiToggleFavorite(id)        { return apiFetch(`/investments/${id}/favorite`, { method: "POST" }); }

// ─── Balances ─────────────────────────────────────────────────────────────────
// New accounting model:
//   - emergency_fund  → only directly editable balance
//   - physical_cash / bank_savings → managed via transfer system
//   - cash_on_hand    → computed by server: (physical_cash + bank_savings) - emergency_fund
//   - crypto          → READ-ONLY, synced from portfolio.db

export const useBalances      = (opts = {}) => useAutoFetch("/balances", opts);
export const useTransferLog   = (opts = {}) => useAutoFetch("/balances/transfers", opts);

/** Set emergency fund (the ONLY directly editable balance). */
export async function apiSetEmergencyFund(value) {
  return apiFetch("/balances/emergency_fund", { method: "PUT", body: JSON.stringify({ value }) });
}

/**
 * Internal transfer between physical_cash ↔ bank_savings.
 * direction: "physical_to_bank" | "bank_to_physical"
 * Does NOT affect Total Credit.
 */
export async function apiTransferBalance(direction, amount, note = "") {
  return apiFetch("/balances/transfer", { method: "POST", body: JSON.stringify({ direction, amount, note }) });
}

/** Legacy shim — only emergency_fund is still accepted. */
export async function apiSetBalance(key, value) {
  if (key !== "emergency_fund") {
    throw new Error(`'${key}' is not directly editable. Use apiSetEmergencyFund or apiTransferBalance.`);
  }
  return apiSetEmergencyFund(value);
}

// ─── Total Credit ──────────────────────────────────────────────────────────────
// Returns this_month, all_time, all_income, all_expense, by_month (last 12 months)
export const useTotalCredit = (opts = {}) => useAutoFetch("/balances/total-credit", opts);

// ─── Portfolio Optimization ──────────────────────────────────────────────────
export const useUniverseAudit = (opts = {}) => useAutoFetch("/genetic/universe/audit", opts);

// ─── Rewards API (cross-device server persistence) ────────────────────────────
export async function apiGetRewardState()       { return apiFetch("/rewards/state"); }
export async function apiPutRewardState(state)  { return apiFetch("/rewards/state", { method: "PUT",  body: JSON.stringify(state) }); }
export async function apiPatchRewardState(patch){ return apiFetch("/rewards/state/patch", { method: "POST", body: JSON.stringify(patch) }); }
export async function apiScanReceipt(file, ocrEngine = null) {
  const form = new FormData();
  form.append("file", file);
  if (ocrEngine) form.append("ocr_engine", ocrEngine);
  const token = _getToken();
  const res = await fetch(`${API_BASE}/receipt/scan`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function apiExportReceipt(target, receipt) {
  return apiFetch("/receipt/export", { method: "POST", body: JSON.stringify({ target, receipt }) });
}

// ─── AI-powered Receipt Scanner ───────────────────────────────────────────────
// Uses Claude Vision (claude-opus-4-5) instead of legacy OCR ensemble.
// Returns same schema as apiScanReceipt plus `ai_analysis` per receipt.
export async function apiScanReceiptAI(file, ocrEngine = null) {
  const form = new FormData();
  form.append("file", file);
  if (ocrEngine) form.append("ocr_engine", ocrEngine);
  const token = _getToken();
  const res = await fetch(`${API_BASE}/receipt/scan-ai`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─── AI Behavioral Insights ───────────────────────────────────────────────────
// Calls Claude to generate personalized financial analysis for the current month.
export async function apiGetAIInsights() {
  return apiFetch("/ai/insights");
}

// Hook version — auto-fetches on mount, exposes loading/error/data/reload
export function useAIInsights() {
  return useAutoFetch("/ai/insights", {});
}

// ─── AI Provider status & control ─────────────────────────────────────────────
export async function apiGetAIStatus() {
  return apiFetch("/ai/status");
}

export async function apiSetAIProvider(provider, model = null) {
  return apiFetch("/ai/provider", {
    method: "POST",
    body: JSON.stringify(model ? { provider, model } : { provider }),
  });
}

// Hook: polls /api/ai/status on mount, exposes status + setter
export function useAIStatus() {
  const [status,  setStatus]  = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setStatus(await apiGetAIStatus()); } catch { setStatus(null); }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const setProvider = useCallback(async (provider, model = null) => {
    try {
      const res = await apiSetAIProvider(provider, model);
      setStatus(s => s ? { ...s, active: res.active, model: res.model, vision: res.vision, override: provider === "auto" ? null : provider } : s);
    } catch { /* ignore */ }
  }, []);

  return { status, loading, refresh, setProvider };
}

// ─── Stocks & Macro ───────────────────────────────────────────────────────────
export const useMacro = (opts = {}) => useAutoFetch("/stocks/macro", { intervalMs: 3600_000, ...opts });
export const useMacroAll = (opts = {}) => useAutoFetch("/stocks/macro/all", opts);
export const useStockWatchlist = (opts = {}) => useAutoFetch("/stocks/watchlist", opts);
export const useMLSummary = (opts = {}) => useAutoFetch("/ml-stocks/summary", { intervalMs: 300_000, ...opts });

// ─── Active Profile Hook ──────────────────────────────────────────────────────
export function useActiveProfile() {
  const [profile, setProfile] = useState({ active: "personal", active_type: "personal", available: [], types: {} });
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch("/profile/");
      setProfile(data);
    } catch { /* fallback */ }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const isBusiness = profile.active_type === "business" || (profile.active && profile.active.toLowerCase().includes("business"));
  return { ...profile, isBusiness, refresh };
}
