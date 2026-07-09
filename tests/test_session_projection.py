"""Tests for canonical EasyCrypt proof-state projection.

Pure Python only: these tests build small session directories and assert that
state text, event logs, goal parsing, and consistency checks converge into one
readable projection.
"""
from __future__ import annotations

import tempfile
import os
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.commands.inspect_commands import (  # type: ignore  # noqa: E402
    handle_goal_info,
    handle_goal_json,
    handle_program_json,
)
from core.easycrypt.commands.session_commands import handle_status  # type: ignore  # noqa: E402
from core.easycrypt.commands.speculative_commands import handle_align  # type: ignore  # noqa: E402
from core.easycrypt.ec_diagnose import diagnose_from_session  # type: ignore  # noqa: E402
from core.easycrypt.ec_suggest import suggest_from_session  # type: ignore  # noqa: E402
from core.easycrypt.ec_bridge_lemmas import analyze_bridge_lemmas_from_session  # type: ignore  # noqa: E402
from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_events import append_event  # type: ignore  # noqa: E402
from core.easycrypt.session_projection import (  # type: ignore  # noqa: E402
    projection_to_dict,
    read_proof_state_projection,
)
from core.easycrypt.session_tool_view import validate_tool_view  # type: ignore  # noqa: E402
from core.easycrypt.analysis.ec_call_subgoals import preview_from_session  # type: ignore  # noqa: E402
from core.easycrypt.subgoal_gap import analyze_session  # type: ignore  # noqa: E402
from core.easycrypt.swap_search import search_swaps  # type: ignore  # noqa: E402
from tests.helpers.builders import start_event, tool_called, tool_result  # noqa: E402

_start_event = start_event
_tool_called = tool_called
_tool_result = tool_result


def _append_closed_stream(d: Path) -> None:
    _start_event(d)
    _tool_called(d, "next")
    append_event(d, "tactic.submitted", {
        "tactic": "qed.",
        "history_lines_before": 0,
        "line_count": 1,
    })
    append_event(d, "goal.changed", {
        "tactic": "qed.",
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
        "no_progress": False,
        "candidate_closed": True,
    })
    append_event(d, "tactic.result", {
        "tactic": "qed.",
        "status": "ok",
        "history_committed": True,
        "goals_before": 1,
        "goals_after": 0,
        "candidate_closed": True,
    })
    append_event(d, "proof.candidate_closed", {
        "tactic": "qed.",
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
    })
    _tool_result(d, "next")


def _extract_json_object(text: str) -> dict:
    lines = text.splitlines(keepends=True)
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("{"):
            start = i
            break
    json_text = "".join(lines[start:])
    depth = 0
    end = len(json_text)
    for i, char in enumerate(json_text):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    import json
    return json.loads(json_text[:end])


def test_projection_reads_closed_verified_state() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[35|check]>\n"
            "No more goals\n"
            "[36|check]>\n"
            "+ added lemma: `L'\n"
            "[37|check]>\n",
            encoding="utf-8",
        )
        (d / "history.ec").write_text("qed.\n", encoding="utf-8")
        _append_closed_stream(d)
        append_event(d, "verification.completed", {
            "lemma": "L",
            "status": "pass",
            "verifier": "easycrypt",
        })

        projection = read_proof_state_projection(d)
        assert projection.status == "verified"
        assert projection.candidate_ready is True
        assert projection.final_ready is True
        assert projection.goal.goal_type == "complete"
        assert projection.goal.num_remaining == 0
        assert projection.events.ok is True
        assert projection.consistency.ok is True
        assert projection.latest_transition.kind == "closed"


def test_projection_preserves_phoare_goal_type() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "phoare [UFCMA(RO).distinguish : true ==> res \\/ UFCMA.bad2]\n"
            "[<=] qdec%r * pr_zeropol\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)

        data = projection_to_dict(d)
        assert data["status"] == "open"
        assert data["goal"]["goal_type"] == "phoare"
        assert data["goal"]["num_remaining"] == 1
        assert data["goal"]["parsed_goal"]["goal_type"] == "phoare"
        assert data["events"]["ok"] is True


