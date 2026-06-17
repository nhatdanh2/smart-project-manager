import type { Metadata } from "next";
import { Toaster } from "sonner";

import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { I18nProvider } from "@/components/I18nProvider";
import { ObservabilityProvider } from "@/components/ObservabilityProvider";

export const metadata: Metadata = {
  title: "Smart Student Project Manager",
  description: "Ai đang gánh team? — quản lý đồ án nhóm với AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <ObservabilityProvider>
          <ThemeProvider>
            <I18nProvider>
              {children}
              <Toaster
                position="top-right"
                richColors
                closeButton
                toastOptions={{ duration: 4000 }}
              />
            </I18nProvider>
          </ThemeProvider>
        </ObservabilityProvider>
      </body>
    </html>
  );
}
