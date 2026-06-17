"use client";

import Link from "next/link";

import { useI18n } from "@/components/I18nProvider";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export default function HomePage() {
  const { t } = useI18n();
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-indigo-50 to-white dark:from-slate-950 dark:to-slate-900 p-8 transition-colors">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>
      <div className="max-w-2xl w-full text-center">
        <h1 className="text-5xl font-bold text-gray-900 dark:text-slate-100 mb-4">
          {t("home.title")}
        </h1>
        <p className="text-lg text-gray-600 dark:text-slate-300 mb-2">
          {t("home.tagline")}
        </p>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-10">
          {t("home.description")}
        </p>
        <div className="flex gap-3 justify-center">
          <Link href="/login" className="btn-primary">
            {t("home.login")}
          </Link>
          <Link href="/register" className="btn-secondary">
            {t("home.register")}
          </Link>
        </div>
      </div>
    </main>
  );
}
