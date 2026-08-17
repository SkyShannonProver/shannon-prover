#!/usr/bin/env python3
"""Unit tests for the agent-view run report bundle (pure parts).

No EasyCrypt / live run needed: tests the committed-proof reconstruction, the
proof-block rendering, and the link relativization (so the committed bundle has
no machine-specific /Users paths and every view link resolves).

Run: python3 -m pytest tests/test_run_report_bundle.py -q
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation import run_report_bundle as rb  # noqa: E402
from workflow.schemas.prover_result import (  # noqa: E402
    PROVER_RUN_INCOMPLETE,
    PROVER_RUN_INFRASTRUCTURE_INVALID,
    PROVER_RUN_VERIFIED,
    ProverResult,
)


def _write_terminal_result(
    iteration: Path,
    status: str,
) -> ProverResult:
    result = ProverResult(
        status=status,
        verification=(
            {"status": "pass", "method": "test_fixture"}
            if status == PROVER_RUN_VERIFIED
            else {}
        ),
        infrastructure_errors=(
            ["test infrastructure failure"]
            if status == PROVER_RUN_INFRASTRUCTURE_INVALID
            else []
        ),
    )
    result.save(iteration / "prover_run_result.json")
    return result


def _make_run(tmp: Path, tree: str, intents: list[tuple[str, str, bool]]) -> Path:
    """intents: (intent_name, tactic, ok) → write a node timeline.jsonl."""
    node = tmp / "node_memory" / tree
    node.mkdir(parents=True, exist_ok=True)
    with (node / "timeline.jsonl").open("w") as f:
        for i, (name, tac, ok) in enumerate(intents):
            payload = {"tactic": tac} if tac else {}
            f.write(json.dumps({
                "turn": i, "ok": ok,
                "intent": {"intent": name, "payload": payload},
            }) + "\n")
    return tmp


def test_committed_proofs_incomplete():
    with tempfile.TemporaryDirectory() as d:
        run = _make_run(Path(d), "Tree_0_0", [
            ("tactic_forms", "congr", True),
            ("commit_tactic", "congr.", True),
            ("commit_tactic", "byequiv=> //.", True),
            ("commit_tactic", "oops.", False),       # rejected → excluded
        ])
        proofs = rb._committed_proofs(run)
        assert len(proofs) == 1
        assert proofs[0]["tree"] == "Tree_0_0"
        assert proofs[0]["tactics"] == ["congr.", "byequiv=> //."]
        assert proofs[0]["session_closed"] is False


def test_committed_proofs_proved_via_qed_and_finish():
    with tempfile.TemporaryDirectory() as d:
        run = _make_run(Path(d), "Tree_0_0", [
            ("commit_tactic", "sim.", True),
            ("commit_tactic", "qed.", True),
            ("finish", "", True),
        ])
        p = rb._committed_proofs(run)[0]
        assert p["tactics"] == ["sim.", "qed."]
        assert p["session_closed"] is True


def test_render_proof_section_incomplete_vs_proved():
    incomplete = rb._render_proof_section(
        [{"tree": "Tree_0_0", "tactics": ["congr.", "proc."], "session_closed": False}])
    assert "```easycrypt" in incomplete
    assert "proof." in incomplete and "congr." in incomplete and "proc." in incomplete
    assert "not completed" in incomplete
    assert "incomplete" in incomplete

    proved = rb._render_proof_section(
        [{"tree": "Tree_0_0", "tactics": ["sim.", "qed."], "session_closed": True}])
    assert proved.count("qed.") == 1   # already ends in qed; not double-added
    assert "session closed" in proved

    # The renderer NEVER fabricates a closing `qed.`: an unclosed body is
    # annotated, not given a fake qed (see `_render_proof_section`).
    proved_no_qed = rb._render_proof_section(
        [{"tree": "Tree_0_0", "tactics": ["trivial."], "session_closed": True}])
    assert proved_no_qed.count("qed.") == 0
    assert "not completed" in proved_no_qed


def test_rewrite_links_relativizes_and_no_user_leak():
    repo = str(rb._REPO_ROOT)
    md = (
        f"[turn_001.json]({repo}/artifacts/x/iteration_1/node_memory/Tree_0_0/"
        "workspace_views/turn_001.json)\n"
        f"[turn_001.json]({repo}/a/node_memory/Tree_0_1/manager_results/turn_001.json)\n"
        f"[manager_bootstrap_0_0.json]({repo}/a/iteration_1/manager_bootstrap_0_0.json)\n"
        f"[initial_workspace_view.json]({repo}/a/node_memory/Tree_0_0/"
        "initial_workspace_view.json)\n"
        f"[inline read]({repo}/a/node_memory/Tree_0_0/initial_followup.md)\n"
        f"[launch task]({repo}/a/node_memory/Tree_0_0/initial_agent_prompt.md)\n"
        f"Run dir: `{repo}/artifacts/x/iteration_1`\n"
    )
    out = rb._rewrite_links(md)
    assert "](./views/Tree_0_0/turn_001.json)" in out
    assert "](./views/Tree_0_1/manager_results/turn_001.json)" in out
    assert "](./views/_bootstrap/manager_bootstrap_0_0.json)" in out
    assert "](./views/Tree_0_0/initial_workspace_view.json)" in out
    assert "](./views/Tree_0_0/initial_followup.md)" in out
    assert "](./views/Tree_0_0/initial_agent_prompt.md)" in out
    assert repo not in out               # no machine-specific absolute path leaks


def test_rewrite_links_relativizes_thinking_views():
    repo = str(rb._REPO_ROOT)
    md = (
        f"[13.9 s]({repo}/artifacts/x/iteration_1/node_memory/Tree_0_0/"
        "thinking/turn_003.md)\n"
        f"[think]({repo}/a/node_memory/Tree_0_1/thinking/turn_001.md)\n"
    )
    out = rb._rewrite_links(md)
    assert "](./views/Tree_0_0/thinking/turn_003.md)" in out
    assert "](./views/Tree_0_1/thinking/turn_001.md)" in out
    assert repo not in out


def test_scrub_paths_removes_repo_and_home_paths():
    repo = str(rb._REPO_ROOT)
    text = (
        f"{repo}/artifacts/x/iteration_1/node_memory/Tree_0_0/foo.json | "
        "/Users/somebody/tmp/cmp_cur/ChaChaPoly/chacha_poly.ec | "
        "/home/ci/work/run/y.json"
    )
    out = rb._scrub_paths(text)
    assert repo not in out
    assert "/Users/" not in out and "/home/" not in out          # no machine leak
    assert "artifacts/x/iteration_1/node_memory/Tree_0_0/foo.json" in out  # repo-relative
    assert "~/tmp/cmp_cur/ChaChaPoly/chacha_poly.ec" in out       # home reduced to ~/
    assert "~/work/run/y.json" in out


def test_copy_json_scrubbed_strips_machine_paths_and_stays_valid_json(tmp_path):
    # This is the path the committed bundle's JSON/bootstrap go through; the
    # earlier bug applied link-rewriting to markdown only, so JSON leaked /Users.
    src = tmp_path / "boot.json"
    src.write_text(json.dumps({
        "source_file": f"{rb._REPO_ROOT}/tmp/cmp/x.ec",
        "include": "/Users/someone/easycrypt-src/theories",
    }))
    dst = tmp_path / "out.json"
    rb._copy_json_scrubbed(src, dst)
    text = dst.read_text()
    assert "/Users/" not in text and str(rb._REPO_ROOT) not in text
    obj = json.loads(text)               # still valid JSON
    assert obj["source_file"] == "tmp/cmp/x.ec"
    assert obj["include"] == "~/easycrypt-src/theories"


def test_copy_views_includes_authoritative_initial_launch_artifacts(tmp_path):
    run_iter = tmp_path / "run" / "iteration_1"
    node = run_iter / "node_memory" / "Tree_0_0"
    node.mkdir(parents=True)
    (node / "initial_workspace_view.json").write_text(
        json.dumps({"current_goal": {"lines": ["goal"]}}),
        encoding="utf-8",
    )
    (node / "initial_followup.md").write_text(
        "submit move=> x.", encoding="utf-8",
    )
    (node / "initial_agent_prompt.md").write_text(
        "authoritative launch task: submit move=> x.", encoding="utf-8",
    )

    views = tmp_path / "views"
    assert rb._copy_views(run_iter, views) == 0

    copied = views / "Tree_0_0"
    assert json.loads(
        (copied / "initial_workspace_view.json").read_text(encoding="utf-8")
    )["current_goal"]["lines"] == ["goal"]
    assert (copied / "initial_followup.md").read_text(encoding="utf-8") == (
        "submit move=> x."
    )
    assert "authoritative launch task" in (
        copied / "initial_agent_prompt.md"
    ).read_text(encoding="utf-8")


def _make_chunk(base: Path, intents, *, resume_from=None, session_lines=None,
                capsule_prefix=None, tree="Tree_0_0"):
    """A run chunk: <base>/config.json + <base>/iter/node_memory/... (+ optional
    ec_sessions history.ec and a resume capsule). Returns the iteration dir."""
    iter_dir = base / "iter"
    _make_run(iter_dir, tree, intents)
    # a minimal per-turn view so the bundle has something to copy/namespace
    vdir = iter_dir / "node_memory" / tree / "workspace_views"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "turn_000.json").write_text(json.dumps({"current_goal": {"lines": []}}))
    source = base / "target.ec"
    source.write_text("lemma lem : true.\n", encoding="utf-8")
    cfg = {
        "file": str(source.resolve()),
        "lemma": "lem",
        "resume_capsules": [str(resume_from)] if resume_from else [],
    }
    (base / "config.json").write_text(json.dumps(cfg))
    if session_lines is not None:
        sess = iter_dir / "ec_sessions" / (".ec_session_prover_" + tree.lower())
        sess.mkdir(parents=True, exist_ok=True)
        (sess / "session_meta.json").write_text(json.dumps({
            "file": str(source.resolve()),
            "lemma": "lem",
        }))
        (sess / "history.ec").write_text("\n".join(session_lines) + "\n")
    if capsule_prefix is not None:
        cap = iter_dir / "resume_capsules" / (tree + "_sess")
        cap.mkdir(parents=True, exist_ok=True)
        (cap / "resume.json").write_text(json.dumps({"kind": "resume"}))
        (cap / "history.ec").write_text("\n".join(capsule_prefix) + "\n")
    return iter_dir


def test_resolve_lineage_walks_capsule_chain(tmp_path):
    c0 = _make_chunk(tmp_path / "c0",
                     [("commit_tactic", "move=> H.", True)],
                     capsule_prefix=["move=> H.", "byequiv => //."])
    cap = c0 / "resume_capsules" / "Tree_0_0_sess" / "resume.json"
    c1 = _make_chunk(tmp_path / "c1",
                     [("commit_tactic", "sim.", True),
                      ("commit_tactic", "qed.", True)],
                     resume_from=cap)
    chain = rb._resolve_lineage(c1)
    assert chain == [c0, c1]                       # ordered root→leaf
    assert rb._resolve_lineage(c0) == [c0]         # fresh run = singleton


def test_build_bundle_stitches_resume_lineage_end_to_end(tmp_path):
    # chunk0 contributes a 2-tactic prefix (captured in its resume capsule);
    # chunk1 resumes from it and closes. The leaf's session history.ec is the
    # cumulative ground truth (prefix + new, undos applied).
    c0 = _make_chunk(tmp_path / "c0",
                     [("commit_tactic", "move=> H.", True)],
                     capsule_prefix=["move=> H.", "byequiv => //."])
    cap = c0 / "resume_capsules" / "Tree_0_0_sess" / "resume.json"
    c1 = _make_chunk(
        tmp_path / "c1",
        [("commit_tactic", "sim.", True), ("commit_tactic", "qed.", True)],
        resume_from=cap,
        session_lines=["move=> H.", "byequiv => //.", "sim.", "qed."])

    dest = rb.build_bundle(c1, dest_root=str(tmp_path / "out"),
                           timestamp="2026-01-02_0000_lem", lemma="lem")
    assert dest is not None
    meta = json.loads((dest / "run_meta.json").read_text())
    assert meta["resume_chunks"] == 2
    assert meta["committed_proof_source"] == "session"   # EC ground truth
    assert meta["committed_proof_tree"] == "Tree_0_0"
    assert meta["outcome"] == "session_closed (terminal result unavailable)"

    md = (dest / "timeline_report.md").read_text()
    assert "end-to-end across 2 resume chunks" in md
    assert "resume 1: replayed 2 tactic" in md          # boundary at capsule prefix
    # full move=>…qed stitched: chunk0 prefix AND chunk1 suffix both present
    assert "move=> H." in md and "byequiv => //." in md and "sim." in md
    assert md.count("qed.") >= 1
    # per-chunk view namespacing
    assert (dest / "views" / "c0").is_dir()
    assert (dest / "views" / "c1").is_dir()


def test_build_bundle_no_follow_resume_is_single_chunk(tmp_path):
    c0 = _make_chunk(tmp_path / "c0",
                     [("commit_tactic", "move=> H.", True)],
                     capsule_prefix=["move=> H."])
    cap = c0 / "resume_capsules" / "Tree_0_0_sess" / "resume.json"
    c1 = _make_chunk(tmp_path / "c1",
                     [("commit_tactic", "qed.", True)], resume_from=cap)
    dest = rb.build_bundle(c1, dest_root=str(tmp_path / "out"),
                           timestamp="2026-01-03_0000_lem", lemma="lem",
                           follow_resume=False)
    meta = json.loads((dest / "run_meta.json").read_text())
    assert "resume_chunks" not in meta                  # single-run bundle only


def test_session_history_preferred_over_timeline_for_undone_tactics(tmp_path):
    # The timeline keeps rewound commits; the session history.ec does not. The
    # rendered proof must reflect EC's accepted script, not the raw ok-commits.
    run = _make_chunk(
        tmp_path / "r",
        [("commit_tactic", "move=> H.", True),
         ("commit_tactic", "wrong_branch.", True),     # later rewound
         ("undo_to_checkpoint", "", True)],
        session_lines=["move=> H.", "sim.", "qed."])
    proofs = rb._committed_proofs(run)
    section = rb._render_proof_section(proofs, run)
    assert "wrong_branch." not in section              # rewound tactic excluded
    assert "sim." in section and section.count("qed.") == 1


def test_append_index_is_idempotent_per_bundle(tmp_path):
    # Two callers (orchestrator + suite runner) or a re-bundle must not produce
    # duplicate INDEX rows for the same run, but must refresh the row in place.
    run = tmp_path / "iter"
    _make_run(run, "Tree_0_0", [("commit_tactic", "qed.", True)])
    kw = dict(dest_root=str(tmp_path / "out"),
              timestamp="2026-01-04_0000_x", lemma="x")
    rb.build_bundle(run, **kw)
    rb.build_bundle(run, **kw)                     # rebuild same run
    index = (tmp_path / "out" / "INDEX.md").read_text()
    assert index.count("/timeline_report.md)") == 1   # exactly one row
    assert "| time | lemma | commit | outcome | turns | report |" in index  # header intact


def test_suite_bundle_keys_prevent_same_minute_arm_collisions(tmp_path):
    run_a = tmp_path / "a" / "iteration_1"
    run_b = tmp_path / "b" / "iteration_1"
    _make_run(run_a, "Tree_0_0", [("commit_tactic", "proc.", True)])
    _make_run(run_b, "Tree_0_0", [("commit_tactic", "wp.", True)])
    environment = {
        "commit": "abc12345",
        "commit_full": "abc12345" + "0" * 32,
        "branch": "codex/test",
        "dirty": False,
    }

    a = rb.build_bundle(
        run_a,
        dest_root=str(tmp_path / "out"),
        timestamp="2026-08-05_0743_step2_1",
        lemma="step2_1",
        profile="audit",
        bundle_key="row-a__audit__r01",
        environment=environment,
    )
    b = rb.build_bundle(
        run_b,
        dest_root=str(tmp_path / "out"),
        timestamp="2026-08-05_0743_step2_1",
        lemma="step2_1",
        profile="treatment",
        bundle_key="row-a__treatment__r01",
        environment=environment,
    )

    assert a is not None and b is not None and a != b
    assert "dirty" not in a.name and "dirty" not in b.name
    assert json.loads((a / "run_meta.json").read_text())["surface_profile"] == (
        "audit"
    )
    assert json.loads((b / "run_meta.json").read_text())["surface_profile"] == (
        "treatment"
    )


# ---------------------------------------------------------------------------
# Faithful committed-proof reconstruction (regression for the step4_1 L4
# respawn bundle 2026-06-08_2246: run_meta committed_proofs kept undone admits
# and EC-rejected commits, and dropped respawned nodes' replay prefixes).
# The row shapes below mirror the real timeline.jsonl of that run.
# ---------------------------------------------------------------------------

def _ma_commit_ok():
    return [{"action": "tactic commit",
             "outcome": "EasyCrypt accepted the committed tactic.",
             "timing": "1 s"}]


def _ma_commit_rejected():
    # NOTE: the row-level `ok` stays True for these — only the manager action's
    # error_summary says EasyCrypt rejected the commit.
    return [{"action": "tactic commit",
             "error_summary": "[error] invalid arguments",
             "outcome": "EasyCrypt rejected the committed tactic. Use the error "
                        "summary and current goal to revise the proof step.",
             "timing": "1 s"}]


def _ma_commit_autoreverted():
    return [{"action": "tactic commit",
             "error_summary": "text-equal",
             "outcome": "NO PROGRESS — EasyCrypt ACCEPTED this commit but it did "
                        "not change the goal, so nothing was committed (it "
                        "auto-reverts).",
             "timing": "1 s"}]


def _ma_undo():
    return [{"action": "undo",
             "outcome": "The manager completed this proof-level request.",
             "timing": "1.5 s"}]


def _ma_checkpoint_menu():
    return [{"action": "checkpoint menu",
             "outcome": "Choose the committed tactic you want to rewind before."}]


def _write_timeline(run: Path, tree: str, rows: list[dict]) -> Path:
    """Write a node timeline with full real-shape rows (bootstrap row first)."""
    node = run / "node_memory" / tree
    node.mkdir(parents=True, exist_ok=True)
    with (node / "timeline.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return run


def _write_bound_session(run: Path, tree: str, lines: list[str]) -> Path:
    source = run.parent / "target.ec"
    source.write_text("lemma lem : true.\n", encoding="utf-8")
    (run.parent / "config.json").write_text(json.dumps({
        "file": str(source.resolve()),
        "lemma": "lem",
    }))
    session = run / "ec_sessions" / (".ec_session_prover_" + tree.lower())
    session.mkdir(parents=True, exist_ok=True)
    (session / "session_meta.json").write_text(json.dumps({
        "file": str(source.resolve()),
        "lemma": "lem",
    }))
    (session / "history.ec").write_text("\n".join(lines) + "\n")
    return session


def _boot_row(prefix_count: int = 0) -> dict:
    return {"kind": "bootstrap", "replay_prefix_count": prefix_count}


def _turn(intent: str, tactic: str = "", *, ok: bool = True, actions=None) -> dict:
    payload = {"tactic": tactic} if tactic else {}
    row = {"intent": {"intent": intent, "payload": payload}, "ok": ok}
    if actions is not None:
        row["manager_actions"] = actions
    return row


def test_committed_proofs_applies_undo_last_step(tmp_path):
    # Tree_0_1 shape from the regression bundle: admit/rewrite/smt committed
    # then rewound via 3 accepted undo_last_step turns (after a checkpoint
    # MENU, which must NOT itself rewind anything). The reconstructed proof
    # must equal what the child respawn bootstrap later replayed: no admit.
    run = _write_timeline(tmp_path / "iter", "Tree_0_1", [
        _boot_row(),
        _turn("commit_tactic", "apply (ler_trans X).", actions=_ma_commit_ok()),
        _turn("commit_tactic", "admit.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "rewrite Pr [mu_or].", actions=_ma_commit_ok()),
        _turn("commit_tactic", "smt(ge0_mu).", actions=_ma_commit_ok()),
        _turn("undo_to_checkpoint", actions=_ma_checkpoint_menu()),  # menu only
        _turn("undo_last_step", actions=_ma_undo()),
        _turn("undo_last_step", actions=_ma_undo()),
        _turn("undo_last_step", actions=_ma_undo()),
        _turn("commit_tactic", "byequiv (_: ={glob A} ==> P).",
              actions=_ma_commit_ok()),
        _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
    ])
    p = rb._committed_proofs(run)[0]
    assert p["source"] == "timeline_replay"
    assert p["tactics"] == [
        "apply (ler_trans X).", "byequiv (_: ={glob A} ==> P).", "proc."]
    assert "admit." not in p["tactics"]
    assert p["session_closed"] is False
    assert "approximate" not in p


def test_committed_proofs_excludes_rejected_and_autoreverted_ok_rows(tmp_path):
    # EC-rejected and auto-reverted (no-op) commits keep row ok=True in the
    # real timeline; only the manager action's error_summary tells the truth.
    run = _write_timeline(tmp_path / "iter", "Tree_0_0", [
        _boot_row(),
        _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "inline{1} (1).", actions=_ma_commit_rejected()),
        _turn("commit_tactic", "sim.", actions=_ma_commit_rejected()),
        _turn("commit_tactic", "wp.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "inline{1} 1.", actions=_ma_commit_autoreverted()),
    ])
    p = rb._committed_proofs(run)[0]
    assert p["tactics"] == ["proc.", "wp."]


def test_committed_proofs_respawn_includes_bootstrap_prefix(tmp_path):
    # A respawned node replays the parent's final committed history as its
    # bootstrap replay_prefix before its first own turn; the reconstruction
    # must include it (run_meta previously listed only the node's own commits).
    run = tmp_path / "iter"
    prefix = ["apply (ler_trans X).", "byequiv (_: ={glob A} ==> P).", "proc."]
    _write_timeline(run, "Tree_0_1_r2", [
        _boot_row(prefix_count=len(prefix)),
        _turn("commit_tactic", "wp.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "skip => />.", actions=_ma_commit_ok()),
    ])
    (run / "manager_bootstrap_0_1_r2.json").write_text(json.dumps({
        "node": "Tree-0.1.r2", "replay_prefix": prefix,
        "replay_prefix_count": len(prefix)}))
    p = rb._committed_proofs(run)[0]
    assert p["tactics"] == prefix + ["wp.", "skip => />."]
    assert p["replay_prefix_count"] == 3
    assert "approximate" not in p


def test_committed_proofs_parent_final_matches_child_bootstrap_prefix(tmp_path):
    # The cross-validation invariant from the regression bundle: the parent's
    # reconstructed committed history must equal the replay_prefix the
    # orchestrator bootstrapped the child respawn node with.
    run = tmp_path / "iter"
    _write_timeline(run, "Tree_0_1", [
        _boot_row(),
        _turn("commit_tactic", "apply (ler_trans X).", actions=_ma_commit_ok()),
        _turn("commit_tactic", "admit.", actions=_ma_commit_ok()),
        _turn("undo_last_step", actions=_ma_undo()),
        _turn("commit_tactic", "byequiv (_: ={glob A} ==> P).",
              actions=_ma_commit_rejected()),
        _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
    ])
    parent_final = ["apply (ler_trans X).", "proc."]
    _write_timeline(run, "Tree_0_1_r2", [
        _boot_row(prefix_count=len(parent_final)),
        _turn("commit_tactic", "wp.", actions=_ma_commit_ok()),
    ])
    (run / "manager_bootstrap_0_1_r2.json").write_text(json.dumps({
        "replay_prefix": parent_final, "replay_prefix_count": len(parent_final)}))
    proofs = {p["tree"]: p for p in rb._committed_proofs(run)}
    assert proofs["Tree_0_1"]["tactics"] == parent_final
    assert (proofs["Tree_0_1"]["tactics"]
            == rb._bootstrap_prefix_lines(run, "Tree_0_1_r2"))
    assert proofs["Tree_0_1_r2"]["tactics"] == parent_final + ["wp."]


def test_committed_proofs_missing_bootstrap_file_marks_approximate(tmp_path):
    # The bootstrap row says a prefix was replayed but the bootstrap file (and
    # session) are gone: the reconstruction cannot recover the prefix and must
    # say so instead of silently presenting a truncated proof as complete.
    run = _write_timeline(tmp_path / "iter", "Tree_0_0_r2", [
        _boot_row(prefix_count=5),
        _turn("commit_tactic", "wp.", actions=_ma_commit_ok()),
    ])
    p = rb._committed_proofs(run)[0]
    assert p["tactics"] == ["wp."]
    assert p["approximate"] is True


def test_committed_proofs_prefers_exact_session_history(tmp_path):
    # When the tree's own history.ec survives it wins over the timeline replay
    # (it also captures in-flight commits a killed run never logged).
    run = _write_timeline(tmp_path / "iter", "Tree_0_0", [
        _boot_row(),
        _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
    ])
    _write_bound_session(run, "Tree_0_0", ["proc.", "wp."])
    p = rb._committed_proofs(run)[0]
    assert p["source"] == "session"
    assert p["tactics"] == ["proc.", "wp."]


def test_committed_proofs_never_reads_stale_worktree_root_session(tmp_path):
    # Suite members reuse Tree_0_0.  A zero-turn/current run without an archived
    # session must not inherit a same-named session left by an earlier target in
    # the worktree root (the 2026-08-05 step2_1/CMAC bundle contamination).
    run = _write_timeline(
        tmp_path / "artifacts" / "suite" / "run" / "iteration_1",
        "Tree_0_0",
        [
            _boot_row(),
            _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
        ],
    )
    stale = tmp_path / ".ec_session_prover_tree_0_0"
    stale.mkdir()
    (stale / "history.ec").write_text(
        "inline RP_RF1.ARP.init F.init.\nforeign_target_tactic.\n",
        encoding="utf-8",
    )

    proof = rb._committed_proofs(run)[0]

    assert proof["source"] == "timeline_replay"
    assert proof["tactics"] == ["proc."]
    assert "RP_RF1" not in "\n".join(proof["tactics"])


def test_committed_proofs_rejects_mismatched_confined_session_meta(tmp_path):
    run = _write_timeline(
        tmp_path / "run" / "iteration_1",
        "Tree_0_0",
        [
            _boot_row(),
            _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
        ],
    )
    session = _write_bound_session(run, "Tree_0_0", ["foreign_tactic."])
    meta = json.loads((session / "session_meta.json").read_text())
    meta["lemma"] = "different_target"
    (session / "session_meta.json").write_text(json.dumps(meta))

    proof = rb._committed_proofs(run)[0]

    assert proof["source"] == "timeline_replay"
    assert proof["tactics"] == ["proc."]


def test_committed_proofs_torn_history_falls_back_to_timeline(tmp_path):
    # A run killed mid-`undo_to_checkpoint` rewind leaves history.ec mid-rewrite
    # (observed: a 45-commit node with a 1-line history.ec). The torn file is a
    # strict proper prefix of the faithful timeline replay — the replay must win
    # (commits append to history BEFORE the timeline row, so the replay can
    # never legitimately be ahead of an intact history).
    run = _write_timeline(tmp_path / "iter", "Tree_0_1_r2", [
        _boot_row(),
        _turn("commit_tactic", "move=> hn.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "byequiv (_: P ==> Q).", actions=_ma_commit_ok()),
        _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
        _turn("undo_to_checkpoint", actions=_ma_checkpoint_menu()),
    ])
    sess = _write_bound_session(run, "Tree_0_1_r2", ["move=> hn."])
    p = rb._committed_proofs(run)[0]
    assert p["source"] == "timeline_replay"
    assert p["tactics"] == ["move=> hn.", "byequiv (_: P ==> Q).", "proc."]

    # but a DIVERGING history (e.g. session epoch repair dropped a line) is
    # still EC ground truth and must stay preferred
    (sess / "history.ec").write_text("move=> hn.\nproc.\n")  # not a prefix
    p = rb._committed_proofs(run)[0]
    assert p["source"] == "session"
    assert p["tactics"] == ["move=> hn.", "proc."]


def test_outcome_not_fooled_by_rejected_or_undone_qed(tmp_path):
    # qed. rejected by EC (row ok=True!) → not proved; qed. then undone → not
    # proved; accepted final qed. → proved.
    rejected = _write_timeline(tmp_path / "a", "Tree_0_0", [
        _boot_row(),
        _turn("commit_tactic", "qed.", actions=_ma_commit_rejected()),
    ])
    assert rb._outcome(rejected) == "incomplete (timeout/open)"

    undone = _write_timeline(tmp_path / "b", "Tree_0_0", [
        _boot_row(),
        _turn("commit_tactic", "trivial.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "qed.", actions=_ma_commit_ok()),
        _turn("undo_last_step", actions=_ma_undo()),
    ])
    assert rb._outcome(undone) == "incomplete (timeout/open)"

    proved = _write_timeline(tmp_path / "c", "Tree_0_0", [
        _boot_row(),
        _turn("commit_tactic", "trivial.", actions=_ma_commit_ok()),
        _turn("commit_tactic", "qed.", actions=_ma_commit_ok()),
    ])
    assert rb._outcome(proved) == "session_closed (terminal result unavailable)"


def test_outcome_consumes_only_canonical_terminal_result(tmp_path):
    # Session history is diagnostic only. The terminal ProverResult decides
    # whether the run is verified, incomplete, or infrastructure-invalid.
    def _proved_run(base: Path) -> Path:
        return _write_timeline(base / "iteration_1", "Tree_0_1", [
            _boot_row(),
            _turn("commit_tactic", "by rewrite addK.", actions=_ma_commit_ok()),
            _turn("commit_tactic", "qed.", actions=_ma_commit_ok()),
        ])

    reverted = _proved_run(tmp_path / "a")
    _write_terminal_result(reverted, PROVER_RUN_INFRASTRUCTURE_INVALID)
    assert rb._outcome(reverted) == "infrastructure_invalid"

    confirmed = _proved_run(tmp_path / "b")
    _write_terminal_result(confirmed, PROVER_RUN_VERIFIED)
    assert rb._outcome(confirmed) == "verified"

    # No terminal artifact never upgrades a session close to verified.
    assert rb._outcome(_proved_run(tmp_path / "c")) == (
        "session_closed (terminal result unavailable)"
    )

    # An unproved session stays "incomplete" regardless of the summary.
    incomplete = _write_timeline(tmp_path / "d" / "iteration_1", "Tree_0_0", [
        _boot_row(),
        _turn("commit_tactic", "trivial.", actions=_ma_commit_ok()),
    ])
    _write_terminal_result(incomplete, PROVER_RUN_INCOMPLETE)
    assert rb._outcome(incomplete) == "incomplete (timeout/open)"


def test_build_bundle_run_meta_committed_proofs_are_faithful(tmp_path):
    # End-to-end: run_meta.json's committed_proofs (the committed artifact the
    # regression was filed against) reflects undos, rejected commits, and the
    # respawn prefix; the rendered proof block matches.
    run = tmp_path / "iter"
    _write_timeline(run, "Tree_0_1", [
        _boot_row(),
        _turn("commit_tactic", "apply (ler_trans X).", actions=_ma_commit_ok()),
        _turn("commit_tactic", "admit.", actions=_ma_commit_ok()),
        _turn("undo_last_step", actions=_ma_undo()),
        _turn("commit_tactic", "proc.", actions=_ma_commit_ok()),
    ])
    _write_timeline(run, "Tree_0_1_r2", [
        _boot_row(prefix_count=2),
        _turn("commit_tactic", "wp.", actions=_ma_commit_ok()),
    ])
    (run / "manager_bootstrap_0_1_r2.json").write_text(json.dumps({
        "replay_prefix": ["apply (ler_trans X).", "proc."],
        "replay_prefix_count": 2}))
    dest = rb.build_bundle(run, dest_root=str(tmp_path / "out"),
                           timestamp="2026-06-09_0000_x", lemma="x")
    assert dest is not None
    meta = json.loads((dest / "run_meta.json").read_text())
    proofs = {p["tree"]: p for p in meta["committed_proofs"]}
    assert proofs["Tree_0_1"]["tactics"] == ["apply (ler_trans X).", "proc."]
    assert proofs["Tree_0_1_r2"]["tactics"] == [
        "apply (ler_trans X).", "proc.", "wp."]
    md = (dest / "timeline_report.md").read_text()
    assert "admit." not in md.split("## Agent's committed proof")[1].split("---")[0]


def test_build_bundle_derives_tree_count_from_node_dirs(tmp_path):
    # When the caller does not pass `trees` (the suite config often omits it),
    # the bundle must report the real topology = the number of Tree_* node dirs
    # that actually ran, not "?" / null.
    run = tmp_path / "iter"
    _make_run(run, "Tree_0_0", [("commit_tactic", "sim.", True)])
    _make_run(run, "Tree_0_1", [("commit_tactic", "congr.", True)])
    dest = rb.build_bundle(
        run, dest_root=str(tmp_path / "out"),
        timestamp="2026-01-01_0000_x", lemma="x")
    assert dest is not None
    meta = json.loads((dest / "run_meta.json").read_text())
    assert meta["trees"] == 2
    assert "| trees | 2 |" in (dest / "timeline_report.md").read_text()
