"""Tests for structured prover-facing ToolView contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_tool_view import (  # type: ignore  # noqa: E402
    EVIDENCE_BUCKETS,
    RECOMMENDATION_ACTION_TYPES,
    Recommendation,
    SourceRef,
    action_requires_instantiation,
    make_tool_view,
    stdout_tool_view,
    write_tool_view_artifact,
    tool_view_from_projection,
    validate_tool_view,
)
from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_events import append_event, events_of_type, read_events  # type: ignore  # noqa: E402
from core.easycrypt.search.handlers import handle_tactic_forms  # type: ignore  # noqa: E402


def test_empty_tool_view_contract() -> None:
    view = make_tool_view(tool="status", proof_state={"status": "open"})
    data = view.to_dict()

    assert data["schema_version"] == 1
    assert data["tool"] == "status"
    assert data["ok"] is True
    assert data["proof_state"]["status"] == "open"
    assert data["guidance"]["recommendations"] == []
    assert set(EVIDENCE_BUCKETS).issubset(data["evidence"].keys())
    assert validate_tool_view(data).ok is True


def test_recommendation_and_evidence_contract() -> None:
    rec = Recommendation(
        id="auto_bridge.0",
        kind="tactic_chain",
        producer="AUTO-BRIDGE-SUGGEST",
        action="-chain -c 'have -> : Pr[A] = Pr[B] by byequiv H.'",
        why="A bridge lemma matched the current Pr equality.",
        action_type="inspection_action",
        confidence="verified",
        preconditions=["proof_state.status == open"],
        source_refs=[
            SourceRef(
                kind="lemma",
                id="H",
                path="proof.ec",
                line=42,
            ),
        ],
        evidence_refs=["probe.auto_bridge.0"],
    )
    data = make_tool_view(
        tool="goal-info",
        proof_state={"status": "open"},
        recommendations=[rec],
        evidence={
            "probe": [{
                "id": "probe.auto_bridge.0",
                "tool": "daemon.try_tactic",
                "accepted": True,
            }],
            "kb": [{
                "id": "kb.bridge_lemma",
                "source": "narrative.lemma_catalog",
            }],
        },
    ).to_dict()

    validation = validate_tool_view(data)
    assert validation.ok is True
    assert data["guidance"]["recommendations"][0]["confidence"] == "verified"
    assert (
        data["guidance"]["recommendations"][0]["action_type"]
        == "inspection_action"
    )
    assert data["evidence"]["probe"][0]["accepted"] is True
    assert "runnable_tactic" in RECOMMENDATION_ACTION_TYPES
    assert "probe_tactic" in RECOMMENDATION_ACTION_TYPES
    assert "epistemic" in EVIDENCE_BUCKETS


def test_tool_view_validation_is_fail_closed_on_bad_shape() -> None:
    bad = {
        "schema_version": 1,
        "tool": "",
        "ok": True,
        "proof_state": {},
        "guidance": {"recommendations": [{"id": "x"}]},
        "evidence": {"probe": {"id": "p0"}},
        "notes": [],
        "errors": [],
        "debug": {},
    }
    validation = validate_tool_view(bad)

    assert validation.ok is False
    assert any("tool" in err for err in validation.errors)
    assert any("missing `kind`" in err for err in validation.errors)


def test_tool_view_rejects_unknown_recommendation_action_type() -> None:
    data = make_tool_view(
        tool="goal-info",
        proof_state={"status": "open"},
        recommendations=[{
            "id": "bad",
            "kind": "tactic_candidate",
            "producer": "test",
            "action": "smt().",
            "why": "invalid action type",
            "confidence": "medium",
            "action_type": "pasteable",
            "preconditions": [],
            "source_refs": [],
            "evidence_refs": [],
            "metadata": {},
        }],
    ).to_dict()

    validation = validate_tool_view(data)
    assert validation.ok is False
    assert any("action_type" in err for err in validation.errors)


def test_stdout_tool_view_strips_legacy_debug_and_optionally_omits_raw_preview() -> None:
    view = {
        "tool": "bridge-lemmas",
        "debug": {
            "legacy_text": "large human block",
            "kept": "small diagnostic",
        },
        "evidence": {
            "raw": [{
                "id": "raw.bridge_lemmas_text",
                "format": "legacy_text",
                "preview": "large preview",
                "source_name": "bridge",
            }],
        },
    }

    full = stdout_tool_view(view)
    assert "legacy_text" not in full["debug"]
    assert full["debug"]["kept"] == "small diagnostic"
    assert full["evidence"]["raw"][0]["preview"] == "large preview"

    slim = stdout_tool_view(view, omit_raw_previews=True)
    assert slim["evidence"]["raw"] == [{
        "id": "raw.bridge_lemmas_text",
        "format": "legacy_text",
        "source_name": "bridge",
        "preview_omitted": True,
    }]


def test_action_requires_instantiation_matches_cli_template_markers() -> None:
    assert action_requires_instantiation("call <lemma>.")
    assert action_requires_instantiation("ecall LEMMA.")
    assert action_requires_instantiation("call oracle_name.")
    assert action_requires_instantiation("ecall foo ... .")
    assert not action_requires_instantiation("call Hf.")


def test_tool_view_from_projection_returns_json_ready_dict() -> None:
    data = tool_view_from_projection(
        tool="diagnose",
        proof_state={"status": "open", "latest_transition": {"kind": "error"}},
        notes=["diagnose used latest structured event"],
    )

    assert data["tool"] == "diagnose"
    assert data["proof_state"]["latest_transition"]["kind"] == "error"
    assert data["notes"][0]["message"] == "diagnose used latest structured event"
    assert validate_tool_view(data).ok is True


def test_tool_view_artifact_payload_is_compact_and_indexable(tmp_path=None) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        view = make_tool_view(
            tool="status",
            proof_state={"status": "open"},
            notes=["compact status view"],
        ).to_dict()
        payload = write_tool_view_artifact(Path(td), view)

        artifact = Path(payload["artifact"])
        assert artifact.exists()
        assert payload["tool"] == "status"
        assert payload["schema_version"] == 1
        assert payload["ok"] is True
        assert len(payload["view_hash"]) == 40
        assert payload["proof_status"] == "open"
        assert payload["recommendation_count"] == 0
        assert validate_tool_view(__import__("json").loads(artifact.read_text())).ok


def test_lookup_tool_records_tool_view_event() -> None:
    import json
    import tempfile
    from contextlib import redirect_stdout
    from io import StringIO
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        append_event(d, "session.started", {
            "file": None,
            "lemma": "L",
            "include_dirs": [],
            "discarded_tactic_count": 0,
            "restart_count": 1,
        })
        session = open_session(d)
        session.curr.write_text(
            "[1|check]>\nCurrent goal\n----\nequiv [ M.f ~ N.f : ={x} ==> ={res} ]\n[2|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_tactic_forms(
                session,
                SimpleNamespace(tactic_forms="call"),
            ) == 0
        text = buf.getvalue()
        assert "call" in text
        assert "exlim" in text
        assert "ecall (equ_cc _ ROin.m{1} ROout.m{1})" not in text

        events = read_events(d)
        view_events = events_of_type(events, "tool.view.produced")
        assert len(view_events) == 1
        payload = view_events[0]["payload"]
        artifact = Path(payload["artifact"])
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert data["tool"] == "tactic-forms"
        assert data["evidence"]["context"][0]["query"]["mode"] == "pRHL"
        assert validate_tool_view(data).ok is True


def test_tactic_forms_reports_phoare_while_mode() -> None:
    import tempfile
    from contextlib import redirect_stdout
    from io import StringIO
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.curr.write_text(
            "[1|check]>\nCurrent goal\n----\nphoare [ M.f : true ==> res ] = 1%r\n[2|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_tactic_forms(
                session,
                SimpleNamespace(tactic_forms="while"),
            ) == 0

    text = buf.getvalue()
    assert "Current proof mode: phoare" in text
    assert "while (INVARIANT) (VARIANT)." in text
    assert "Do not append a probability argument" in text


def test_tactic_forms_reports_phoare_rnd_mode() -> None:
    import tempfile
    from contextlib import redirect_stdout
    from io import StringIO
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.curr.write_text(
            "[1|check]>\nCurrent goal\n----\nphoare [ M.guess : true ==> res ] = 1%r\n[2|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_tactic_forms(
                session,
                SimpleNamespace(tactic_forms="rnd"),
            ) == 0

    text = buf.getvalue()
    assert "Current proof mode: phoare" in text
    # The single-program phoare/pHL forms must be surfaced (the gap this fixes:
    # the agent previously got pRHL-only guidance and discarded the result).
    assert "rnd predT." in text
    assert "rnd (fun x => P x)." in text
    assert "SINGLE-program goal" in text
    assert "mu d predT = 1%r" in text
    # The two-function pRHL bijection must be explicitly warned against here.
    assert "pRHL-only" in text


def test_tactic_forms_reports_generic_ecall_forms() -> None:
    import tempfile
    from contextlib import redirect_stdout
    from io import StringIO
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        append_event(d, "session.started", {
            "file": None,
            "lemma": "L",
            "include_dirs": [],
            "discarded_tactic_count": 0,
            "restart_count": 1,
        })
        session = open_session(d)
        session.curr.write_text(
            "[1|check]>\nCurrent goal\n----\n"
            "equiv [ M.f ~ N.f : ={x} ==> ={res} ]\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_tactic_forms(
                session,
                SimpleNamespace(tactic_forms="ecall"),
            ) == 0
        text = buf.getvalue()
        assert "=== `ecall` tactic" in text
        assert "ecall (LEMMA arg1 arg2 ...)." in text
        assert "ecall{1}" in text
        assert "f_ok1 x" in text
        assert "equ_cc" not in text

        events = read_events(d)
        view_events = events_of_type(events, "tool.view.produced")
        assert len(view_events) == 1
        payload = view_events[0]["payload"]
        data = json.loads(Path(payload["artifact"]).read_text(encoding="utf-8"))
        assert data["tool"] == "tactic-forms"
        assert data["evidence"]["context"][0]["query"]["tactic"] == "ecall"
        assert validate_tool_view(data).ok is True


def test_tactic_forms_reports_indexed_sp_branch_opener() -> None:
    import tempfile
    from contextlib import redirect_stdout
    from io import StringIO
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.curr.write_text(
            "[1|check]>\nCurrent goal\n----\n"
            "equiv [ DDH1.G1.dec ~ DDH0.G1.dec : ={glob A} ==> ={res} ]\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_tactic_forms(
                session,
                SimpleNamespace(tactic_forms="sp"),
            ) == 0

    text = buf.getvalue()
    assert "Current proof mode: pRHL" in text
    assert "sp I J." in text
    assert "sp 0 1; inline *; if => //; auto." in text


def main() -> int:
    tests = [
        test_empty_tool_view_contract,
        test_recommendation_and_evidence_contract,
        test_tool_view_validation_is_fail_closed_on_bad_shape,
        test_tool_view_rejects_unknown_recommendation_action_type,
        test_stdout_tool_view_strips_legacy_debug_and_optionally_omits_raw_preview,
        test_action_requires_instantiation_matches_cli_template_markers,
        test_tool_view_from_projection_returns_json_ready_dict,
        test_tool_view_artifact_payload_is_compact_and_indexable,
        test_lookup_tool_records_tool_view_event,
        test_tactic_forms_reports_phoare_while_mode,
        test_tactic_forms_reports_phoare_rnd_mode,
        test_tactic_forms_reports_generic_ecall_forms,
        test_tactic_forms_reports_indexed_sp_branch_opener,
    ]
    for test in tests:
        test()
    print("PASS test_session_tool_view")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
