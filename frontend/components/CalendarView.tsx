"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import type { Task } from "@/lib/types";
import { colorFromName, formatDate } from "@/lib/utils";

interface CalendarViewProps {
  tasks: Task[];
  onTaskClick?: (task: Task) => void;
}

const MONTH_NAMES = [
  "Tháng 1",
  "Tháng 2",
  "Tháng 3",
  "Tháng 4",
  "Tháng 5",
  "Tháng 6",
  "Tháng 7",
  "Tháng 8",
  "Tháng 9",
  "Tháng 10",
  "Tháng 11",
  "Tháng 12",
];

const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

interface Cell {
  date: Date;
  inMonth: boolean;
  tasks: Task[];
}

function buildMonthGrid(year: number, month: number, tasks: Task[]): Cell[] {
  const first = new Date(year, month, 1);
  // Monday-based: 0=Mon, 6=Sun
  const startOffset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - startOffset);
  const cells: Cell[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const inMonth = d.getMonth() === month;
    const dayTasks = tasks.filter((t) => {
      if (!t.deadline) return false;
      const dl = new Date(t.deadline);
      return (
        dl.getFullYear() === d.getFullYear() &&
        dl.getMonth() === d.getMonth() &&
        dl.getDate() === d.getDate()
      );
    });
    cells.push({ date: d, inMonth, tasks: dayTasks });
  }
  return cells;
}

export function CalendarView({ tasks, onTaskClick }: CalendarViewProps) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const cells = useMemo(() => buildMonthGrid(year, month, tasks), [year, month, tasks]);

  function prev() {
    if (month === 0) {
      setMonth(11);
      setYear((y) => y - 1);
    } else {
      setMonth((m) => m - 1);
    }
  }
  function next() {
    if (month === 11) {
      setMonth(0);
      setYear((y) => y + 1);
    } else {
      setMonth((m) => m + 1);
    }
  }
  function goToday() {
    setYear(today.getFullYear());
    setMonth(today.getMonth());
  }

  const isToday = (d: Date) =>
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();

  // Quick stats
  const totalThisMonth = cells
    .filter((c) => c.inMonth)
    .reduce((s, c) => s + c.tasks.length, 0);
  const overdueCount = tasks.filter(
    (t) => t.deadline && new Date(t.deadline) < today && t.status !== "done"
  ).length;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <button onClick={prev} className="btn-ghost p-2" aria-label="Tháng trước">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <h2 className="font-semibold text-lg dark:text-slate-100 min-w-[160px] text-center">
            {MONTH_NAMES[month]} {year}
          </h2>
          <button onClick={next} className="btn-ghost p-2" aria-label="Tháng sau">
            <ChevronRight className="w-4 h-4" />
          </button>
          <button onClick={goToday} className="btn-secondary text-xs ml-2">
            Hôm nay
          </button>
        </div>
        <div className="text-xs text-muted flex gap-3">
          <span>
            <span className="font-medium text-heading">{totalThisMonth}</span> deadline tháng này
          </span>
          <span>
            <span className="font-medium text-red-600 dark:text-red-400">{overdueCount}</span>{" "}
            quá hạn
          </span>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px bg-gray-200 dark:bg-slate-700 rounded overflow-hidden">
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="bg-gray-50 dark:bg-slate-800 text-center text-xs font-semibold text-muted py-2"
          >
            {d}
          </div>
        ))}
        {cells.map((c, i) => (
          <div
            key={i}
            className={`min-h-[90px] sm:min-h-[110px] p-1.5 ${
              c.inMonth
                ? "bg-white dark:bg-slate-900"
                : "bg-gray-50 dark:bg-slate-800/40 text-faint"
            } ${isToday(c.date) ? "ring-2 ring-primary ring-inset" : ""}`}
          >
            <div
              className={`text-xs mb-1 ${
                isToday(c.date)
                  ? "font-bold text-primary"
                  : c.inMonth
                  ? "text-body"
                  : "text-faint"
              }`}
            >
              {c.date.getDate()}
            </div>
            <div className="space-y-1">
              {c.tasks.slice(0, 3).map((t) => (
                <button
                  key={t.id}
                  onClick={() => onTaskClick?.(t)}
                  className={`w-full text-left text-[10px] px-1.5 py-0.5 rounded truncate cursor-pointer hover:opacity-80 ${
                    t.status === "done"
                      ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                      : t.is_overdue
                      ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                      : t.is_critical
                      ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300"
                      : "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                  }`}
                  title={`${t.title}${t.assignee_name ? ` · ${t.assignee_name}` : ""}`}
                >
                  {t.title}
                </button>
              ))}
              {c.tasks.length > 3 && (
                <div className="text-[10px] text-muted px-1">
                  +{c.tasks.length - 3} nữa
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3 mt-3 text-xs text-muted">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-indigo-100 dark:bg-indigo-900/40" />
          Deadline
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-red-100 dark:bg-red-900/40" />
          Quá hạn
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-orange-100 dark:bg-orange-900/40" />
          Critical
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-green-100 dark:bg-green-900/40" />
          Done
        </div>
      </div>
    </div>
  );
}
