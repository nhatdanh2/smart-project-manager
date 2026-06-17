"use client";

import { Globe } from "lucide-react";

import { useI18n } from "@/components/I18nProvider";

export function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  return (
    <div className="flex items-center gap-1">
      <Globe className="w-3.5 h-3.5 text-muted" />
      <button
        onClick={() => setLang("vi")}
        className={`text-xs px-1.5 py-0.5 rounded ${
          lang === "vi"
            ? "bg-primary text-white"
            : "text-muted hover:text-body"
        }`}
      >
        VI
      </button>
      <button
        onClick={() => setLang("en")}
        className={`text-xs px-1.5 py-0.5 rounded ${
          lang === "en"
            ? "bg-primary text-white"
            : "text-muted hover:text-body"
        }`}
      >
        EN
      </button>
    </div>
  );
}
