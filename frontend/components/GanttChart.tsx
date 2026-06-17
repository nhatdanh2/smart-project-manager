"use client";

import { useEffect, useMemo, useState } from "react";

import type { Task } from "@/lib/types";
import { colorFromName } from "@/lib/utils";

interface GanttChartProps {
  tasks: Task[];
  onTaskClick?: (task: Task) => void;
}

const ROW_HEIGHT = 36;
const HEADER_HEIGHT = 36;
const DAY_WIDTH = 24;
const MIN_WIDTH = 600;
const PADDING = 16;

export function GanttChart({ tasks, onTaskClick }: GanttChartProps) {
  const [hoveredTask, setHoveredTask] = useState<string | null>(null);

  // Compute layout based on CPM data.  We need at least early_start /
  // early_finish; if missing we fall back to story_points.
  const layout = useMemo(() => {
    const hasCpm = tasks.some(
      (t) => t.early_start !== null && t.early_start !== undefined
    );

    let projectEnd = 0;
    const normalised = tasks.map((t) => {
      const es = t.early_start ?? 0;
      const dur = t.story_points;
      const ef = t.early_finish ?? es + dur;
      if (ef > projectEnd) projectEnd = ef;
      return {
        id: t.id,
        title: t.title,
        assignee: t.assignee_name,
        es,
        ef,
        dur,
        status: t.status,
        isCritical: t.is_critical,
        slack: t.slack ?? 0,
        dependsOn: t.depends_on ?? [],
      };
    });

    // Build lookup: task id -> index
    const indexById = new Map(normalised.map((t, i) => [t.id, i]));
    return { normalised, hasCpm, projectEnd, indexById };
  }, [tasks]);

  if (layout.normalised.length === 0) {
    return (
      <div className="card text-sm text-muted text-center py-12">
        Chưa có task nào. Hãy tạo task để xem Gantt.
      </div>
    );
  }

  const totalDays = Math.max(layout.projectEnd, 1);
  const chartWidth = Math.max(MIN_WIDTH, totalDays * DAY_WIDTH + PADDING * 2);

  return (
    <div className="card overflow-x-auto scroll-thin">
      {!layout.hasCpm && (
        <div className="text-xs text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded p-2 mb-3">
          ⚠ CPM chưa được tính. Đang hiển thị layout dựa trên thời lượng task. Nhấn "Tính
          CPM" trong Kanban để có critical path chính xác.
        </div>
      )}
      <div className="min-w-fit">
        <svg
          width={chartWidth}
          height={HEADER_HEIGHT + tasks.length * ROW_HEIGHT + 20}
          className="font-sans"
        >
          {/* Day grid */}
          {Array.from({ length: totalDays + 1 }).map((_, i) => (
            <g key={`grid-${i}`}>
              <line
                x1={PADDING + i * DAY_WIDTH}
                y1={HEADER_HEIGHT}
                x2={PADDING + i * DAY_WIDTH}
                y2={HEADER_HEIGHT + tasks.length * ROW_HEIGHT}
                stroke="currentColor"
                className="text-gray-200 dark:text-slate-700"
                strokeDasharray={i % 5 === 0 ? undefined : "2,3"}
              />
              {i % 5 === 0 && (
                <text
                  x={PADDING + i * DAY_WIDTH}
                  y={HEADER_HEIGHT - 10}
                  textAnchor="middle"
                  className="text-[10px] fill-gray-500 dark:fill-slate-400"
                >
                  D{i}
                </text>
              )}
            </g>
          ))}

          {/* Task rows + bars */}
          {layout.normalised.map((t, i) => {
            const y = HEADER_HEIGHT + i * ROW_HEIGHT;
            const x = PADDING + t.es * DAY_WIDTH;
            const w = Math.max(DAY_WIDTH, t.dur * DAY_WIDTH);
            const color = t.isCritical
              ? "#EF4444"
              : t.status === "done"
              ? "#10B981"
              : colorFromName(t.assignee || "?");
            const hovered = hoveredTask === t.id;
            return (
              <g
                key={t.id}
                onMouseEnter={() => setHoveredTask(t.id)}
                onMouseLeave={() => setHoveredTask(null)}
                onClick={() => onTaskClick?.(tasks[i])}
                className="cursor-pointer"
              >
                {/* Row background + critical highlight stripe */}
                <rect
                  x={0}
                  y={y}
                  width={chartWidth}
                  height={ROW_HEIGHT}
                  className={i % 2 === 0 ? "fill-white dark:fill-slate-900" : "fill-gray-50 dark:fill-slate-800/40"}
                />
                {t.isCritical && (
                  <rect
                    x={0}
                    y={y}
                    width={4}
                    height={ROW_HEIGHT}
                    className="fill-red-500"
                  />
                )}
                {/* Task label */}
                <text
                  x={PADDING - 8}
                  y={y + ROW_HEIGHT / 2 + 3}
                  textAnchor="end"
                  className={`text-[11px] font-medium ${
                    t.isCritical
                      ? "fill-red-600 dark:fill-red-400 font-semibold"
                      : "fill-gray-700 dark:fill-slate-200"
                  }`}
                >
                  {t.title.length > 22 ? t.title.slice(0, 22) + "…" : t.title}
                </text>
                {/* Bar */}
                <rect
                  x={x}
                  y={y + 6}
                  width={w}
                  height={ROW_HEIGHT - 12}
                  rx={4}
                  fill={color}
                  opacity={hovered ? 1 : 0.85}
                  stroke={t.isCritical ? "#991B1B" : "none"}
                  strokeWidth={t.isCritical ? 2 : 0}
                  className="gantt-bar"
                />
                {/* Bar label */}
                {w > 60 && (
                  <text
                    x={x + 6}
                    y={y + ROW_HEIGHT / 2 + 3}
                    className="text-[10px] fill-white font-medium pointer-events-none"
                  >
                    {t.dur}d {t.isCritical && "🔥"}
                  </text>
                )}
                {/* Slack hint */}
                {t.slack > 0 && !t.isCritical && (
                  <text
                    x={x + w + 4}
                    y={y + ROW_HEIGHT / 2 + 3}
                    className="text-[10px] fill-gray-400 dark:fill-slate-500"
                  >
                    +{t.slack}d
                  </text>
                )}
              </g>
            );
          })}

          {/* Dependency arrows */}
          {layout.normalised.flatMap((t, i) =>
            t.dependsOn
              .map((depId) => {
                const depIdx = layout.indexById.get(depId);
                if (depIdx === undefined) return null;
                const from = layout.normalised[depIdx];
                const x1 = PADDING + from.ef * DAY_WIDTH;
                const y1 = HEADER_HEIGHT + depIdx * ROW_HEIGHT + ROW_HEIGHT / 2;
                const x2 = PADDING + t.es * DAY_WIDTH;
                const y2 = HEADER_HEIGHT + i * ROW_HEIGHT + ROW_HEIGHT / 2;
                const midX = (x1 + x2) / 2;
                const path = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${
                  x2 - 4
                } ${y2} L ${x2} ${y2}`;
                return (
                  <g key={`dep-${t.id}-${depId}`} className="pointer-events-none">
                    <path
                      d={path}
                      fill="none"
                      stroke="#9CA3AF"
                      strokeWidth={1.5}
                      markerEnd="url(#arrowhead)"
                    />
                  </g>
                );
              })
              .filter(Boolean)
          )}

          <defs>
            <marker
              id="arrowhead"
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <path d="M 0 0 L 6 3 L 0 6 z" fill="#9CA3AF" />
            </marker>
          </defs>
        </svg>
      </div>

      <div className="flex items-center gap-4 mt-3 text-xs text-body flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-red-500" /> Critical path
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-green-500" /> Done
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-indigo-400" /> Đang làm
        </div>
        <div className="ml-auto text-muted">
          {layout.normalised.length} task · {totalDays} ngày (theo CPM)
        </div>
      </div>
    </div>
  );
}
