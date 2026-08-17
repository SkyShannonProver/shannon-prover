"""Deterministic sentinels for native EasyCrypt typed-state projection."""

from __future__ import annotations

import hashlib
from pathlib import Path

from core.easycrypt.ec_runtime_identity import discover_easycrypt_runtime_identity
from core.easycrypt.native_semantics import (
    NativeStateProjectionRequest,
    run_native_state_projection,
)
from core.easycrypt.session_projection import active_goal_hash_from_raw


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "native_semantics"
TRUE_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
true
"""
STATEMENT_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
Context : hr: {x, y : int}

pre = true

(1--)  y <- x + 1                 
(2--)  if (y < 0) {               
(2.1)    y <- -y                  
(2--)  } else {                   
(2?1)    NativeStateFixture.g <- y
(2--)  }                          

post = true
"""
EQUIV_STATEMENT_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {x, y : int} [programs are in sync]
&2 (right) : {x, y : int}

pre = x{1} = x{2}

(1)  y <@ NativeStateCallee.bump(x)

post = y{1} = y{2}
"""
TWO_GOAL_FOCUSED_GOAL = """Current goal (remaining: 2)

Type variables: <none>

------------------------------------------------------------------------
true
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_truncated(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("kind") == "truncated" or any(
            _contains_truncated(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_truncated(item) for item in value)
    return False


def _request(
    request_id: str,
    context: Path,
    history: Path,
    goal_text: str,
    *,
    max_nodes: int = 4096,
) -> NativeStateProjectionRequest:
    return NativeStateProjectionRequest(
        request_id=request_id,
        context_file=context,
        history_file=history,
        include_dirs=(),
        expected_goal_identity=active_goal_hash_from_raw(goal_text),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
        max_nodes=max_nodes,
    )


def test_native_state_projects_pure_goal_without_changing_inputs() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    before = (context.read_bytes(), history.read_bytes())
    result = run_native_state_projection(
        _request("native-state-pure", context, history, TRUE_GOAL),
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )

    projection = result.projection
    assert projection["complete"] is True
    assert projection["open_goal_count"] == 1
    assert projection["focused_goal"] == {
        "judgment_kind": "pure",
        "formula": {
            "kind": "true",
            "complete": True,
            "text": "true",
            "type": "bool",
            "children": [],
        },
        "programs": [],
        "procedures": [],
    }
    assert (context.read_bytes(), history.read_bytes()) == before


def test_native_state_multi_goal_focus_matches_easycrypt_current_goal() -> None:
    context = FIXTURES / "two_goal_focus.ec"
    history = FIXTURES / "split_history.ec"
    before = (context.read_bytes(), history.read_bytes())

    result = run_native_state_projection(
        _request(
            "native-state-two-goal-focus",
            context,
            history,
            TWO_GOAL_FOCUSED_GOAL,
        ),
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )

    assert result.goal_before == TWO_GOAL_FOCUSED_GOAL
    assert active_goal_hash_from_raw(result.goal_before) == (
        active_goal_hash_from_raw(TWO_GOAL_FOCUSED_GOAL)
    )
    assert result.projection["open_goal_count"] == 2
    assert result.projection["focused_goal"]["formula"] == {
        "kind": "true",
        "complete": True,
        "text": "true",
        "type": "bool",
        "children": [],
    }
    assert (context.read_bytes(), history.read_bytes()) == before


def test_native_state_projects_statement_instruction_tree_and_locals() -> None:
    context = FIXTURES / "statement_goal.ec"
    history = FIXTURES / "proc_history.ec"
    runtime = discover_easycrypt_runtime_identity()
    result = run_native_state_projection(
        _request(
            "native-state-statement",
            context,
            history,
            STATEMENT_GOAL,
        ),
        runtime_identity=runtime,
        timeout=30,
    )

    projection = result.projection
    focused = projection["focused_goal"]
    assert projection["complete"] is True
    assert focused["judgment_kind"] == "hoare_statement"
    assert focused["formula"]["child_roles"] == [
        "precondition", "postcondition"
    ]
    postcondition = focused["formula"]["children"][1]
    assert postcondition["kind"] == "exceptional_postcondition"
    assert postcondition["child_roles"] == ["normal_postcondition"]
    assert postcondition["exception_paths"] == []
    assert postcondition["children"][0]["text"] == "true"
    assert len(focused["programs"]) == 1
    statement = focused["programs"][0]["statement"]
    assert statement["kind"] == "statement"
    assert [item["kind"] for item in statement["instructions"]] == [
        "assign", "if"
    ]
    assert statement["instructions"][0]["top_level_position"] == 1
    conditional = statement["instructions"][1]
    assert conditional["structural_path"] == ["single", "2"]
    assert conditional["then_statement"]["instructions"][0]["kind"] == "assign"
    assert conditional["else_statement"]["instructions"][0]["kind"] == "assign"
    assert projection["local_declarations"] == []


def test_native_state_rejects_goal_identity_drift_after_valid_projection() -> None:
    context = FIXTURES / "local_goal.ec"
    history = FIXTURES / "local_history.ec"
    request = NativeStateProjectionRequest(
        request_id="native-state-drift",
        context_file=context,
        history_file=history,
        include_dirs=(),
        expected_goal_identity="not-the-current-goal",
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )
    try:
        run_native_state_projection(
            request,
            runtime_identity=discover_easycrypt_runtime_identity(),
            timeout=30,
        )
    except RuntimeError as exc:
        assert "different goal" in str(exc)
    else:
        raise AssertionError("native state projection accepted stale goal identity")


def test_native_state_projects_typed_local_variable_and_hypothesis() -> None:
    context = FIXTURES / "local_goal.ec"
    history = FIXTURES / "local_history.ec"
    # This rendering is the installed EasyCrypt pretty-printer's canonical
    # current-goal block, used only to bind the replay to the expected state.
    goal = """Current goal

Type variables: <none>

x: int
H: x = 0
------------------------------------------------------------------------
x = 0
"""
    result = run_native_state_projection(
        _request(
            "native-state-locals",
            context,
            history,
            goal,
        ),
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    locals_value = result.projection["local_declarations"]
    assert [(item["name"], item["kind"]) for item in locals_value] == [
        ("H", "hypothesis"),
        ("x", "variable"),
    ]
    assert locals_value[0]["formula"]["kind"] == "equality"
    assert locals_value[1]["type"] == "int"


def test_native_state_marks_order_relation_from_typed_operator_path() -> None:
    context = FIXTURES / "relation_goal.ec"
    history = FIXTURES / "empty_history.ec"
    goal = """Current goal

Type variables: <none>

x: int
y: int
------------------------------------------------------------------------
x <= y
"""
    result = run_native_state_projection(
        _request("native-state-relation", context, history, goal),
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )

    formula = result.projection["focused_goal"]["formula"]
    assert formula["kind"] == "operator_application"
    assert formula["relation_operator"] == "<="
    assert [child["text"] for child in formula["children"]] == ["x", "y"]


def test_native_state_projects_two_sided_calls_with_exact_xpaths() -> None:
    context = FIXTURES / "equiv_statement_goal.ec"
    history = FIXTURES / "proc_history.ec"
    result = run_native_state_projection(
        _request(
            "native-state-equiv-statement",
            context,
            history,
            EQUIV_STATEMENT_GOAL,
        ),
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )

    focused = result.projection["focused_goal"]
    assert focused["judgment_kind"] == "equivalence_statement"
    assert focused["formula"]["child_roles"] == [
        "precondition", "postcondition"
    ]
    assert [program["side"] for program in focused["programs"]] == [
        "left", "right"
    ]
    calls = [
        program["statement"]["instructions"][0]
        for program in focused["programs"]
    ]
    assert [call["structural_path"] for call in calls] == [
        ["left", "1"], ["right", "1"]
    ]
    assert {call["procedure"] for call in calls} == {
        "Top.NativeStateCallee./bump"
    }
    assert all(call["kind"] == "call" for call in calls)


def test_native_state_marks_budget_truncation_explicitly() -> None:
    context = FIXTURES / "deep_goal.ec"
    history = FIXTURES / "empty_history.ec"
    goal = """Current goal

Type variables: <none>

a0: bool
a1: bool
a2: bool
a3: bool
a4: bool
a5: bool
a6: bool
a7: bool
a8: bool
a9: bool
a10: bool
------------------------------------------------------------------------
a0 => a1 => a2 => a3 => a4 => a5 => a6 => a7 => a8 => a9 => a10 => true
"""
    request = NativeStateProjectionRequest(
        request_id="native-state-truncated",
        context_file=context,
        history_file=history,
        include_dirs=(),
        expected_goal_identity=active_goal_hash_from_raw(goal),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
        max_depth=8,
    )

    result = run_native_state_projection(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )

    assert result.projection["complete"] is False
    assert result.projection["truncation_reasons"] == ["max_depth"]
    assert _contains_truncated(result.projection["focused_goal"]["formula"])
