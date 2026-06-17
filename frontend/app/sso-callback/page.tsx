"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { API_BASE_URL, setTokens } from "@/lib/api";


/**
 * SAML SSO callback page.
 *
 * The IdP redirects the browser back to ``/?saml_jwt=…`` after a
 * successful assertion.  We immediately exchange the one-shot
 * token for the normal access/refresh pair, persist them, and
 * push the user to the dashboard.
 */
function SAMLCallbackInner() {
  const router = useRouter();
  const search = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const samlJwt = search?.get("saml_jwt");
    if (!samlJwt) {
      setError("Missing saml_jwt in the URL — did the IdP redirect correctly?");
      return;
    }
    void (async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/saml/exchange?saml_jwt=${encodeURIComponent(samlJwt)}`,
          { method: "POST" }
        );
        if (!res.ok) {
          throw new Error(`SAML exchange failed: ${res.status} ${await res.text()}`);
        }
        const json = await res.json();
        setTokens(json.access_token, json.refresh_token);
        router.replace("/dashboard");
      } catch (err: any) {
        setError(err?.message || "SSO exchange failed");
      }
    })();
  }, [router, search]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold text-red-600 mb-2">SSO failed</h1>
          <p className="text-sm text-muted mb-4">{error}</p>
          <a href="/login" className="btn-primary">Back to login</a>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-sm text-muted">Signing you in…</p>
    </div>
  );
}

export default function SAMLCallbackPage() {
  // ``useSearchParams`` requires a Suspense boundary during static
  // generation — we render a tiny placeholder while it resolves.
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <p className="text-sm text-muted">Signing you in…</p>
        </div>
      }
    >
      <SAMLCallbackInner />
    </Suspense>
  );
}
