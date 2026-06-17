"use client";

import { useMemo } from "react";

import type { Task } from "@/lib/types";
import { colorFromName } from "@/lib/utils";

interface DependencyGraphProps {
  tasks: Task[];
  onTaskClick?: (taskId: string) => void;
}

interface Layout {
  x: number;
  y: number;
  level: number;
}

const NODE_W = 140;
const NODE_H = 48;
const H_GAP = 30;
const V_GAP = 50;
const PADDING = 20;

/**
 * Simple topological layout: assign each node a "level" = max(levels of
 * parents) + 1.  We render left-to-right by level, distributing siblings
 * vertically so they don't overlap.
 */
function layoutTasks(tasks: Task[]): Record<string, Layout> {
  const byId: Record<string, Task> = {};
  for (const t of tasks) byId[t.id] = t;

  const level: Record<string, number> = {};
  const visiting = new Set<string>();

  function compute(id: string): number {
    if (level[id] !== undefined) return level[id];
    if (visiting.has(id)) {
      // cycle - just put on its own level
      return (level[id] = 0);
    }
    visiting.add(id);
    const t = byId[id];
    if (!t) return 0;
    const deps = (t.depends_on || []).filter((d) => byId[d]);
    if (deps.length === 0) {
      level[id] = 0;
    } else {
      level[id] = 1 + Math.max(...deps.map(compute));
    }
    visiting.delete(id);
    return level[id];
  }

  for (const t of tasks) compute(t.id);

  // Group by level
  const byLevel: Record<number, string[]> = {};
  for (const t of tasks) {
    const lv = level[t.id] ?? 0;
    (byLevel[lv] = byLevel[lv] || []).push(t.id);
  }

  // Compute x/y for each
  const coords: Record<string, Layout> = {};
  const levels = Object.keys(byLevel)
    .map(Number)
    .sort((a, b) => a - b);
  for (const lv of levels) {
    const ids = byLevel[lv];
    ids.forEach((id, i) => {
      coords[id] = {
        x: PADDING + lv * (NODE_W + H_GAP),
        y: PADDING + i * (NODE_H + V_GAP),
        level: lv,
      };
    });
  }
  return coords;
}

export function DependencyGraph({ tasks, onTaskClick }: DependencyGraphProps) {
  const coords = useMemo(() => layoutTasks(tasks), [tasks]);

  if (tasks.length === 0) {
    return (
      <div className="text-sm text-muted text-center py-6">
        Chưa có task nào.
      </div>
    );
  }

  const maxLevel = Math.max(...Object.values(coords).map((c) => c.level), 0);
  const width = PADDING * 2 + (maxLevel + 1) * NODE_W + maxLevel * H_GAP;
  const height =
    PADDING * 2 +
    Math.max(...Object.values(coords).map((c) => c.y), 0) +
    NODE_H +
    20;

  return (
    <div className="overflow-auto scroll-thin">
      <svg width={width} height={height} className="font-sans">
        <defs>
          <marker
            id="dep-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L0,6 L6,3 z" className="fill-gray-400 dark:fill-slate-500" />
          </marker>
        </defs>

        {/* Edges */}
        {tasks.flatMap((t) =>
          (t.depends_on || []).map((depId) => {
            const from = coords[depId];
            const to = coords[t.id];
            if (!from || !to) return null;
            const x1 = from.x + NODE_W;
            const y1 = from.y + NODE_H / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            return (
              <path
                key={`${depId}-${t.id}`}
                d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2 - 4} ${y2}`}
                fill="none"
                stroke={t.is_critical ? "#EF4444" : "currentColor"}
                className={t.is_critical ? "" : "text-gray-400 dark:text-slate-500"}
                strokeWidth={t.is_critical ? 2 : 1.5}
                markerEnd="url(#dep-arrow)"
                opacity={0.6}
              />
            );
          })
        )}

        {/* Nodes */}
        {tasks.map((t) => {
          const c = coords[t.id];
          if (!c) return null;
          const color = t.is_critical
            ? "#EF4444"
            : t.status === "done"
            ? "#10B981"
            : colorFromName(t.assignee_name || "?");
          return (
            <g
              key={t.id}
              transform={`translate(${c.x}, ${c.y})`}
              onClick={() => onTaskClick?.(t.id)}
              className="cursor-pointer"
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={6}
                className="fill-white dark:fill-slate-800"
                stroke={color}
                strokeWidth={t.is_critical ? 2.5 : 1.5}
              />
              <rect
                x={0}
                y={0}
                width={4}
                height={NODE_H}
                rx={2}
                fill={color}
              />
              <text
                x={10}
                y={18}
                className="text-[10px] fill-gray-500 dark:fill-slate-400 uppercase"
              >
                D{c.level}
              </text>
              <text
                x={10}
                y={34}
                className="text-[11px] fill-gray-900 dark:fill-slate-100 font-medium"
              >
                {t.title.length > 18 ? t.title.slice(0, 18) + "…" : t.title}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
