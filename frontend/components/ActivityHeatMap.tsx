"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { cn, colorFromName } from "@/lib/utils";

interface ActivityCell {
  date: string;
  count: number;
}

interface HeatMapData {
  weeks: number;
  cells: ActivityCell[];
  total: number;
  per_user: Record<string, ActivityCell[]>;
}

interface HeatMapProps {
  projectId: string;
  members: { user_id: string; name: string }[];
}

const DAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

function colorForCount(count: number, max: number): string {
  if (count === 0) return "bg-gray-100 dark:bg-slate-800";
  if (max <= 0) return "bg-indigo-200";
  const ratio = count / max;
  if (ratio < 0.25) return "bg-indigo-200 dark:bg-indigo-900/60";
  if (ratio < 0.5) return "bg-indigo-300 dark:bg-indigo-700/80";
  if (ratio < 0.75) return "bg-indigo-500 dark:bg-indigo-500";
  return "bg-indigo-700 dark:bg-indigo-400";
}

export function ActivityHeatMap({ projectId, members }: HeatMapProps) {
  const [data, setData] = useState<HeatMapData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<HeatMapData>(`/projects/${projectId}/activity?weeks=12`)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="card h-48 animate-pulse">
        <div className="h-4 w-1/4 bg-gray-200 dark:bg-slate-700 rounded mb-3" />
        <div className="h-24 bg-gray-100 dark:bg-slate-800 rounded" />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="card text-sm text-muted text-center py-6">
        Không tải được dữ liệu hoạt động.
      </div>
    );
  }

  // Group cells by week (Mon-Sun)
  const cellsByWeek: ActivityCell[][] = [];
  let current: ActivityCell[] = [];
  let weekStart: Date | null = null;

  data.cells.forEach((cell) => {
    const d = new Date(cell.date + "T00:00:00Z");
    if (!weekStart) {
      weekStart = d;
      current.push(cell);
      return;
    }
    const diff = Math.floor(
      (d.getTime() - weekStart.getTime()) / (1000 * 60 * 60 * 24)
    );
    if (diff >= 7) {
      cellsByWeek.push(current);
      current = [cell];
      weekStart = d;
    } else {
      current.push(cell);
    }
  });
  if (current.length) cellsByWeek.push(current);

  // Compute max for color scaling
  const max = Math.max(1, ...data.cells.map((c) => c.count));

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <h2 className="font-semibold dark:text-slate-100">Heat map hoạt động</h2>
          <p className="text-xs text-muted">
            12 tuần gần nhất · {data.total} lượt cập nhật
          </p>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted">
          <span>Ít</span>
          {[0, 0.2, 0.4, 0.6, 0.85].map((r) => (
            <span
              key={r}
              className={cn(
                "w-3 h-3 rounded-sm",
                colorForCount(Math.ceil(r * max), max)
              )}
            />
          ))}
          <span>Nhiều</span>
        </div>
      </div>

      <div className="overflow-x-auto scroll-thin">
        <div className="inline-block">
          <div className="flex gap-0.5 ml-8">
            {cellsByWeek.map((_, i) => (
              <div
                key={i}
                className="w-3 text-[9px] text-muted text-center"
                style={{ minWidth: 12 }}
              >
                {i % 2 === 0 ? `T${i + 1}` : ""}
              </div>
            ))}
          </div>
          <div className="flex">
            <div className="flex flex-col gap-0.5 mr-1 mt-0.5">
              {DAY_LABELS.map((d) => (
                <div
                  key={d}
                  className="h-3 text-[9px] text-muted leading-3"
                  style={{ minWidth: 24 }}
                >
                  {d}
                </div>
              ))}
            </div>
            <div className="flex gap-0.5">
              {cellsByWeek.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-0.5">
                  {Array.from({ length: 7 }).map((_, di) => {
                    const cell = week[di];
                    if (!cell) {
                      return <div key={di} className="w-3 h-3" />;
                    }
                    return (
                      <div
                        key={di}
                        title={`${cell.date}: ${cell.count} lượt`}
                        className={cn(
                          "w-3 h-3 rounded-sm heat-cell",
                          colorForCount(cell.count, max)
                        )}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {members.length > 0 && Object.keys(data.per_user).length > 0 && (
        <div className="mt-4 pt-4 border-t border-subtle">
          <h3 className="text-xs font-semibold mb-2 text-muted uppercase tracking-wide">
            Per-member (top 4 hoạt động)
          </h3>
          <div className="space-y-2">
            {members
              .filter((m) => data.per_user[m.user_id])
              .sort((a, b) => {
                const sa = data.per_user[a.user_id].reduce((s, c) => s + c.count, 0);
                const sb = data.per_user[b.user_id].reduce((s, c) => s + c.count, 0);
                return sb - sa;
              })
              .slice(0, 4)
              .map((m) => {
                const userCells = data.per_user[m.user_id];
                const total = userCells.reduce((s, c) => s + c.count, 0);
                return (
                  <div key={m.user_id} className="flex items-center gap-2 text-xs">
                    <span
                      className="w-5 h-5 rounded-full text-white text-[9px] font-semibold flex items-center justify-center"
                      style={{ background: colorFromName(m.name) }}
                    >
                      {m.name
                        .split(/\s+/)
                        .map((s) => s[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()}
                    </span>
                    <span className="font-medium dark:text-slate-200 w-32 truncate">
                      {m.name}
                    </span>
                    <div className="flex gap-0.5 flex-1">
                      {userCells.slice(-28).map((c, i) => (
                        <div
                          key={i}
                          className={cn(
                            "w-2 h-2 rounded-sm heat-cell",
                            colorForCount(c.count, max)
                          )}
                          title={`${c.date}: ${c.count}`}
                        />
                      ))}
                    </div>
                    <span className="text-muted w-10 text-right">{total}</span>
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