def test_projection_goal_hash_ignores_final_ec_prompt_line() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plain = root / "plain"
        prompted = root / "prompted"
        plain.mkdir()
        prompted.mkdir()
        body = "[1|check]>\nCurrent goal\n----\nx = y\n"
        (plain / "current.out").write_text(body, encoding="utf-8")
        (prompted / "current.out").write_text(body + "[2|check]>\n", encoding="utf-8")
        _start_event(plain)
        _start_event(prompted)

        plain_projection = read_proof_state_projection(plain)
        prompted_projection = read_proof_state_projection(prompted)

        assert plain_projection.goal.active_goal_hash
        assert (
            plain_projection.goal.active_goal_hash
            == prompted_projection.goal.active_goal_hash
        )


def test_projection_prefers_ec_native_goal_artifact_over_pretty_parser() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "Pr[M.f() @ &m : res] <= 1%r\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        tool_views = d / "tool_views"
        tool_views.mkdir()
        (tool_views / "ec_goal.json").write_text(
            json.dumps({
                "tool": "ec-goal-json",
                "goal_state": {
                    "goal_type": "phoare",
                    "state_kind": "open",
                    "num_remaining": 3,
                    "num_remaining_determined": True,
                    "proof_candidate_closed": False,
                },
            }),
            encoding="utf-8",
        )
        _start_event(d)

        data = projection_to_dict(d)

        assert data["goal"]["goal_type"] == "phoare"
        assert data["goal"]["num_remaining"] == 3
        assert data["goal"]["fact_source"] == "ec_native_goal_state"
        assert data["goal"]["authority"] == "ec_native_ground_truth"
        assert data["goal"]["ec_ground_truth"] is True
        assert data["goal"]["parsed_goal"]["parser_num_remaining"] == 1


def test_goal_json_adapter_emits_fallback_provenance() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = x\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_goal_json(session, SimpleNamespace()) == 0
        data = _extract_json_object(buf.getvalue())

        assert data["kind"] == "easycrypt_goal_state_adapter"
        assert data["goal_state"]["fact_source"] == "pretty_goal_text"
        assert data["goal_state"]["authority"] == "pretty_text_fallback"
        assert data["goal_state"]["ec_ground_truth"] is False
        assert "x = x" in data["goal_state"]["active_goal_text"]
        assert validate_tool_view(data["tool_view"]).ok is True
        assert data["tool_view"]["tool"] == "goal-json"
        reread = projection_to_dict(d)
        assert reread["goal"]["fact_source"] == "pretty_goal_text"
        assert reread["goal"]["ec_ground_truth"] is False


def test_program_json_adapter_emits_program_ir_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "pre = true\n"
            "(1) x <@ M.f();\n"
            "post = true\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_program_json(session, SimpleNamespace()) == 0
        data = _extract_json_object(buf.getvalue())

        assert data["kind"] == "easycrypt_program_state_adapter"
        assert data["program_ir"]["fact_source"] == "pretty_program_text"
        assert data["program_ir"]["authority"] == "pretty_text_fallback"
        assert data["program_ir"]["ec_ground_truth"] is False
        assert validate_tool_view(data["tool_view"]).ok is True
        assert data["tool_view"]["tool"] == "program-json"
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_program_json(session, SimpleNamespace()) == 0
        reread = _extract_json_object(buf.getvalue())
        assert reread["program_ir"]["fact_source"] == "pretty_program_text"
        assert reread["program_ir"]["ec_ground_truth"] is False


def test_projection_surfaces_scoped_pr_bridge_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "sess"
        d.mkdir()
        theories = Path(td) / "theories"
        theories.mkdir()
        source = Path(td) / "Target.ec"
        source.write_text(
            "\n".join([
                "local lemma step1 &m:",
                "  Pr[MainD(D, RO).distinguish() @ &m : res] =",
                "  Pr[MainD(D, FinRO).distinguish() @ &m : res].",
                "proof. done. qed.",
            ]),
            encoding="utf-8",
        )
        (theories / "PROM.ec").write_text(
            "\n".join([
                "lemma pr_RO_FinRO_D &m x (p : bool -> bool):",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : p res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : p res].",
                "proof. done. qed.",
            ]),
            encoding="utf-8",
        )
        (d / "include_dirs.txt").write_text(str(theories) + "\n", encoding="utf-8")
        (d / "session_meta.json").write_text(
            '{"file": "' + str(source).replace("\\", "\\\\") + '", "lemma": "step1"}',
            encoding="utf-8",
        )
        (d / "context.ec").write_text("", encoding="utf-8")
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n\n"
            "Type variables: <none>\n\n"
            "&m: {}\n"
            "------------------------------------------------------------------------\n"
            "Pr[MainD(G2, FinRO).distinguish() @ &m : res] =\n"
            "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)

        projection = read_proof_state_projection(d)
        candidates = projection.goal.parsed_goal.get("pr_rewrite_candidates", [])
        names = [candidate["name"] for candidate in candidates]
        assert "pr_RO_FinRO_D" in names
        assert "step1" not in names


