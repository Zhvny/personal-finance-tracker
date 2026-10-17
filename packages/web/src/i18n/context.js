// ─── context.js (i18n React Context & Hook) ──────────────────────────────────
import React, { createContext, useContext, useState, useEffect } from "react";
import en from "./en.js";
import id from "./id.js";

const dictionaries = { en, id };
const STORAGE_KEY = "finance_tracker_locale";

export const I18nContext = createContext({
  locale: "en",
  setLocale: () => {},
  t: (key, fallback) => fallback || key,
});

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || "en";
    } catch {
      return "en";
    }
  });

  const setLocale = (newLocale) => {
    const loc = newLocale === "id" ? "id" : "en";
    setLocaleState(loc);
    try {
      localStorage.setItem(STORAGE_KEY, loc);
    } catch {}
  };

  const t = (key, params) => {
    const dict = dictionaries[locale] || dictionaries.en;
    let val = dict[key] || dictionaries.en[key] || key;
    if (params && typeof params === "object") {
      Object.entries(params).forEach(([k, v]) => {
        val = val.replace(new RegExp(`{${k}}`, "g"), v);
      });
    }
    return val;
  };

  return React.createElement(
    I18nContext.Provider,
    { value: { locale, setLocale, t } },
    children
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      locale: "en",
      setLocale: () => {},
      t: (key, fallback) => fallback || key,
    };
  }
  return ctx;
}
