"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api, getAccessToken } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api";
import type { SearchResult, SearchHit } from "@/lib/types";


interface Props {
  projectId: string;
}

const STATUSES = [
  { value: "", label: "Tất cả" },
  { value: "todo", label: "To do" },
  { value: "in_progress", label: "Doing" },
  { value: "review", label: "Review" },
  { value: "done", label: "Done" },
];

const KINDS: { value: "tasks" | "meetings"; label: string }[] = [
  { value: "tasks", label: "Tasks" },
  { value: "meetings", label: "Meetings" },
];

/**
 * Debounced search bar with results dropdown.
 *
 * Uses the new ``/api/projects/:id/search`` endpoint.  Empty query
 * shows the most recent items as a "recents" list.
 */
export function SearchBar({ projectId }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"tasks" | "meetings">("tasks");
  const [status, setStatus] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounce 250ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void runSearch(query);
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, kind, status]);

  // Close on outside click
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function runSearch(q: string) {
    setLoading(true);
    try {
      const url = new URL(`${API_BASE_URL}/api/projects/${projectId}/search`);
      url.searchParams.set("q", q);
      url.searchParams.set("index", kind);
      if (status) url.searchParams.set("status", status);
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` },
      });
      if (!res.ok) {
        setResult({ hits: [], backend: "error" });
        return;
      }
      const json = (await res.json()) as SearchResult;
      setResult(json);
    } finally {
      setLoading(false);
    }
  }

  const hits = useMemo<SearchHit[]>(() => result?.hits ?? [], [result]);

  function go(hit: SearchHit) {
    setOpen(false);
    if (kind === "tasks") {
      router.push(`/projects/${projectId}/kanban?task=${hit.id}`);
    } else {
      router.push(`/projects/${projectId}/meeting?m=${hit.id}`);
    }
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder={`Tìm trong ${kind === "tasks" ? "tasks" : "meetings"}…`}
            className="w-full pl-3 pr-9 py-1.5 text-sm border border-subtle rounded-md bg-white dark:bg-slate-900 dark:text-slate-100"
          />
          {loading && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted">
              ⟳
            </span>
          )}
        </div>
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as "tasks" | "meetings")}
          className="text-sm border border-subtle rounded-md bg-white dark:bg-slate-900 dark:text-slate-100 py-1.5"
        >
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        {kind === "tasks" && (
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="text-sm border border-subtle rounded-md bg-white dark:bg-slate-900 dark:text-slate-100 py-1.5"
          >
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {open && hits.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-30 left-0 right-0 mt-1 max-h-80 overflow-y-auto rounded-md border border-subtle bg-white dark:bg-slate-900 shadow-lg"
        >
          {hits.map((h) => (
            <li
              key={h.id}
              onClick={() => go(h)}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-800 flex items-center gap-2"
            >
              <span className="flex-1 truncate">
                {highlight(h.title || h.id, query)}
              </span>
              {h.status && (
                <span className="text-xs text-muted">{String(h.status)}</span>
              )}
            </li>
          ))}
          {result?.backend && (
            <li className="px-3 py-1 text-[10px] text-muted border-t border-subtle">
              backend: {result.backend}
              {result.estimatedTotalHits != null &&
                ` · ${result.estimatedTotalHits} kết quả`}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function highlight(text: string, q: string): React.ReactNode {
  if (!q) return text;
  const re = new RegExp(`(${escapeRegExp(q)})`, "ig");
  const parts = text.split(re);
  return parts.map((p, i) =>
    re.test(p) ? (
      <mark key={i} className="bg-yellow-200 dark:bg-yellow-800/60 rounded px-0.5">
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
