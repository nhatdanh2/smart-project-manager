"""Smoke tests for the CPM engine."""
from app.services.cpm_service import CPMTaskInput, calculate_cpm


def test_simple_chain():
    tasks = [
        CPMTaskInput(id="A", title="A", story_points=3, depends_on=[]),
        CPMTaskInput(id="B", title="B", story_points=2, depends_on=["A"]),
        CPMTaskInput(id="C", title="C", story_points=4, depends_on=["B"]),
    ]
    result = calculate_cpm(tasks)
    assert result.project_duration == 9
    assert set(result.critical_path) == {"A", "B", "C"}
    for t in result.tasks:
        assert t.slack == 0


def test_parallel_branches():
    tasks = [
        CPMTaskInput(id="A", title="A", story_points=2, depends_on=[]),
        CPMTaskInput(id="B", title="B", story_points=5, depends_on=["A"]),
        CPMTaskInput(id="C", title="C", story_points=2, depends_on=["A"]),
        CPMTaskInput(id="D", title="D", story_points=3, depends_on=["B", "C"]),
    ]
    result = calculate_cpm(tasks)
    assert result.project_duration == 10
    assert set(result.critical_path) == {"A", "B", "D"}
    # C has slack
    c = next(t for t in result.tasks if t.id == "C")
    assert c.slack == 3
    assert not c.is_critical


def test_isolated_nodes():
    tasks = [
        CPMTaskInput(id="X", title="X", story_points=1, depends_on=[]),
        CPMTaskInput(id="Y", title="Y", story_points=1, depends_on=[]),
    ]
    result = calculate_cpm(tasks)
    assert result.project_duration == 1
    assert set(result.critical_path) == {"X", "Y"}