def test_projection_reads_start_goal_after_prompt_without_trailing_prompt() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[13|check]>\n"
            "Current goal\n"
            "\n"
            "Type variables: <none>\n"
            "\n"
            "x: int\n"
            "------------------------------------------------------------------------\n"
            "x = x\n",
            encoding="utf-8",
        )
        _start_event(d)

        projection = read_proof_state_projection(d)
        assert projection.status == "open"
        assert projection.goal.state_kind == "open"
        assert projection.goal.num_remaining == 1
        assert projection.goal.num_remaining_determined is True
        assert projection.goal.parsed_goal["parser_num_remaining"] == 1


def test_projection_preserves_prompt_before_goal_remaining_count() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[13|check]>\n"
            "Current goal (remaining: 2)\n"
            "\n"
            "Type variables: <none>\n"
            "\n"
            "x: int\n"
            "------------------------------------------------------------------------\n"
            "x = x\n",
            encoding="utf-8",
        )
        _start_event(d)

        projection = read_proof_state_projection(d)
        assert projection.status == "open"
        assert projection.goal.state_kind == "open"
        assert projection.goal.num_remaining == 2
        assert projection.goal.num_remaining_determined is True
        assert projection.goal.parsed_goal["parser_num_remaining"] == 2
        assert projection.consistency.errors == []


def test_projection_ignores_non_marker_remaining_text_after_goal_header() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal (remaining: 2)\n"
            "----\n"
            "x = y\n"
            "diagnostic: session_state remaining count differs from goal parser (1 != 2)\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)

        projection = read_proof_state_projection(d)
        assert projection.status == "open"
        assert projection.goal.num_remaining == 2
        assert projection.goal.parsed_goal["parser_num_remaining"] == 2
        assert projection.consistency.errors == []


def test_projection_surfaces_no_progress_transition() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "rewrite Foo.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "rewrite Foo.",
            "goals_before": 1,
            "goals_after": 1,
            "no_more_goals": False,
            "async_check_close": False,
            "no_progress": True,
            "no_progress_reason": "structural-fingerprint-equal",
            "candidate_closed": False,
        })
        append_event(d, "tactic.result", {
            "tactic": "rewrite Foo.",
            "status": "no_progress_reverted",
            "history_committed": False,
            "goals_before": 1,
            "goals_after": 1,
            "no_progress": True,
            "no_progress_reason": "structural-fingerprint-equal",
            "candidate_closed": False,
        })
        _tool_result(d, "next")

        projection = read_proof_state_projection(d)
        assert projection.latest_transition.kind == "no_progress"
        assert projection.latest_transition.no_progress is True
        assert projection.latest_transition.no_progress_reason == (
            "structural-fingerprint-equal"
        )
        assert projection.goal.goal_type == "ambient"
        assert projection.events.tactic_status_counts == {
            "no_progress_reverted": 1,
        }


def test_projection_status_recovers_after_later_accepted_tactic() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "rnd.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "tactic.result", {
            "tactic": "rnd.",
            "status": "error",
            "history_committed": False,
            "goals_before": 1,
            "goals_after": 1,
            "latest_error": "[error] invalid last instruction",
        })
        _tool_result(d, "next", status="error")
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "rnd{1}.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "tactic.result", {
            "tactic": "rnd{1}.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 1,
            "goals_after": 1,
            "latest_error": "",
        })
        _tool_result(d, "next")

        projection = read_proof_state_projection(d)

        assert projection.events.latest_error == "[error] invalid last instruction"
        assert projection.latest_transition.kind == "state_changed_same_goal_count"
        assert projection.status == "open"


