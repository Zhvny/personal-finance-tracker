"use client";

import React, { createContext, useContext, useState } from "react";
import en from "./en";
import id from "./id";

type Locale = "en" | "id";
type Translations = Record<string, string>;

const dictionaries: Record<Locale, Translations> = { en, id };
const STORAGE_KEY = "finance_tracker_locale";

interface I18nContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (
    key: string,
    fallbackOrParams?: string | Record<string, string | number>,
    params?: Record<string, string | number>
  ) => string;
}

const I18nContext = createContext<I18nContextType>({
  locale: "en",
  setLocale: () => {},
  t: (key, fallbackOrParams) => (typeof fallbackOrParams === "string" ? fallbackOrParams : key),
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(STORAGE_KEY) as Locale;
        if (stored === "en" || stored === "id") {
          return stored;
        }
      } catch {
        // ignore
      }
    }
    return "en";
  });

  const setLocale = (newLocale: Locale) => {
    const loc: Locale = newLocale === "id" ? "id" : "en";
    setLocaleState(loc);
    try {
      localStorage.setItem(STORAGE_KEY, loc);
    } catch {
      // ignore
    }
  };

  const t = (
    key: string,
    fallbackOrParams?: string | Record<string, string | number>,
    params?: Record<string, string | number>
  ): string => {
    const dict = dictionaries[locale] || dictionaries.en;
    const fallback = typeof fallbackOrParams === "string" ? fallbackOrParams : key;
    const actualParams = typeof fallbackOrParams === "object" ? fallbackOrParams : params;

    let val = dict[key] || dictionaries.en[key] || fallback;
    if (actualParams && typeof actualParams === "object") {
      Object.entries(actualParams).forEach(([k, v]) => {
        val = val.replace(new RegExp(`{${k}}`, "g"), String(v));
      });
    }
    return val;
  };

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
