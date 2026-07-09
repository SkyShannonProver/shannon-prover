"""Build a committed, self-contained agent-view report bundle for one prover run.

After every prover run we want a *fixed-location*, GitHub-uploadable bundle that
lets a human click through, step by step, exactly what view the agent saw and
what it did — the same kind of timeline table produced by
``agent_view_timeline_report`` — plus the environment it ran in (git commit,
time, lemma, model, profile, …).

Run artifacts live under gitignored ``artifacts/`` / ``workflow/runs/``, and the
timeline report links views by absolute path (not portable). This module fixes
both: it copies the per-turn views into the bundle and rewrites the report's
view links to point at those local copies, so the whole thing is committable and
the links resolve on GitHub.

Layout (under ``dest_root``, default ``agent_view_runs/`` at repo root):

    agent_view_runs/
      INDEX.md                                  # running index of all bundles
      <lemma>/<TS>__<commit8>[-dirty]/
        timeline_report.md                      # env header + clickable table
        timeline_report.json
        run_meta.json
        views/<Tree_x_y>/turn_NNN.json          # copied per-turn agent views

Usage (also hooked into eval_suite.run / orchestrator post-run):
    python3 -m workflow.validation.run_report_bundle <run_iteration_dir> \
        [--dest-root agent_view_runs] [--lemma L] [--model M] [--profile P] ...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Rewrite the timeline report's absolute artifact links → local bundle copies so
# every link resolves on GitHub (and no machine-specific /Users path leaks).
_LINK_VIEW = re.compile(
    r"\]\((?:[^)]*?/)?node_memory/(?P<tree>Tree_[A-Za-z0-9_]+)/"
    r"workspace_views/(?P<turn>turn_\d+\.json)\)")
_LINK_RESULT = re.compile(
    r"\]\((?:[^)]*?/)?node_memory/(?P<tree>Tree_[A-Za-z0-9_]+)/"
    r"manager_results/(?P<turn>turn_\d+\.json)\)")
_LINK_BOOTSTRAP = re.compile(
    r"\]\((?:[^)]*?/)?(?P<boot>manager_bootstrap_[A-Za-z0-9_]+\.json)\)")
_LINK_THINKING = re.compile(
    r"\]\((?:[^)]*?/)?node_memory/(?P<tree>Tree_[A-Za-z0-9_]+)/"
    r"thinking/(?P<turn>turn_\d+\.md)\)")
_LINK_FOLLOWUP = re.compile(
    r"\]\((?:[^)]*?/)?node_memory/(?P<tree>Tree_[A-Za-z0-9_]+)/"
    r"followups/(?P<turn>turn_\d+\.md)\)")


# Machine-specific home-dir paths that may survive repo-relativization (e.g. a
# scrubbed-source copy living under a tmp dir outside the repo root).
_HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s\"']+/")


def _scrub_paths(text: str) -> str:
    """Strip machine-specific absolute paths so committed artifacts are portable
    and leak no ``/Users/<name>`` path: repo paths become repo-relative, and any
    other absolute home path is reduced to ``~/``."""
    return _HOME_PATH.sub("~/", text.replace(str(_REPO_ROOT) + "/", ""))


def _scrub_json_file(path: Path) -> None:
    """Rewrite a JSON file in place with machine paths scrubbed (no-op on error
    or if unchanged). Path strings are plain JSON string values, so the
    substring scrub keeps the document valid."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return
    scrubbed = _scrub_paths(raw)
    if scrubbed != raw:
        path.write_text(scrubbed, encoding="utf-8")


def _copy_json_scrubbed(src: Path, dst: Path) -> None:
    """Copy a JSON artifact into the committed bundle with machine paths
    scrubbed (falls back to a verbatim copy only if the read fails)."""
    try:
        dst.write_text(_scrub_paths(src.read_text(encoding="utf-8")), encoding="utf-8")
    except Exception:
        shutil.copy2(src, dst)


def _rewrite_links(md: str) -> str:
    md = _LINK_VIEW.sub(r"](./views/\g<tree>/\g<turn>)", md)
    md = _LINK_RESULT.sub(r"](./views/\g<tree>/manager_results/\g<turn>)", md)
    md = _LINK_THINKING.sub(r"](./views/\g<tree>/thinking/\g<turn>)", md)
    md = _LINK_FOLLOWUP.sub(r"](./views/\g<tree>/followups/\g<turn>)", md)
    md = _LINK_BOOTSTRAP.sub(r"](./views/_bootstrap/\g<boot>)", md)
    # Relativize any remaining absolute path (e.g. the report tool's
    # informational "Run dir:" line) so no machine-specific /Users path leaks.
    return _scrub_paths(md)


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:
        return ""


def _env_info() -> dict[str, Any]:
    dirty = bool(_git("status", "--porcelain"))
    return {
        "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
        "commit_full": _git("rev-parse", "HEAD") or "unknown",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        "dirty": dirty,
    }


def _node_dirs(run_iter_dir: Path) -> list[Path]:
    nm = run_iter_dir / "node_memory"
    if not nm.is_dir():
        return []
    return sorted(p for p in nm.iterdir() if p.is_dir() and p.name.startswith("Tree_"))


