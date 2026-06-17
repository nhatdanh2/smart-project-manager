"use client";

import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckSquare, Square, Trash2, X } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { KANBAN_COLUMNS, type Task, type TaskStatus, type Project, type Member } from "@/lib/types";
import { useI18n } from "@/components/I18nProvider";
import { colorFromName, formatDate, initials } from "@/lib/utils";

const STATUSES: TaskStatus[] = ["todo", "in_progress", "review", "done"];

interface KanbanBoardProps {
  projectId: string;
  project: Project | null;
  initialTasks: Task[];
  onChange: (tasks: Task[]) => void;
  onTaskClick?: (task: Task) => void;
  currentUserId?: string;
}

export function KanbanBoard({
  projectId,
  project,
  initialTasks,
  onChange,
  onTaskClick,
  currentUserId,
}: KanbanBoardProps) {
  const { t } = useI18n();
  const [tasks, setTasks] = useState<Task[]>(initialTasks);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    setTasks(initialTasks);
  }, [initialTasks]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const members: Member[] = project?.members || [];

  function applyChange(updater: (prev: Task[]) => Task[]) {
    setTasks((prev) => {
      const next = updater(prev);
      onChange(next);
      return next;
    });
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function clearSelection() {
    setSelected(new Set());
  }

  async function bulkStatusChange(status: TaskStatus) {
    if (selected.size === 0) return;
    setBulkBusy(true);
    try {
      const res = await api.post<{ updated: number; total: number }>(
        `/projects/${projectId}/tasks/bulk`,
        {
          task_ids: Array.from(selected),
          status,
        }
      );
      toast.success(
        t("kanban.bulkMovedToast", res.data.updated, res.data.total,
          KANBAN_COLUMNS.find((c) => c.id === status)?.title || status)
      );
      clearSelection();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.bulkError"));
    } finally {
      setBulkBusy(false);
    }
  }

  async function bulkAssignee(assigneeId: string | null) {
    if (selected.size === 0) return;
    setBulkBusy(true);
    try {
      await api.post(`/projects/${projectId}/tasks/bulk`, {
        task_ids: Array.from(selected),
        assignee_id: assigneeId,
      });
      const assigneeName = assigneeId
        ? members.find((m) => m.user_id === assigneeId)?.name
        : t("kanban.unassignedBulk");
      toast.success(t("kanban.bulkAssignedToast", selected.size, assigneeName || "—"));
      clearSelection();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.bulkError"));
    } finally {
      setBulkBusy(false);
    }
  }

  async function bulkDelete() {
    if (selected.size === 0) return;
    if (!confirm(t("kanban.bulkDeleteConfirm", selected.size))) return;
    setBulkBusy(true);
    try {
      const res = await api.post<{ deleted: number }>(
        `/projects/${projectId}/tasks/bulk`,
        {
          task_ids: Array.from(selected),
          delete: true,
        }
      );
      toast.success(t("kanban.bulkDeletedToast", res.data.deleted));
      clearSelection();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.deleteError"));
    } finally {
      setBulkBusy(false);
    }
  }

  function onDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
  }

  async function onDragEnd(e: DragEndEvent) {
    setActiveId(null);
    const taskId = String(e.active.id);
    const overId = e.over?.id ? String(e.over.id) : null;
    if (!overId) return;

    let newStatus: TaskStatus | null = null;
    let position: number | null = null;

    if ((STATUSES as string[]).includes(overId)) {
      newStatus = overId as TaskStatus;
    } else {
      const overTask = tasks.find((tk) => tk.id === overId);
      if (!overTask) return;
      newStatus = overTask.status;
      const sameCol = tasks.filter((tk) => tk.status === newStatus);
      position = sameCol.findIndex((tk) => tk.id === overId);
    }

    const original = tasks.find((tk) => tk.id === taskId);
    if (!original || original.status === newStatus) {
      if (original && newStatus && position !== null) {
        const sameCol = tasks
          .filter((tk) => tk.status === newStatus)
          .sort((a, b) => a.priority - b.priority);
        const fromIdx = sameCol.findIndex((tk) => tk.id === taskId);
        if (fromIdx === position) return;
        const reordered = [...sameCol];
        const [moved] = reordered.splice(fromIdx, 1);
        reordered.splice(position, 0, moved);
        const newPriorities = new Map(
          reordered.map((tk, i) => [tk.id, (i + 1) * 10])
        );
        applyChange((prev) =>
          prev.map((tk) =>
            newPriorities.has(tk.id) ? { ...tk, priority: newPriorities.get(tk.id)! } : tk
          )
        );
        try {
          await api.put(`/tasks/${taskId}/move`, {
            status: newStatus,
            position,
          });
        } catch (err: any) {
          toast.error(err?.response?.data?.detail || t("kanban.reorderError"));
          onChange(initialTasks);
        }
      }
      return;
    }

    applyChange((prev) =>
      prev.map((tk) =>
        tk.id === taskId
          ? { ...tk, status: newStatus!, priority: Date.now() }
          : tk
      )
    );
    try {
      await api.put(`/tasks/${taskId}/move`, {
        status: newStatus,
        position: position ?? undefined,
      });
      toast.success(
        t("kanban.movedToast", KANBAN_COLUMNS.find((c) => c.id === newStatus)?.title || newStatus || "")
      );
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || t("kanban.moveError"));
      onChange(initialTasks);
    }
  }

  const activeTask = activeId ? tasks.find((tk) => tk.id === activeId) : null;

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {STATUSES.map((status) => {
          const col = KANBAN_COLUMNS.find((c) => c.id === status)!;
          const list = tasks
            .filter((tk) => tk.status === status)
            .sort((a, b) => a.priority - b.priority);
          return (
            <KanbanColumn key={status} id={status} title={col.title} tone={col.tone} count={list.length}>
              {list.map((tk) => (
                <KanbanCard
                  key={tk.id}
                  task={tk}
                  selected={selected.has(tk.id)}
                  onToggleSelect={() => toggleSelect(tk.id)}
                  onClick={() => onTaskClick?.(tk)}
                />
              ))}
              {list.length === 0 && (
                <div className="text-xs text-gray-400 italic text-center py-6 border-2 border-dashed border-gray-200 rounded-md">
                  {t("kanban.dropHere")}
                </div>
              )}
            </KanbanColumn>
          );
        })}
      </div>
      <DragOverlay>
        {activeTask ? (
          <KanbanCard task={activeTask} selected={false} />
        ) : null}
      </DragOverlay>

      {selected.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 bg-white dark:bg-slate-900 border border-subtle rounded-lg shadow-2xl px-4 py-2 flex items-center gap-2 flex-wrap max-w-[95vw]">
          <span className="text-sm font-medium dark:text-slate-100">
            {t("kanban.selectedCount", selected.size)}
          </span>
          <span className="text-muted">·</span>
          <select
            className="input py-1 text-xs h-8"
            disabled={bulkBusy}
            onChange={(e) => {
              if (e.target.value) bulkStatusChange(e.target.value as TaskStatus);
            }}
            defaultValue=""
          >
            <option value="" disabled>
              {t("kanban.moveTo")}
            </option>
            {KANBAN_COLUMNS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
          <select
            className="input py-1 text-xs h-8"
            disabled={bulkBusy}
            onChange={(e) => {
              bulkAssignee(e.target.value || null);
            }}
            defaultValue=""
          >
            <option value="" disabled>
              {t("kanban.assignTo")}
            </option>
            <option value="">{t("kanban.unassign")}</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.name}
              </option>
            ))}
          </select>
          <Button
            variant="danger"
            size="sm"
            onClick={bulkDelete}
            disabled={bulkBusy}
          >
            <Trash2 className="w-3.5 h-3.5" />
            {t("common.delete")}
          </Button>
          <Button variant="ghost" size="icon" onClick={clearSelection} title={t("common.cancel")}>
            <X className="w-4 h-4" />
          </Button>
        </div>
      )}
    </DndContext>
  );
}

