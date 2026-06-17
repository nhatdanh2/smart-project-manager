"""Critical Path Method (CPM) engine.

Implements the standard forward / backward pass algorithm using
``story_points`` as task duration in days.  Returns a complete CPM
result so the API layer can persist it onto the Task rows.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Set


@dataclass
class CPMTaskInput:
    id: str
    title: str
    story_points: int
    depends_on: List[str] = field(default_factory=list)


@dataclass
class CPMTaskResult:
    id: str
    title: str
    duration: int
    depends_on: List[str]
    early_start: int
    early_finish: int
    late_start: int
    late_finish: int
    slack: int
    is_critical: bool


@dataclass
class CPMResult:
    project_duration: int
    critical_path: List[str]
    tasks: List[CPMTaskResult]
    estimated_completion: Optional[datetime] = None
    delay_risk: float = 0.0

    def to_dict(self) -> dict:
        return {
            "project_duration": self.project_duration,
            "critical_path": self.critical_path,
            "estimated_completion": self.estimated_completion.isoformat()
            if self.estimated_completion
            else None,
            "delay_risk": self.delay_risk,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "duration": t.duration,
                    "depends_on": t.depends_on,
                    "early_start": t.early_start,
                    "early_finish": t.early_finish,
                    "late_start": t.late_start,
                    "late_finish": t.late_finish,
                    "slack": t.slack,
                    "is_critical": t.is_critical,
                }
                for t in self.tasks
            ],
        }


def calculate_cpm(
    tasks: Iterable[CPMTaskInput],
    deadline: Optional[datetime] = None,
    today: Optional[datetime] = None,
) -> CPMResult:
    """Run the CPM algorithm.

    Args:
        tasks: list of CPMTaskInput.
        deadline: project deadline (used to compute ``late_finish`` for sinks
            and ``delay_risk``).
        today: reference point for delay_risk.  Defaults to UTC now.
    """
    tasks_list = list(tasks)
    by_id: Dict[str, CPMTaskInput] = {t.id: t for t in tasks_list}

    # 1. Validate dependencies & build adjacency
    successors: Dict[str, List[str]] = defaultdict(list)
    predecessors: Dict[str, List[str]] = defaultdict(list)
    for t in tasks_list:
        for dep in t.depends_on:
            if dep not in by_id:
                # Skip unknown deps gracefully
                continue
            successors[dep].append(t.id)
            predecessors[t.id].append(dep)

    # 2. Topological sort (Kahn). If the graph is cyclic we return a best-effort
    #    result with project_duration=0 and empty critical path.
    in_degree: Dict[str, int] = {tid: len(predecessors[tid]) for tid in by_id}
    queue: deque = deque([tid for tid, deg in in_degree.items() if deg == 0])
    topo: List[str] = []
    while queue:
        node = queue.popleft()
        topo.append(node)
        for nxt in successors[node]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(topo) != len(tasks_list):
        # Cyclic graph - fall back to identity ordering.
        topo = list(by_id.keys())

    # 3. Forward pass
    es: Dict[str, int] = {}
    ef: Dict[str, int] = {}
    for tid in topo:
        node = by_id[tid]
        preds = predecessors[tid]
        start = max((ef[p] for p in preds), default=0)
        es[tid] = start
        ef[tid] = start + max(1, node.story_points)

    project_duration = max(ef.values()) if ef else 0

    # 4. Backward pass - determine project finish for sinks
    today_ = today or datetime.now(tz=timezone.utc)
    if deadline is not None:
        # Normalise to UTC for arithmetic
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        days_until_deadline = max(0, (deadline - today_).days)
        project_finish = max(project_duration, days_until_deadline)
    else:
        project_finish = project_duration

    ls: Dict[str, int] = {}
    lf: Dict[str, int] = {}
    for tid in reversed(topo):
        node = by_id[tid]
        succs = successors[tid]
        if not succs:
            lf[tid] = project_finish
        else:
            lf[tid] = min(ls[s] for s in succs)
        ls[tid] = lf[tid] - max(1, node.story_points)

    # 5. Slack & critical path
    results: List[CPMTaskResult] = []
    critical_path: List[str] = []
    for tid in topo:
        node = by_id[tid]
        slack = ls[tid] - es[tid]
        is_critical = slack == 0
        if is_critical:
            critical_path.append(tid)
        results.append(
            CPMTaskResult(
                id=tid,
                title=node.title,
                duration=max(1, node.story_points),
                depends_on=node.depends_on,
                early_start=es[tid],
                early_finish=ef[tid],
                late_start=ls[tid],
                late_finish=lf[tid],
                slack=slack,
                is_critical=is_critical,
            )
        )

    # Estimated completion = today + project_duration
    estimated_completion = today_ + timedelta(days=project_duration) if project_duration else None

    # delay_risk: 0 = on-time, 1 = certainly late
    if deadline is None or project_duration == 0:
        delay_risk = 0.0
    else:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        days_remaining = (deadline - today_).days
        delay_risk = max(0.0, min(1.0, (project_duration - days_remaining) / project_duration))

    return CPMResult(
        project_duration=project_duration,
        critical_path=critical_path,
        tasks=results,
        estimated_completion=estimated_completion,
        delay_risk=round(delay_risk, 3),
    )