def test_projection_ignores_pending_live_mutating_tool_call() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "rewrite Foo.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "rewrite Foo.",
            "goals_before": 1,
            "goals_after": 1,
            "no_more_goals": False,
            "async_check_close": False,
            "no_progress": False,
            "candidate_closed": False,
        })
        append_event(d, "tactic.result", {
            "tactic": "rewrite Foo.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 1,
            "goals_after": 1,
            "candidate_closed": False,
        })

        strict = read_proof_state_projection(d)
        live = read_proof_state_projection(d, live_tool_name="next")

        assert strict.events.ok is False
        assert any("missing_result" in err for err in strict.events.errors)
        assert live.events.ok is True
        assert live.latest_transition.kind == "state_changed_same_goal_count"


def test_projection_fails_closed_event_when_state_is_open() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _append_closed_stream(d)

        projection = read_proof_state_projection(d)
        assert projection.events.ok is True
        assert projection.goal.proof_candidate_closed is False
        assert projection.candidate_ready is False
        assert projection.consistency.ok is False
        assert any(
            "event log says candidate_closed" in err
            for err in projection.consistency.errors
        )


def test_projection_reports_event_contract_errors() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "events.jsonl").write_text(
            "{not json}\n"
            "{\"type\": \"tactic.result\", \"payload\": {}}\n",
            encoding="utf-8",
        )

        projection = read_proof_state_projection(d)
        assert projection.events.ok is False
        assert projection.status == "no_current"
        assert any("invalid JSON" in err for err in projection.events.errors)
        assert any("event.envelope.missing" in err for err in projection.events.errors)


def test_goal_info_embeds_compact_projection() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        session.curr.write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "rewrite Foo.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "rewrite Foo.",
            "goals_before": 1,
            "goals_after": 1,
            "no_more_goals": False,
            "async_check_close": False,
            "no_progress": True,
            "no_progress_reason": "structural-fingerprint-equal",
            "candidate_closed": False,
        })
        append_event(d, "tactic.result", {
            "tactic": "rewrite Foo.",
            "status": "no_progress_reverted",
            "history_committed": False,
            "goals_before": 1,
            "goals_after": 1,
            "no_progress": True,
            "no_progress_reason": "structural-fingerprint-equal",
            "candidate_closed": False,
        })
        _tool_result(d, "next")
        _tool_called(d, "goal-info", mutates=False)

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_goal_info(session, SimpleNamespace()) == 0
        data = _extract_json_object(buf.getvalue())

        assert data["goal_type"] == "ambient"
        ps = data["proof_state"]
        assert ps["status"] == "open"
        assert ps["goal"]["goal_type"] == "ambient"
        assert ps["goal"]["num_remaining"] == 1
        assert ps["latest_transition"]["kind"] == "no_progress"
        assert ps["event_contract"]["ok"] is True
        assert ps["consistency"]["ok"] is True
        tv = data["tool_view"]
        assert validate_tool_view(tv).ok is True
        assert tv["tool"] == "goal-info"
        assert tv["proof_state"]["status"] == "open"
        assert tv["guidance"]["recommendations"] == []
        assert "suggested_tactics" not in data
        assert "parser_action_policy" not in data
        assert "legacy_shape_tactic_templates" not in data


def test_goal_info_hidden_display_emits_tool_view_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = x\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)

        old = os.environ.get("SHANNON_LEGACY_DISPLAY")
        os.environ["SHANNON_LEGACY_DISPLAY"] = "hidden"
        try:
            buf = StringIO()
            with redirect_stdout(buf):
                assert handle_goal_info(session, SimpleNamespace()) == 0
        finally:
            if old is None:
                os.environ.pop("SHANNON_LEGACY_DISPLAY", None)
            else:
                os.environ["SHANNON_LEGACY_DISPLAY"] = old
        data = _extract_json_object(buf.getvalue())

        assert data["tool"] == "goal-info"
        assert "tool_view" not in data
        assert validate_tool_view(data).ok is True
        assert data["proof_state"]["status"] == "open"
        assert data["guidance"]["goal_info"]["goal_type"] == "ambient"
        assert data["guidance"]["recommendations"] == []
        assert "legacy_auto_resolved_names_text" not in data["debug"]


def test_projection_ignores_current_read_only_tool_call_when_live() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _start_event(d)
        _tool_called(d, "goal-info", mutates=False)

        strict = read_proof_state_projection(d)
        live = read_proof_state_projection(d, live_tool_name="goal-info")

        assert strict.events.ok is False
        assert any("tool.missing_result" in err for err in strict.events.errors)
        assert live.events.ok is True


