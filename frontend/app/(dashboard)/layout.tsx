"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { setTokens } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Skeleton } from "@/components/Skeletons";
import { ThemeToggle } from "@/components/ThemeToggle";
import { NotificationBell } from "@/components/NotificationBell";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useI18n } from "@/components/I18nProvider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth(true);
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-3">
        <Skeleton className="h-3 w-3 rounded-full" />
        <div className="text-gray-500 dark:text-slate-400">{t("common.loading")}</div>
      </div>
    );
  }
  if (!user) return null;

  const navItems = [
    { href: "/projects", label: t("nav.projects") },
    ...(user.role === "instructor"
      ? [{ href: "/instructor", label: t("nav.instructor") }]
      : []),
  ];

  function logout() {
    setTokens(null, null);
    router.push("/login");
  }

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-60 bg-white dark:bg-slate-900 border-r border-gray-200 dark:border-slate-800 flex-col">
        <SidebarContent
          userName={user.name}
          userEmail={user.email}
          navItems={navItems}
          pathname={pathname}
          onLogout={logout}
        />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-800 z-30 flex items-center px-4 gap-3">
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 -ml-2 text-gray-700 dark:text-slate-300"
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        <Link href="/projects" className="font-bold text-primary">
          {t("common.appName").split(" ").slice(-2).join(" ")}
        </Link>
        <div className="ml-auto flex items-center gap-1">
          <NotificationBell />
          <ThemeToggle />
          <LanguageSwitcher />
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/40"
          onClick={() => setMobileOpen(false)}
        >
          <div
            className="absolute left-0 top-0 bottom-0 w-64 bg-white dark:bg-slate-900 slide-in flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-slate-800">
              <span className="font-bold text-primary">{t("common.appName").split(" ").slice(-2).join(" ")}</span>
              <button
                onClick={() => setMobileOpen(false)}
                className="text-gray-500 dark:text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <SidebarContent
                userName={user.name}
                userEmail={user.email}
                navItems={navItems}
                pathname={pathname}
                onLogout={logout}
                onNavigate={() => setMobileOpen(false)}
              />
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 overflow-y-auto md:pt-0 pt-14">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </div>
  );
}

function SidebarContent({
  userName,
  userEmail,
  navItems,
  pathname,
  onLogout,
  onNavigate,
}: {
  userName: string;
  userEmail: string;
  navItems: { href: string; label: string }[];
  pathname: string | null;
  onLogout: () => void;
  onNavigate?: () => void;
}) {
  const { t } = useI18n();
  return (
    <>
      <div className="p-5 border-b border-gray-200 dark:border-slate-800">
        <Link
          href="/projects"
          className="block"
          onClick={() => onNavigate?.()}
        >
          <div className="text-lg font-bold text-primary">SPM</div>
          <div className="text-xs text-gray-500 dark:text-slate-400">
            {t("common.appName")}
          </div>
        </Link>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => onNavigate?.()}
            className={cn(
              "block px-3 py-2 rounded-md text-sm",
              pathname === item.href || pathname?.startsWith(item.href + "/")
                ? "bg-indigo-50 text-primary font-medium dark:bg-indigo-900/30 dark:text-indigo-300"
                : "text-gray-700 hover:bg-gray-50 dark:text-slate-300 dark:hover:bg-slate-800"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-200 dark:border-slate-800">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-sm font-medium dark:text-slate-100">{userName}</div>
            <div className="text-xs text-gray-500 dark:text-slate-400">{userEmail}</div>
          </div>
          <div className="hidden md:flex items-center gap-1">
            <NotificationBell />
            <ThemeToggle />
          </div>
        </div>
        <div className="flex items-center justify-between mb-2">
          <LanguageSwitcher />
          <button onClick={onLogout} className="btn-ghost w-2/3 text-sm">
            {t("common.logout")}
          </button>
        </div>
      </div>
    </>
  );
}
