#!/usr/bin/env python3
"""Root-cause guard for the Bug-1 class: parse the AUTHORITATIVE backend result.

Backend command stdout is multi-section (hook/legacy lines, candidate-option
JSON previews, daemon-verify emissions, then the real result block). Selecting
"the first decodable JSON" let consumers latch onto a stray earlier object:
  * a commit verdict read an `ok:false` daemon-verify emission and reported a
    successful commit as "rejected" (Bug 1);
  * the agent-view snapshot — which becomes the agent's entire visible state —
    has the same exposure.

The fix replaces first-`{` with marker/shape-anchored selection. These tests
pin the shared primitives so the anti-pattern can't quietly come back.

Pure: no EasyCrypt needed.

Run: python3 -m pytest tests/test_backend_stdout_authoritative_parse.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.backend_actions import (  # noqa: E402
    _content_observation_from_payload,
    _iter_json_objects,
    _select_json_object,
    _stdout_error_summary,
    _tactic_execution_result_payload,
    agent_observation_from_command,
    workspace_payload_from_stdout,
)


def test_tactic_forms_inspect_return_is_not_truncated():
    """tactic_forms is a static, bounded argument-forms reference the agent pulls to
    disambiguate a form; the generic 1200-char inspect preview cut it mid-list around
    Form 4 (disproportionately the form needed). It must be shown WHOLE while every
    other inspect/lookup topic stays capped. panel audit: tactic_forms was 80% USED
    and truncation was its only quality defect."""
    from core.easycrypt.search.ec_tactic_forms import format_forms, get_forms
    full = format_forms(get_forms("call"), mode="probability", goal_text="")
    assert len(full) > 1200 and full.count("Form ") >= 10  # the case that used to truncate
    # the backend result payload carries no `topic`, so it falls through to the
    # stdout preview (the path that did the truncating).
    tf = _content_observation_from_payload("inspect_tactic_forms", {}, full)
    prev = tf.get("preview", "")
    assert prev.count("Form ") == full.count("Form ")  # every form present, none clipped
    assert "\nForm 1:" in prev                         # line structure preserved
    assert "\n  Use when:" in prev                     # not flattened into a paragraph
    assert not prev.endswith("...")                    # not truncated
    # a different inspect topic with the same long stdout stays capped at 1200
    other = _content_observation_from_payload("inspect_diagnose", {}, full)
    assert len(other.get("preview", "")) <= 1200
    assert other.get("preview", "").endswith("...")    # genuinely truncated


def _fake_lemma_index(n: int) -> str:
    head = (
        f"=== Foo.eca: {n} lemma statement(s) (signatures only) ===\n"
        "These are every lemma declared in the current file...\n"
    )
    return head + "".join(
        f"\nL{40 + i} [lemma, top_level] mylemma_{i}:\n"
        f"    lemma mylemma_{i} : long_signature_{i} = ok_{i}\n"
        for i in range(n)
    )


def test_lemma_index_inspect_return_keeps_whole_entries():
    """lemma_index is an UNBOUNDED whole-file roster the agent pulls to plan; the
    generic 1200-char flatten-and-cut dropped the load-bearing lemmas (chacha 51 -> 9)
    and sliced the last entry mid-signature. A small file is shown whole; a large one
    cuts at a lemma BOUNDARY (never mid-signature) with a count + lookup_symbol escape.
    panel audit: lemma_index, INSPECT_QUALITY.md."""
    # small file: shown whole, no truncation note
    small = _content_observation_from_payload(
        "inspect_lemma_index", {}, _fake_lemma_index(20)).get("preview", "")
    assert small.count("[lemma, top_level]") == 20
    assert "more lemma" not in small
    # large file: count note present, ends on the note (not mid-signature)
    big = _content_observation_from_payload(
        "inspect_lemma_index", {}, _fake_lemma_index(300)).get("preview", "")
    assert "more lemma(s) not shown" in big and "lookup_symbol" in big
    shown = big.count("[lemma, top_level]")
    assert 0 < shown < 300                              # truncated to a useful prefix
    # every shown entry is COMPLETE: header line + its signature line both present
    assert big.count("lemma mylemma_") == shown


def test_iter_yields_every_object_in_order():
    text = (
        "noise {\"a\":1} more\n"
        "[MARKER]\n{\"b\":2}\n"
        "trailing {\"c\":3}"
    )
    objs = list(_iter_json_objects(text))
    assert [o.get(k) for o, k in zip(objs, "abc")] == [1, 2, 3]


def test_iter_skips_unquoted_braces_and_keeps_going():
    # Legacy goal text has brace fragments like `{x : unit, r : bool}` that are
    # not valid JSON; the scanner must skip them and still find real objects.
    text = "&1 (left) : {x : unit, r : bool}\n{\"real\": true}"
    objs = list(_iter_json_objects(text))
    assert objs == [{"real": True}]


def test_select_returns_last_or_first_match():
    text = (
        json.dumps({"kind": "v", "n": 1}) + "\n"
        + json.dumps({"kind": "other"}) + "\n"
        + json.dumps({"kind": "v", "n": 2})
    )
    pred = lambda o: o.get("kind") == "v"
    assert _select_json_object(text, pred, last=True).get("n") == 2
    assert _select_json_object(text, pred, last=False).get("n") == 1
    assert _select_json_object(text, lambda o: o.get("kind") == "absent") == {}


def test_tactic_result_anchor_picks_block_after_last_marker():
    # An earlier verify-style TER block (ok:false) must not win over the final
    # committed result block (ok:true).
    earlier = json.dumps({"result": {"ok": False, "status": "needs_intermediate"}})
    final = json.dumps({"execution": {"state_changed": True},
                        "result": {"ok": True, "status": "ok"}})
    text = (
        f"[TACTIC-EXECUTION-RESULT]\n{earlier}\n"
        "[AUTO-PIVOT] probability-route analysis\n{\"intent\":\"x\"}\n"
        f"[TACTIC-EXECUTION-RESULT]\n{final}\n"
    )
    got = _tactic_execution_result_payload(text)
    assert got["result"]["ok"] is True
    assert got["result"]["status"] == "ok"


def test_tactic_result_anchor_absent_returns_empty():
    assert _tactic_execution_result_payload("no marker {\"ok\":true} here") == {}


def test_workspace_payload_ignores_stray_json_before_the_view():
    # A candidate-option preview decodes first; the workspace view follows.
    stray = json.dumps({"intent": "commit_tactic", "payload": {"tactic": "x."}})
    view = json.dumps({
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "x = x"]},
        "proof_status": "open",
        "candidate_moves": [],
    })
    text = f"[AUTO-PIVOT] ...\n{stray}\n{view}\n"
    got = workspace_payload_from_stdout(text)
    assert got.get("kind") == "prover_workspace_view"
    assert got.get("current_goal", {}).get("lines")


def test_workspace_payload_prefers_the_freshest_view():
    older = json.dumps({"current_goal": {"lines": ["old"]}, "proof_status": "open"})
    newer = json.dumps({"current_goal": {"lines": ["new"]}, "proof_status": "open"})
    got = workspace_payload_from_stdout(f"{older}\n{newer}")
    assert got["current_goal"]["lines"] == ["new"]


def test_workspace_payload_falls_back_when_no_view_shape():
    # Defensive: if nothing looks like a view, return the first object rather
    # than crash (caller validates downstream).
    got = workspace_payload_from_stdout(json.dumps({"unrelated": 1}))
    assert got == {"unrelated": 1}


def test_stdout_error_summary_recovers_envelope_error():
    # The [TACTIC-EXECUTION-RESULT] block carries no structured errors, but the
    # daemon agent-view envelope (earlier in stdout) carries the raw EC error.
    stdout = (
        '{"kind":"agent_view","ok":false,"status":"error","errors":'
        '[{"code":"commit.failed","failed_tactic":"call (equ_cc _ _ _).",'
        '"message":"[error] cannot infer all placeholders"}]}\n'
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":false,"status":"error","execution":{"state_changed":false}}\n'
    )
    assert _stdout_error_summary(stdout) == "[error] cannot infer all placeholders"


def test_rejected_commit_surfaces_raw_ec_error_in_observation():
    # End-to-end: a rejection whose result block omits errors still lands the raw
    # EC error in last_result.error_summary (so the "use the error summary" text
    # is no longer a blank pointer; L1 can show *why* it failed).
    stdout = (
        '{"kind":"agent_view","ok":false,"status":"error","errors":'
        '[{"message":"[error] cannot infer all placeholders"}]}\n'
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":false,"status":"error","execution":{"state_changed":false}}\n'
    )
    obs = agent_observation_from_command(
        "commit_tactic",
        ["sh", "-c", "call (equ_cc _ _ _)."],
        stdout=stdout,
        stderr="",
        exit_code=1,
    )
    assert obs.get("error_summary") == "[error] cannot infer all placeholders"
    assert "rejected" in str(obs.get("result") or "").lower()


def test_no_progress_commit_says_no_progress_not_rejected_with_error():
    # EC ACCEPTS a no-op tactic but it changes nothing -> auto-reverts
    # (status=no_progress_reverted, errors=None). It must NOT render as "rejected —
    # use the error summary" (there is no error); say it is a no-op so the agent stops
    # hunting a non-existent error and tries something else. Root-caused by EC replay
    # (MEE-CBC L1 2026-06-06: repeated `inline` variants accepted-but-no-op'd).
    stdout = (
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":false,"result":{"ok":false,"status":"no_progress_reverted",'
        '"raw_excerpt":"[TACTIC_NO_EFFECT_AUTO_REVERTED] accepted but no change"},'
        '"execution":{"state_changed":false}}\n'
    )
    obs = agent_observation_from_command(
        "commit_tactic", ["sh", "-c", "inline PRPc.PseudoRP.fi."],
        stdout=stdout, stderr="", exit_code=1,
    )
    assert "NO PROGRESS" in obs["result"] and "no-op" in obs["result"]
    assert "use the error summary" not in obs["result"].lower()
    assert obs.get("error_summary") is None   # no error invented
    assert obs["proof_state"] == "The committed EasyCrypt proof state was not changed."


def test_daemon_rejected_commit_surfaces_structured_error_field():
    # A daemon rejection carries the clean reason in result.error / result.failure_reason
    # (no `error_excerpt:`/`errors` structure). These were never read, so a
    # `[DAEMON_REJECTED]` commit landed error_summary=None and the agent was told to
    # "use the error summary" with none present (root-caused by EC replay, L1 2026-06-06).
    stdout = (
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":false,"result":{"ok":false,"status":"error",'
        '"error":"[error] unknown procedure: PseudoRP.fi",'
        '"failure_reason":"[error] unknown procedure: PseudoRP.fi"},'
        '"execution":{"state_changed":false}}\n'
    )
    obs = agent_observation_from_command(
        "commit_tactic", ["sh", "-c", "inline PseudoRP.fi."],
        stdout=stdout, stderr="", exit_code=1)
    assert obs.get("error_summary") == "[error] unknown procedure: PseudoRP.fi"


def test_daemon_rejected_marker_in_raw_excerpt_is_recovered():
    # When only the `[DAEMON_REJECTED] <reason>` line is present (no structured field),
    # recover the reason from it rather than dropping the error.
    from workflow.proof_management.backend_actions import _error_summary
    payload = {"result": {"ok": False, "status": "error", "raw_excerpt":
        "==[ L0 ]==\n[DAEMON_REJECTED] conseq: not a phl/prhl judgement\n  EC daemon rejected"}}
    assert _error_summary(payload, "", ok=False) == "conseq: not a phl/prhl judgement"


def test_accepted_commit_never_gets_a_spurious_error_summary():
    # The fallback is gated on `not ok`: a successful commit must never pick up an
    # error_summary from a stray earlier envelope.
    stdout = (
        '{"kind":"agent_view","ok":false,"errors":[{"message":"[error] stale"}]}\n'
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":true,"status":"accepted","execution":{"state_changed":true}}\n'
    )
    obs = agent_observation_from_command(
        "commit_tactic",
        ["sh", "-c", "proc."],
        stdout=stdout,
        stderr="",
        exit_code=0,
    )
    assert "error_summary" not in obs
