"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api, getAccessToken, setTokens } from "@/lib/api";
import { clearUserContext, setUserContext } from "@/lib/observability";
import type { User } from "@/lib/types";

export function useAuth(redirectIfUnauth = true) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      clearUserContext();
      if (redirectIfUnauth) router.push("/login");
      return;
    }
    api
      .get<User>("/auth/me")
      .then((res) => {
        setUser(res.data);
        setUserContext({ id: res.data.id, name: res.data.name, email: res.data.email });
      })
      .catch(() => {
        setTokens(null, null);
        clearUserContext();
        if (redirectIfUnauth) router.push("/login");
      })
      .finally(() => setLoading(false));
  }, [redirectIfUnauth, router]);

  return { user, loading, setUser };
}
