"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { API_BASE_URL, api, setTokens } from "@/lib/api";
import type { AuthTokens } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [email, setEmail] = useState("an.leader@example.com");
  const [password, setPassword] = useState("password123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ssoEnabled, setSsoEnabled] = useState(false);

  // Probe whether SSO is enabled so we can show / hide the button.
  // Uses a tiny unauthenticated endpoint we expose for the SPA.
  useState(() => {
    if (typeof window === "undefined") return;
    fetch(`${API_BASE_URL}/api/saml/status`, { credentials: "omit" })
      .then((r) => (r.ok ? r.json() : { enabled: false }))
      .then((d) => setSsoEnabled(!!d.enabled))
      .catch(() => setSsoEnabled(false));
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.post<AuthTokens>("/auth/login", { email, password });
      setTokens(res.data.access_token, res.data.refresh_token);
      router.push("/projects");
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || t("auth.loginError")
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6 bg-gray-50 dark:bg-slate-950 transition-colors relative">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("auth.login")}</CardTitle>
          <CardDescription>
            {t("auth.welcomeBack")} {t("auth.welcomeBackDesc")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="email">{t("auth.email")}</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="password">{t("auth.password")}</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && (
              <div className="rounded-md bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm p-3">
                {error}
              </div>
            )}
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? t("auth.loggingIn") : t("auth.login")}
            </Button>
          </form>

          {ssoEnabled && (
            <>
              <div className="my-4 flex items-center gap-2 text-xs text-faint">
                <span className="flex-1 h-px bg-subtle" />
                <span>{t("common.or")}</span>
                <span className="flex-1 h-px bg-subtle" />
              </div>
              <a
                href={`${API_BASE_URL}/api/saml/login?relay_state=/dashboard`}
                className="block text-center btn-secondary w-full"
              >
                🔐 {t("auth.sso")}
              </a>
            </>
          )}

          <p className="text-sm text-muted mt-4 text-center">
            {t("auth.noAccount")}{" "}
            <Link href="/register" className="text-primary hover:underline">
              {t("auth.registerNow")}
            </Link>
          </p>
          <div className="mt-6 border-t border-subtle pt-4 text-xs text-muted">
            <p className="font-medium mb-1">{t("auth.demoAccounts")}</p>
            <p>an.leader@example.com · alice@example.com · instructor@example.com</p>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