def _final_proved_from_summary(run_iter_dir: Path) -> bool | None:
    """The orchestrator's final verdict (``final_proved`` in the run's
    ``summary.json``, one level above the iteration dir), or None when the
    summary is absent/unreadable (e.g. bundling mid-run)."""
    try:
        data = json.loads(
            (run_iter_dir.parent / "summary.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("final_proved")
    return value if isinstance(value, bool) else None


def _outcome(run_iter_dir: Path) -> str:
    """Best-effort: proved / timeout-or-open, from the reconstructed proofs.

    Proved only when a tree's reconstructed committed script ENDS in `qed.` —
    a `qed.` that was EC-rejected (the timeline row still has ``ok: true``;
    only ``manager_actions.error_summary`` says it failed) or later undone
    must not count. A bare `finish` is NOT proof of closure (while goals
    remain it is a give-up), so it must not be mislabeled as proved.

    A session-level close is reconciled against the orchestrator's final
    verdict: when ``summary.json`` says ``final_proved: false`` the proof was
    rejected/reverted after the session (e.g. the post-verify admit check),
    so the outcome must not read as a plain "proved".
    """
    session_proved = any(
        proof["proved"] for proof in _committed_proofs(run_iter_dir))
    if not session_proved:
        return "incomplete (timeout/open)"
    if _final_proved_from_summary(run_iter_dir) is False:
        return "proved_in_session (final verification failed)"
    return "proved"


def _bootstrap_prefix_lines(run_iter: Path, tree: str) -> list[str]:
    """The replay prefix a node was bootstrapped with (``replay_prefix`` in
    ``manager_bootstrap_<node>.json``) — for a respawned node this is the
    parent's final committed history, replayed before the node's first turn.
    [] for a fresh root node or when no bootstrap file survives."""
    suffix = tree[len("Tree_"):] if tree.startswith("Tree_") else tree
    try:
        raw = json.loads(
            (run_iter / f"manager_bootstrap_{suffix}.json").read_text(
                encoding="utf-8")).get("replay_prefix")
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [str(t).strip() for t in raw if str(t).strip()]


def _commit_action(row: dict[str, Any]) -> dict[str, Any] | None:
    for action in row.get("manager_actions") or []:
        if isinstance(action, dict) and action.get("action") == "tactic commit":
            return action
    return None


def _has_action(row: dict[str, Any], name: str, *, ok_only: bool = False) -> bool:
    for action in row.get("manager_actions") or []:
        if isinstance(action, dict) and action.get("action") == name:
            if not ok_only or "error_summary" not in action:
                return True
    return False


def _replay_timeline_commits(run_iter: Path, node_dir: Path) -> dict[str, Any] | None:
    """Faithfully replay one node's ``timeline.jsonl`` into its committed script.

    Semantics (validated against session ``history.ec`` ground truth across the
    step4_1 L4 respawn runs — every tree matched exactly):

    - seed with the node's bootstrap ``replay_prefix`` (respawned nodes start
      from the parent's final committed history, which the raw ok-commit list
      silently dropped);
    - a ``commit_tactic`` row counts only if EasyCrypt ACCEPTED it: the row's
      ``ok`` is true even for EC-rejected and auto-reverted (no-op) commits —
      the real signal is the ``tactic commit`` manager action carrying NO
      ``error_summary``. Rows without manager actions fall back to ``ok``;
    - an accepted ``undo_last_step`` pops the last committed tactic;
    - a CONFIRMED ``undo_to_checkpoint`` rewind (a ``checkpoint rewind`` action;
      the bare intent only opens a menu) rewinds to the latest earlier state
      with the same ``goal_hash``; when that cannot be resolved the result is
      flagged ``approximate``;
    - a confirmed ``fresh_restart`` erases the branch back to its bootstrap
      (post-replay-prefix) state.

    Returns ``{"tactics", "replay_prefix_count", "approximate"}`` or None when
    no timeline exists.
    """
    tl = node_dir / "timeline.jsonl"
    if not tl.exists():
        return None
    prefix = _bootstrap_prefix_lines(run_iter, node_dir.name)
    stack: list[str] = list(prefix)
    approximate = False
    # (goal_hash, committed-depth) after each turn, for checkpoint-rewind resync
    depth_at_hash: list[tuple[str, int]] = []
    try:
        rows = [json.loads(line) for line in
                tl.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return None
    for row in rows:
        it = row.get("intent") or {}
        name = it.get("intent")
        if not name:
            # bootstrap row: it declares the replayed prefix length; if the
            # bootstrap file vanished but a prefix WAS replayed, say so.
            declared = row.get("replay_prefix_count")
            if not prefix and isinstance(declared, int) and declared > 0:
                approximate = True
            continue
        if name == "commit_tactic":
            action = _commit_action(row)
            accepted = ("error_summary" not in action) if action is not None \
                else bool(row.get("ok"))
            tac = str((it.get("payload") or {}).get("tactic") or "").strip()
            if accepted and tac:
                stack.append(tac)
        elif name == "undo_last_step" and row.get("ok"):
            # real rows carry an `undo` action; bare rows (older runs) trust ok
            if (_has_action(row, "undo") or not row.get("manager_actions")) and stack:
                stack.pop()
        elif name == "undo_to_checkpoint" and row.get("ok"):
            # only a confirmed rewind mutates; the bare intent shows a menu
            if _has_action(row, "checkpoint rewind", ok_only=True):
                gh = str(row.get("goal_hash") or "")
                depth = next((d for h, d in reversed(depth_at_hash) if h == gh),
                             None)
                if gh and depth is not None and depth <= len(stack):
                    del stack[depth:]
                else:
                    approximate = True
        elif name in {"fresh_restart", "request_restart"} and row.get("ok"):
            if _has_action(row, "fresh restart", ok_only=True):
                stack = list(prefix)
        elif name == "commit_replay_suffix_chunk" and row.get("ok"):
            # the chunk's tactics are not in the row payload (only a chunk_id)
            approximate = True
        gh = str(row.get("goal_hash") or "")
        if gh:
            depth_at_hash.append((gh, len(stack)))
    return {
        "tactics": stack,
        "replay_prefix_count": len(prefix),
        "approximate": approximate,
    }


def _committed_proofs(run_iter_dir: Path) -> list[dict[str, Any]]:
    """Reconstruct the proof each tree actually committed.

    Source of truth per tree, in order:

    1. ``source: "session"`` — the tree's exact session ``history.ec`` (the
       EC-accepted script: undos/rewinds applied, respawn replay prefix
       included). Exact session-name match ONLY — never another tree's file.
    2. ``source: "timeline_replay"`` — a faithful replay of the timeline (see
       `_replay_timeline_commits`): bootstrap replay prefix + EC-accepted
       commits, with `undo_last_step` / confirmed rewinds applied. The raw
       ok-commit list is NOT the committed proof: ``ok: true`` includes
       EC-rejected and auto-reverted commits, and undone tactics stay in it.

    Only a committed script that ENDS in `qed.` marks the tree proved (an
    undone/rejected `qed.` does not; nor does `finish`, which while goals
    remain is a give-up).
    """
    out: list[dict[str, Any]] = []
    for node in _node_dirs(run_iter_dir):
        if not (node / "timeline.jsonl").exists():
            continue
        hist = _session_history_exact(run_iter_dir, node.name)
        replayed = _replay_timeline_commits(run_iter_dir, node)
        use_hist = bool(hist)
        if use_hist and replayed is not None and not replayed["approximate"]:
            fold = replayed["tactics"]
            # A run killed mid-`undo_to_checkpoint` rewind leaves a TORN
            # history.ec: the rewind rewrites the file by replaying from the
            # start, so the torn file is a strict proper prefix of the
            # faithful timeline replay (observed: a 45-commit node with a
            # 1-line history). Commits append to history BEFORE the timeline
            # row is recorded, so the replay can never legitimately be ahead
            # — prefer the replay then.
            if len(hist) < len(fold) and fold[:len(hist)] == hist:
                use_hist = False
        if use_hist:
            entry: dict[str, Any] = {
                "tree": node.name, "tactics": hist, "source": "session"}
        else:
            if replayed is None:
                continue
            entry = {
                "tree": node.name,
                "tactics": replayed["tactics"],
                "source": "timeline_replay",
                "replay_prefix_count": replayed["replay_prefix_count"],
            }
            if replayed["approximate"]:
                entry["approximate"] = True
        tactics = entry["tactics"]
        entry["proved"] = bool(tactics) and tactics[-1].rstrip().endswith("qed.")
        out.append(entry)
    return out


def _render_proof_section(proofs: list[dict[str, Any]],
                          run_iter: Path | None = None) -> str:
    """Render each tree's committed proof as a copy-pasteable EasyCrypt block.

    ``proofs`` from `_committed_proofs` is already grounded (session history
    preferred; otherwise a faithful timeline replay with undos and the respawn
    replay prefix applied) — render it as-is. For hand-built entries with no
    ``source`` (older callers), prefer the tree's EXACT session ``history.ec``
    when ``run_iter`` is given."""
    blocks: list[str] = []
    for p in proofs:
        tree, tactics, proved = p["tree"], p["tactics"], p["proved"]
        source = p.get("source")
        if source is None and run_iter is not None:
            hist = _session_history_exact(run_iter, tree)
            if hist:
                tactics = hist
                proved = hist[-1].rstrip().endswith("qed.")
                source = "session"
        status = ("proved" if proved
                  else f"incomplete — {len(tactics)} tactic(s) committed, not closed")
        if source == "timeline_replay":
            status += " (timeline replay — no session history survived)"
        if p.get("approximate"):
            status += " (approximate: a rewind could not be fully resolved)"
        ends_qed = bool(tactics) and tactics[-1].rstrip().endswith("qed.")
        body = "\n".join(f"  {t}" for t in tactics) if tactics else "  (* no tactic committed *)"
        # Never fabricate a closing `qed.`: a proved tree already ends in its
        # accepted `qed.`; an unclosed tree is annotated, not given a fake qed.
        tail = "" if ends_qed else "  (* proof not completed in this run *)\n"
        blocks.append(
            f"### `{tree}` — {status}\n\n```easycrypt\nproof.\n{body}\n{tail}```\n")
    if not blocks:
        return ""
    return ("## Agent's committed proof\n\nThe committed script per proof tree "
            "(EC-accepted commits only; undos/rewinds applied; a respawned "
            "node's replayed prefix included).\n\n"
            + "\n".join(blocks) + "\n---\n\n")


# --------------------------------------------------------------------------
# Resume lineage: stitch a chunk0 → chunk1 → … → leaf proof into ONE bundle.
#
# A resumed run records its parent capsule(s) in ``<run_dir>/config.json``
# (``resume_capsules``); each capsule lives at
# ``<parent_iter>/resume_capsules/<node>/resume.json`` (so the parent run-iter is
# ``capsule.parents[2]``) and carries the cumulative committed prefix in a
# sibling ``history.ec``. Resume runs log only their NEW commits (the replayed
# prefix is not re-logged), so concatenating each chunk's committed tactics in
# lineage order yields the full end-to-end proof, one boundary per resume.
#
# Lineage resolution needs the live artifacts/worktree intact (capsule paths are
# repo-relative to the run's cwd) — so build the bundle at closure, before any
# worktree cleanup. That is the whole point: one bundle then holds the complete
# move=>…qed proof + the whole timeline, instead of only the closing chunk.
# --------------------------------------------------------------------------
def _load_run_config(run_iter: Path) -> dict[str, Any]:
    try:
        return json.loads((run_iter.parent / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _worktree_root(run_iter: Path) -> Path:
    """The cwd the run was launched from: the parent of the ``artifacts`` dir the
    run lives under (capsule paths in config.json are relative to it)."""
    for parent in run_iter.parents:
        if parent.name == "artifacts":
            return parent.parent
    return run_iter.parent


def _primary_capsule(run_iter: Path) -> Path | None:
    caps = _load_run_config(run_iter).get("resume_capsules") or []
    if not caps:
        return None
    cap = Path(caps[0])
    if not cap.is_absolute():
        cap = _worktree_root(run_iter) / caps[0]
    return cap if cap.exists() else None


def _resolve_lineage(leaf_iter: Path) -> list[Path]:
    """Walk the resume-capsule chain backward to the fresh root; return the
    run-iteration dirs ordered root→leaf (``[leaf]`` for a non-resumed run)."""
    chain = [leaf_iter]
    seen = {str(leaf_iter.resolve())}
    cur = leaf_iter
    for _ in range(64):  # safety bound against a cyclic/corrupt chain
        cap = _primary_capsule(cur)
        if cap is None:
            break
        try:
            parent_iter = cap.parents[2]
        except IndexError:
            break
        key = str(parent_iter.resolve())
        if key in seen or not (parent_iter / "node_memory").is_dir():
            break
        seen.add(key)
        chain.append(parent_iter)
        cur = parent_iter
    chain.reverse()
    return chain


def _capsule_prefix_lines(run_iter: Path) -> list[str]:
    """The cumulative committed prefix (history.ec tactic lines) ``run_iter``
    resumed from, read from its primary capsule. [] for a fresh run."""
    cap = _primary_capsule(run_iter)
    if cap is None:
        return []
    try:
        return [ln for ln in (cap.parent / "history.ec").read_text(
            encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        return []


def _copy_views(run_iter: Path, views_dir: Path) -> int:
    """Copy a run's per-turn agent views (+ manager results, thinking, followups,
    bootstraps) into ``views_dir`` (``<views_dir>/<Tree>/turn_NNN.json``, …,
    ``<views_dir>/_bootstrap/…``). Returns the workspace-view count. Thinking is
    assumed already extracted by the caller."""
    copied = 0
    for node in _node_dirs(run_iter):
        out = views_dir / node.name
        vsrc = node / "workspace_views"
        if vsrc.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            for v in sorted(vsrc.glob("turn_*.json")):
                _copy_json_scrubbed(v, out / v.name)
                copied += 1
        rsrc = node / "manager_results"
        if rsrc.is_dir():
            rout = out / "manager_results"
            rout.mkdir(parents=True, exist_ok=True)
            for r in sorted(rsrc.glob("turn_*.json")):
                _copy_json_scrubbed(r, rout / r.name)
        tsrc = node / "thinking"
        if tsrc.is_dir():
            tout = out / "thinking"
            tout.mkdir(parents=True, exist_ok=True)
            for t in sorted(tsrc.glob("turn_*.md")):
                tout.joinpath(t.name).write_text(
                    _scrub_paths(t.read_text(encoding="utf-8")), encoding="utf-8")
            if (tsrc / "index.json").exists():
                _copy_json_scrubbed(tsrc / "index.json", tout / "index.json")
        fsrc = node / "followups"
        if fsrc.is_dir():
            fout = out / "followups"
            fout.mkdir(parents=True, exist_ok=True)
            for f in sorted(fsrc.glob("turn_*.md")):
                fout.joinpath(f.name).write_text(
                    _scrub_paths(f.read_text(encoding="utf-8")), encoding="utf-8")
    boots = sorted(run_iter.glob("manager_bootstrap_*.json"))
    if boots:
        boot_out = views_dir / "_bootstrap"
        boot_out.mkdir(parents=True, exist_ok=True)
        for b in boots:
            _copy_json_scrubbed(b, boot_out / b.name)
    return copied


def _rewrite_chunk_links(md: str, base: str, label: str) -> str:
    """Namespace one chunk's absolute view links → ``./views/<label>/…`` so each
    resume chunk's per-turn views resolve to its own copied subtree."""
    b = re.escape(base.rstrip("/"))
    md = re.sub(b + r"/node_memory/(Tree_[A-Za-z0-9_]+)/workspace_views/(turn_\d+\.json)",
                rf"./views/{label}/\g<1>/\g<2>", md)
    md = re.sub(b + r"/node_memory/(Tree_[A-Za-z0-9_]+)/manager_results/(turn_\d+\.json)",
                rf"./views/{label}/\g<1>/manager_results/\g<2>", md)
    md = re.sub(b + r"/node_memory/(Tree_[A-Za-z0-9_]+)/thinking/(turn_\d+\.md)",
                rf"./views/{label}/\g<1>/thinking/\g<2>", md)
    md = re.sub(b + r"/node_memory/(Tree_[A-Za-z0-9_]+)/followups/(turn_\d+\.md)",
                rf"./views/{label}/\g<1>/followups/\g<2>", md)
    md = re.sub(b + r"/(manager_bootstrap_[A-Za-z0-9_]+\.json)",
                rf"./views/{label}/_bootstrap/\g<1>", md)
    return md


def _read_history_file(path: Path) -> list[str]:
    try:
        return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        return []


def _session_history_exact(run_iter: Path, tree: str) -> list[str]:
    """``tree``'s own session ``history.ec`` (exact session-name match only —
    never another tree's file). Fresh runs persist the session under
    ``<run_iter>/ec_sessions/``; resume runs leave it at the worktree root."""
    sess = ".ec_session_prover_" + tree.lower()
    for d in (run_iter / "ec_sessions", _worktree_root(run_iter)):
        lines = _read_history_file(d / sess / "history.ec")
        if lines:
            return lines
    return []


def _session_history_lines(run_iter: Path, tree: str | None) -> list[str]:
    """The EC-accepted committed script for ``tree`` — its session ``history.ec``,
    which is the GROUND TRUTH: undos and ``undo_to_checkpoint`` rewinds are already
    applied, unlike the timeline's raw ok-commit list (which keeps rewound
    tactics). Fresh runs persist the session under ``<run_iter>/ec_sessions/``;
    resume runs leave it at the worktree root. Falls back to the largest
    ``history.ec`` found. [] if none (e.g. session already cleaned up)."""
    search_dirs = [run_iter / "ec_sessions", _worktree_root(run_iter)]
    if tree:  # exact session name first (Tree_0_0 -> .ec_session_prover_tree_0_0)
        lines = _session_history_exact(run_iter, tree)
        if lines:
            return lines
    best: list[str] = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for h in d.glob(".ec_session*/history.ec"):
            lines = _read_history_file(h)
            if len(lines) > len(best):
                best = lines
    return best


def _lineage_proof(chain: list[Path]) -> dict[str, Any]:
    """End-to-end proof for the tree the LEAF closed (else its richest tree).

    Source of truth is the leaf's cumulative session ``history.ec`` (the prefix
    every chunk replayed + the leaf's own commits, with undos/rewinds applied).
    Resume boundaries come from each chunk's capsule prefix count. Falls back to
    concatenating per-chunk timeline commits only if no session history survives
    (less accurate — it can include rewound tactics)."""
    leaf_proofs = _committed_proofs(chain[-1])
    winner = next((p for p in leaf_proofs if p["proved"]), None)
    if winner is None and leaf_proofs:
        winner = max(leaf_proofs, key=lambda p: len(p["tactics"]))
    tree = winner["tree"] if winner else None

    hist = _session_history_lines(chain[-1], tree)
    if hist:
        # cumulative replayed-prefix count at each resume (chain[1:] are resumes)
        bounds = [len(_capsule_prefix_lines(ci)) for ci in chain[1:]]
        bounds = sorted({b for b in bounds if 0 < b < len(hist)})
        return {"source": "session", "tree": tree, "lines": hist,
                "boundaries": bounds,
                "proved": bool(hist) and hist[-1].rstrip().endswith("qed.")}

    # fallback 1: the leaf's faithful timeline replay. It already includes the
    # replayed prefix (= the whole lineage before the leaf), so it IS the
    # end-to-end script — concatenating chunks on top would double-count.
    chosen = next((p for p in leaf_proofs if p["tree"] == tree), None)
    if chosen is not None and (
            len(chain) == 1 or chosen.get("replay_prefix_count")):
        lines = list(chosen["tactics"])
        bounds = [len(_capsule_prefix_lines(ci)) for ci in chain[1:]]
        bounds = sorted({b for b in bounds if 0 < b < len(lines)})
        return {"source": "timeline_replay", "tree": tree, "lines": lines,
                "boundaries": bounds, "proved": bool(chosen["proved"])}

    # fallback 2: per-chunk timeline concatenation (approximate — the leaf had
    # no usable replay prefix, so stitch chunk scripts in lineage order)
    segments: list[list[str]] = []
    for ci in chain:
        ps = _committed_proofs(ci)
        seg = next((p for p in ps if p["tree"] == tree), None)
        if seg is None and ps:
            seg = max(ps, key=lambda p: len(p["tactics"]))
        segments.append(list((seg or {}).get("tactics", [])))
    return {"source": "timeline", "tree": tree, "segments": segments,
            "proved": bool(winner and winner["proved"])}


def _render_lineage_proof(chain: list[Path], lp: dict[str, Any]) -> str:
    tree = lp["tree"]
    if "lines" in lp:
        src = lp["lines"]
        cuts = sorted({0, *lp["boundaries"], len(src)})
        out = ["proof."]
        for si in range(len(cuts) - 1):
            if si > 0:
                out.append(
                    f"  (* ─── resume {si}: replayed {cuts[si]} tactic(s) "
                    f"above, continued below ─── *)")
            out.extend(f"  {t}" for t in src[cuts[si]:cuts[si + 1]])
        if not out[-1].rstrip().endswith("qed."):
            out.append("  (* proof not completed in this lineage *)")
        total = len(src)
        if lp["source"] == "session":
            how = (f"Reconstructed from the leaf's EasyCrypt session `history.ec` "
                   f"({total} accepted tactic(s); undos/rewinds already applied), "
                   f"split at each resume boundary.")
        else:
            how = (f"Reconstructed by replaying the leaf chunk's timeline "
                   f"({total} EC-accepted tactic(s), undos applied, replayed "
                   f"prefix included — no session history.ec survived), split "
                   f"at each resume boundary.")
    else:
        out = ["proof."]
        running = 0
        for i, seg in enumerate(lp["segments"]):
            if i > 0:
                out.append(
                    f"  (* ─── resume {i}: replayed {running} tactic(s) "
                    f"above, continued below ─── *)")
            out.extend(f"  {t}" for t in seg)
            running += len(seg)
        if not out[-1].rstrip().endswith("qed."):
            out.append("  (* proof not completed in this lineage *)")
        total = running
        how = ("Reconstructed by concatenating each chunk's committed tactics "
               "(timeline fallback — no session history.ec survived, so rewound "
               "tactics may appear).")
    body = "\n".join(out)
    status = ("proved" if lp["proved"]
              else f"incomplete — {total} tactic(s) across {len(chain)} "
                   "chunk(s), not closed")
    return (
        f"## Agent's committed proof (end-to-end across {len(chain)} resume "
        f"chunks)\n\n{how} `(* ─── resume k ─── *)` marks each resume "
        f"boundary.\n\n"
        f"### `{tree}` — {status}\n\n```easycrypt\n{body}\n```\n\n---\n\n")


def _build_chain_bundle(
    chain: list[Path],
    *,
    dest_root: str | Path,
    timestamp: str,
    lemma: str | None,
    source_file: str | None,
    model: str | None,
    profile: str | None,
    trees: int | None,
    eval_mode: bool | None,
    extra_meta: dict[str, Any] | None,
) -> Path:
    """Build ONE end-to-end bundle spanning a resume lineage (root→leaf)."""
    leaf = chain[-1]
    labels = [f"c{i}" for i in range(len(chain))]
    env = _env_info()
    lemma = lemma or "unknown_lemma"
    safe_ts = re.sub(r"[^0-9A-Za-z_]", "-", str(timestamp))
    tag = f"{safe_ts}__{env['commit']}" + ("-dirty" if env["dirty"] else "")
    dest = (_REPO_ROOT / dest_root / re.sub(r"[^0-9A-Za-z_]", "_", lemma) / tag)
    dest.mkdir(parents=True, exist_ok=True)
    views_dir = dest / "views"

    # 1. extract thinking + copy views per chunk, namespaced under views/c{i}/
    copied = 0
    for label, ci in zip(labels, chain):
        try:
            from workflow.validation.agent_thinking_trace import write_run_thinking
            write_run_thinking(ci)
        except Exception:
            pass
        copied += _copy_views(ci, views_dir / label)

    # 2. one timeline over the whole lineage (LABEL=PATH specs, root→leaf)
    md_tmp = dest / ".timeline_raw.md"
    json_out = dest / "timeline_report.json"
    specs = [f"{label}={ci}" for label, ci in zip(labels, chain)]
    try:
        subprocess.run(
            [sys.executable, "-m", "workflow.validation.agent_view_timeline_report",
             *specs, "--output", str(md_tmp), "--json-output", str(json_out)],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=180,
            env={**os.environ, "SHANNON_BUNDLE_INTERNAL": "1"},
        )
    except Exception:
        pass
    _scrub_json_file(json_out)
    raw_md = md_tmp.read_text(encoding="utf-8") if md_tmp.exists() else ""
    for label, ci in zip(labels, chain):
        raw_md = _rewrite_chunk_links(raw_md, str(ci.resolve()), label)
    raw_md = _rewrite_links(raw_md)
    md_tmp.unlink(missing_ok=True)

    # 3. meta + header + end-to-end proof
    turn_count = 0
    try:
        rep = json.loads(json_out.read_text(encoding="utf-8")) if json_out.exists() else {}
        turn_count = sum(len(r.get("rows") or []) for r in (rep.get("runs") or []))
    except Exception:
        pass
    lp = _lineage_proof(chain)
    proof_tactics = (len(lp["lines"]) if "lines" in lp
                     else sum(len(s) for s in lp["segments"]))
    if trees is None:
        trees = len(_node_dirs(leaf)) or None
    if not lp["proved"]:
        outcome = _outcome(leaf)
    elif _final_proved_from_summary(leaf) is False:
        outcome = "proved_in_session (final verification failed)"
    else:
        outcome = "proved"
    meta = {
        "kind": "agent_view_run_report",
        "timestamp": timestamp,
        "lemma": lemma,
        "source_file": source_file,
        "model": model,
        "surface_profile": profile,
        "trees": trees,
        "eval_mode": eval_mode,
        "outcome": outcome,
        "resume_chunks": len(chain),
        "resume_lineage": [_scrub_paths(str(c)) for c in chain],
        "committed_proof_tactics": proof_tactics,
        "committed_proof_source": lp["source"],
        "committed_proof_tree": lp["tree"],
        "turn_count": turn_count,
        "views_copied": copied,
        "run_iteration_dir": _scrub_paths(str(leaf)),
        **env,
        **(extra_meta or {}),
    }
    (dest / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    header = (
        f"# Agent-View Timeline — `{lemma}` (resume lineage, {len(chain)} chunks)\n\n"
        f"| field | value |\n|---|---|\n"
        f"| commit | `{env['commit']}`{' **(dirty/uncommitted)**' if env['dirty'] else ''} |\n"
        f"| branch | `{env['branch']}` |\n"
        f"| run time | {timestamp} |\n"
        f"| lemma | `{lemma}` |\n"
        f"| source file | `{source_file or '?'}` |\n"
        f"| model | `{model or '?'}` |\n"
        f"| surface profile | `{profile or '?'}` |\n"
        f"| resume chunks | {len(chain)} (c0=fresh → c{len(chain)-1}=leaf) |\n"
        f"| trees | {trees if trees is not None else '?'} |\n"
        f"| eval mode | {eval_mode if eval_mode is not None else '?'} |\n"
        f"| outcome | {outcome} |\n"
        f"| turns (all chunks) | {turn_count} |\n\n"
        "This run was built across a **resume lineage**: the proof was carried "
        "chunk0 → … → leaf via resume capsules. The committed-proof "
        "block below is the FULL `proof. … qed.` stitched across all chunks "
        "(resume boundaries marked); the timeline below has one `## c<k>` section "
        "per chunk, in order.\n\n---\n\n"
    )
    proof_section = _render_lineage_proof(chain, lp)
    (dest / "timeline_report.md").write_text(
        header + proof_section + raw_md, encoding="utf-8")

    _append_index(_REPO_ROOT / dest_root, dest, meta)
    return dest


def build_bundle(
    run_iter_dir: str | Path,
    *,
    dest_root: str | Path = "agent_view_runs",
    timestamp: str,
    lemma: str | None = None,
    source_file: str | None = None,
    model: str | None = None,
    profile: str | None = None,
    trees: int | None = None,
    eval_mode: bool | None = None,
    extra_meta: dict[str, Any] | None = None,
    follow_resume: bool = True,
) -> Path | None:
    """Build the committed bundle for ``run_iter_dir``. Returns the bundle dir.

    ``timestamp`` must be supplied by the caller (the orchestrator/runner knows
    the run start time; this module does not call ``datetime.now`` so it stays
    deterministic and re-runnable).

    If ``follow_resume`` (default) and ``run_iter_dir`` is the leaf of a resume
    lineage (chunk0 → … → leaf via resume capsules), the bundle spans the WHOLE
    lineage: one end-to-end ``proof. … qed.`` stitched across all chunks plus a
    per-chunk timeline — instead of only the final (closing) chunk. Resolution
    needs the live worktree intact, so build at closure before any cleanup.
    """
    run_iter_dir = Path(run_iter_dir)
    if not (run_iter_dir / "node_memory").is_dir():
        return None
    if follow_resume:
        chain = _resolve_lineage(run_iter_dir)
        if len(chain) > 1:
            return _build_chain_bundle(
                chain, dest_root=dest_root, timestamp=timestamp, lemma=lemma,
                source_file=source_file, model=model, profile=profile,
                trees=trees, eval_mode=eval_mode, extra_meta=extra_meta)
    # Default the tree count to the number of proof-tree node dirs that actually
    # ran — the suite/config `tree_initial_provers` is often unset, and the real
    # topology is what the report should show (keeps the header honest, not "?").
    if trees is None:
        trees = len(_node_dirs(run_iter_dir)) or None
    env = _env_info()
    lemma = lemma or "unknown_lemma"
    safe_ts = re.sub(r"[^0-9A-Za-z_]", "-", str(timestamp))
    tag = f"{safe_ts}__{env['commit']}" + ("-dirty" if env["dirty"] else "")
    dest = (_REPO_ROOT / dest_root / re.sub(r"[^0-9A-Za-z_]", "_", lemma) / tag)
    dest.mkdir(parents=True, exist_ok=True)
    views_dir = dest / "views"

    # 0. extract each turn's agent reasoning into node_memory/<tree>/thinking/ so
    #    the timeline can link a per-step thinking view. The reasoning lives in the
    #    prover's Claude session transcript (not the run artifacts); best-effort.
    try:
        from workflow.validation.agent_thinking_trace import write_run_thinking
        write_run_thinking(run_iter_dir)
    except Exception:
        pass

    # 1. copy per-turn agent views (+ manager results + thinking + followups +
    #    bootstraps) so every link in the report resolves inside the bundle. The
    #    followup is the INLINE text the agent actually read (a filtered preview of
    #    the full view) — copied so the report links "what was consumed", not only
    #    "what was offered".
    copied = _copy_views(run_iter_dir, views_dir)

    # 2. generate the timeline report markdown + json via the existing tool
    md_tmp = dest / ".timeline_raw.md"
    json_out = dest / "timeline_report.json"
    try:
        subprocess.run(
            [sys.executable, "-m", "workflow.validation.agent_view_timeline_report",
             str(run_iter_dir), "--output", str(md_tmp),
             "--json-output", str(json_out)],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=120,
            # Mark this as the bundle's internal table pass so the bare tool does
            # not print its "use run_report_bundle" nudge to a tool that already
            # wraps it.
            env={**os.environ, "SHANNON_BUNDLE_INTERNAL": "1"},
        )
    except Exception:
        pass
    # The timeline tool writes the JSON report with absolute artifact paths;
    # scrub it in place so the committed JSON leaks no machine path either.
    _scrub_json_file(json_out)
    raw_md = md_tmp.read_text(encoding="utf-8") if md_tmp.exists() else ""
    raw_md = _rewrite_links(raw_md)
    md_tmp.unlink(missing_ok=True)

    # 3. environment header + meta
    turn_count = 0
    try:
        rep = json.loads(json_out.read_text(encoding="utf-8")) if json_out.exists() else {}
        turn_count = sum(len(r.get("rows") or []) for r in (rep.get("runs") or []))
    except Exception:
        pass
    proofs = _committed_proofs(run_iter_dir)
    meta = {
        "kind": "agent_view_run_report",
        "timestamp": timestamp,
        "lemma": lemma,
        "source_file": source_file,
        "model": model,
        "surface_profile": profile,
        "trees": trees,
        "eval_mode": eval_mode,
        "outcome": _outcome(run_iter_dir),
        "committed_proofs": proofs,
        "turn_count": turn_count,
        "views_copied": copied,
        "run_iteration_dir": _scrub_paths(str(run_iter_dir)),
        **env,
        **(extra_meta or {}),
    }
    (dest / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    header = (
        f"# Agent-View Timeline — `{lemma}`\n\n"
        f"| field | value |\n|---|---|\n"
        f"| commit | `{env['commit']}`{' **(dirty/uncommitted)**' if env['dirty'] else ''} |\n"
        f"| branch | `{env['branch']}` |\n"
        f"| run time | {timestamp} |\n"
        f"| lemma | `{lemma}` |\n"
        f"| source file | `{source_file or '?'}` |\n"
        f"| model | `{model or '?'}` |\n"
        f"| surface profile | `{profile or '?'}` |\n"
        f"| trees | {trees if trees is not None else '?'} |\n"
        f"| eval mode | {eval_mode if eval_mode is not None else '?'} |\n"
        f"| outcome | {meta['outcome']} |\n"
        f"| turns | {turn_count} |\n\n"
        "Each row below: the view → the intent the agent submitted → the manager "
        "result. The **Decision View** column has TWO links: `turn_NNN.json` is the "
        "full projected `ProverWorkspaceView` the framework computed (all panels); "
        "`inline read` is the filtered preview the agent ACTUALLY read inline "
        "(`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops "
        "panels — so to see what the agent truly consumed, open `inline read`, not "
        "the full view.\n\n---\n\n"
    )
    proof_section = _render_proof_section(proofs, run_iter_dir)
    (dest / "timeline_report.md").write_text(
        header + proof_section + raw_md, encoding="utf-8")

    _append_index(_REPO_ROOT / dest_root, dest, meta)
    return dest


_INDEX_HEADER = (
    "# Agent-View Run Reports\n\n"
    "Auto-generated, committed timeline+view bundles (one per prover "
    "run). Newest appended at the bottom.\n\n"
    "| time | lemma | commit | outcome | turns | report |\n"
    "|---|---|---|---|---|---|\n")


def _append_index(root: Path, bundle: Path, meta: dict[str, Any]) -> None:
    """Append/refresh a one-line entry in the bundle root INDEX.md.

    Idempotent: a bundle is keyed by its report link, so re-bundling the same run
    (or two callers bundling it — orchestrator + suite runner) refreshes that
    one row in place rather than appending a duplicate."""
    index = root / "INDEX.md"
    rel = bundle.relative_to(root)
    link = f"[report]({rel.as_posix()}/timeline_report.md)"
    row = (f"| {meta.get('timestamp')} | `{meta.get('lemma')}` | "
           f"`{meta.get('commit')}`{'(dirty)' if meta.get('dirty') else ''} | "
           f"{meta.get('outcome')} | {meta.get('turn_count')} | {link} |")
    existing = index.read_text(encoding="utf-8") if index.exists() else _INDEX_HEADER
    # Drop only a prior row for THIS bundle (keep header + blank lines intact).
    kept = [ln for ln in existing.splitlines()
            if f"({rel.as_posix()}/timeline_report.md)" not in ln]
    index.write_text("\n".join(kept).rstrip("\n") + "\n" + row + "\n",
                     encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_iteration_dir")
    p.add_argument("--dest-root", default="agent_view_runs")
    p.add_argument("--timestamp", required=True)
    p.add_argument("--lemma")
    p.add_argument("--source-file")
    p.add_argument("--model")
    p.add_argument("--profile")
    p.add_argument("--trees", type=int)
    p.add_argument("--eval-mode", action="store_true")
    p.add_argument(
        "--no-follow-resume", dest="follow_resume", action="store_false",
        help="Bundle only this run, not its resume lineage (default: stitch the "
             "whole chunk0→…→leaf chain into one end-to-end report).")
    a = p.parse_args(argv)
    dest = build_bundle(
        a.run_iteration_dir, dest_root=a.dest_root, timestamp=a.timestamp,
        lemma=a.lemma, source_file=a.source_file, model=a.model,
        profile=a.profile, trees=a.trees, eval_mode=a.eval_mode or None,
        follow_resume=a.follow_resume,
    )
    if dest is None:
        print("run_report_bundle: no node_memory found; nothing written",
              file=sys.stderr)
        return 1
    print(f"run_report_bundle: wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
