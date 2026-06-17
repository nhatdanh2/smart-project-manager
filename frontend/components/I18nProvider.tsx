"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { dicts, type Lang, t as translate } from "@/lib/i18n";

const STORAGE_KEY = "spm_lang";

interface I18nContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (path: string, ...args: any[]) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getInitialLang(): Lang {
  if (typeof window === "undefined") return "vi";
  const stored = localStorage.getItem(STORAGE_KEY) as Lang | null;
  if (stored === "vi" || stored === "en") return stored;
  // Default to browser language
  const browser = navigator.language?.toLowerCase() ?? "";
  return browser.startsWith("en") ? "en" : "vi";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("vi");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setLangState(getInitialLang());
    setMounted(true);
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // ignore
    }
  }, []);

  const tFn = useCallback(
    (path: string, ...args: any[]) => translate(lang, path, ...args),
    [lang]
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t: tFn }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      lang: "vi" as Lang,
      setLang: () => {},
      t: (p: string, ...args: any[]) => {
        // Fallback for SSR / outside-provider: lookup directly in 'vi' dict
        const fn = translate as any;
        return fn("vi", p, ...args);
      },
    };
  }
  return ctx;
}