def test_projection_treats_post_qed_prompt_as_closed_candidate() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text("[31|check]>", encoding="utf-8")
        (d / "history.ec").write_text(
            "proc; islossless.\nqed.\n",
            encoding="utf-8",
        )
        _append_closed_stream(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "qed.",
            "history_lines_before": 1,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "qed.",
            "goals_before": 0,
            "goals_after": -1,
            "no_more_goals": False,
            "async_check_close": False,
            "no_progress": False,
            "candidate_closed": False,
        })
        append_event(d, "tactic.result", {
            "tactic": "qed.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 0,
            "goals_after": -1,
            "candidate_closed": False,
        })
        _tool_result(d, "next")

        projection = read_proof_state_projection(d)
        assert projection.status == "candidate_closed"
        assert projection.candidate_ready is True
        assert projection.final_ready is False
        assert projection.goal.state_kind == "candidate_closed"
        assert projection.goal.goal_type == "complete"
        assert projection.goal.num_remaining == 0
        assert projection.goal.proof_candidate_closed is True
        assert projection.goal.parsed_goal["goal_type"] == "complete"
        assert "suggested_tactics" not in projection.goal.parsed_goal
        assert "parser_action_policy" not in projection.goal.parsed_goal
        assert projection.goal.parsed_goal["warnings"] == []
        assert projection.latest_transition.kind == "qed_saved"
        assert projection.consistency.ok is True
        assert not projection.consistency.warnings
        assert not projection.consistency.notes


def test_status_reports_post_qed_projection_as_complete() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        session.curr.write_text("[31|check]>", encoding="utf-8")
        session.history.write_text("proc; islossless.\nqed.\n", encoding="utf-8")
        _append_closed_stream(d)

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_status(session, SimpleNamespace()) == 0
        out = buf.getvalue()
        assert "[status] Goal type: complete" in out
        assert "[status] Proof COMPLETE" in out


def test_read_only_tools_use_projection_for_post_qed_complete() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        session.curr.write_text("[31|check]>", encoding="utf-8")
        session.history.write_text("proc; islossless.\nqed.\n", encoding="utf-8")
        _append_closed_stream(d)

        assert "Proof is already complete" in suggest_from_session(d, [])
        assert "proof complete" in analyze_session(d)
        assert "Proof is already complete" in diagnose_from_session(d)
        assert "Proof is already complete" in analyze_bridge_lemmas_from_session(d)
        assert "Proof is already complete" in preview_from_session(d, "true")
        swap = search_swaps(d)
        assert swap.success is True
        assert "Proof is already complete" in (swap.hint or "")

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_align(session, SimpleNamespace()) == 0
        assert "Proof is already complete" in buf.getvalue()


def test_goal_info_tool_view_closed_state_has_no_recommendations() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        session.curr.write_text("[31|check]>", encoding="utf-8")
        session.history.write_text("proc; islossless.\nqed.\n", encoding="utf-8")
        _append_closed_stream(d)

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_goal_info(session, SimpleNamespace()) == 0
        data = _extract_json_object(buf.getvalue())
        tv = data["tool_view"]

        assert validate_tool_view(tv).ok is True
        assert tv["proof_state"]["status"] == "candidate_closed"
        assert tv["guidance"]["recommendations"] == []
        assert tv["proof_state"]["goal"]["goal_type"] == "complete"
        assert tv["proof_state"]["goal"]["num_remaining"] == 0


if __name__ == "__main__":
    test_projection_reads_closed_verified_state()
    test_projection_preserves_phoare_goal_type()
    test_projection_reads_start_goal_after_prompt_without_trailing_prompt()
    test_projection_surfaces_no_progress_transition()
    test_projection_fails_closed_event_when_state_is_open()
    test_projection_reports_event_contract_errors()
    test_goal_info_embeds_compact_projection()
    test_goal_info_hidden_display_emits_tool_view_only()
    test_projection_ignores_current_read_only_tool_call_when_live()
    test_projection_ignores_pending_live_mutating_tool_call()
    test_projection_treats_post_qed_prompt_as_closed_candidate()
    test_status_reports_post_qed_projection_as_complete()
    test_read_only_tools_use_projection_for_post_qed_complete()
    test_goal_info_tool_view_closed_state_has_no_recommendations()
    print("PASS test_session_projection")