function KanbanColumn({
  id,
  title,
  tone,
  count,
  children,
}: {
  id: string;
  title: string;
  tone: string;
  count: number;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={`rounded-lg p-3 ${tone} ${isOver ? "kanban-column-over" : ""}`}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm dark:text-slate-100">{title}</h3>
        <span className="text-xs text-body bg-white/60 dark:bg-slate-800/60 px-2 rounded-full">
          {count}
        </span>
      </div>
      <div className="space-y-2 min-h-[100px]">{children}</div>
    </div>
  );
}

function KanbanCard({
  task,
  selected = false,
  onToggleSelect,
  onClick,
  overlay = false,
}: {
  task: Task;
  selected?: boolean;
  onToggleSelect?: () => void;
  onClick?: () => void;
  overlay?: boolean;
}) {
  const { t } = useI18n();
  const { attributes, listeners, setNodeRef, isDragging, transform } = useDraggable({
    id: task.id,
  });
  const color = task.assignee_name ? colorFromName(task.assignee_name) : "#9CA3AF";
  const style: React.CSSProperties = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      }
    : {};
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-white dark:bg-slate-900 border rounded-lg p-3 shadow-sm select-none transition-colors ${
        selected
          ? "border-primary ring-2 ring-primary/30"
          : "border-subtle"
      } ${task.is_critical && !selected ? "border-l-4 border-l-red-500" : ""} ${
        isDragging || overlay ? "kanban-card-dragging shadow-lg" : ""
      }`}
    >
      <div className="flex items-start gap-2 mb-1">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect?.();
          }}
          className="mt-0.5 flex-shrink-0"
          title={selected ? t("common.cancel") : t("common.add")}
        >
          {selected ? (
            <CheckSquare className="w-4 h-4 text-primary" />
          ) : (
            <Square className="w-4 h-4 text-faint" />
          )}
        </button>
        <div
          {...listeners}
          {...attributes}
          onClick={() => onClick?.()}
          className="flex-1 cursor-grab active:cursor-grabbing"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="font-medium text-sm dark:text-slate-100">
              {task.title}
            </div>
            {task.is_critical && <span className="badge-critical">{t("gantt.fields.critical")}</span>}
          </div>
          {task.description && (
            <p className="text-xs text-muted line-clamp-2 mt-1">{task.description}</p>
          )}
        </div>
      </div>
      <div
        {...listeners}
        {...attributes}
        onClick={() => onClick?.()}
        className="flex items-center justify-between text-xs text-muted mt-1 pl-6 cursor-grab active:cursor-grabbing"
      >
        <div className="flex items-center gap-2">
          {task.assignee_name ? (
            <span
              className="w-6 h-6 rounded-full text-white text-[10px] font-medium flex items-center justify-center"
              style={{ background: color }}
              title={task.assignee_name}
            >
              {initials(task.assignee_name)}
            </span>
          ) : (
            <span className="text-faint">—</span>
          )}
          <span className="badge-primary">{task.story_points} SP</span>
          {task.deadline && (
            <span
              className={
                task.is_overdue
                  ? "text-red-600 dark:text-red-400 font-medium"
                  : ""
              }
            >
              {formatDate(task.deadline, "dd/MM")}
            </span>
          )}
          {task.slack !== null &&
            task.slack !== undefined &&
            task.slack > 0 && (
              <span className="text-faint" title="Slack">
                +{task.slack}d
              </span>
            )}
          {task.recurrence && task.recurrence !== "none" && (
            <span
              className="badge-primary text-[9px]"
              title={`Lặp lại: ${task.recurrence}`}
            >
              🔁
            </span>
          )}
        </div>
        {task.depends_on.length > 0 && (
          <span
            className="text-xs text-faint"
            title={`${task.depends_on.length} dependency`}
          >
            🔗 {task.depends_on.length}
          </span>
        )}
      </div>
    </div>
  );
}
