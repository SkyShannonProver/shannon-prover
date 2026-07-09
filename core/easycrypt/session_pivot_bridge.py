"""Pr-bridge suggestion engine (AUTO-BRIDGE-SUGGEST): typed Pr-bridge frontend candidates, named-bridge fallback, up-to-bad call coherence.

Extracted verbatim from PivotStrategyPhase (session_hook_phases.py) — the
2,900-line inspect-engine god-class. Each function's first parameter is
named ``self`` ON PURPOSE: it receives the PivotStrategyPhase instance
(for ``self.session`` and the small shared helpers that stay on the
class), so the bodies are byte-identical to the original methods and the
panel-invariance guarantee holds. De-self-ifying the signatures into
explicit params is a follow-up, not part of this carve.
"""
from __future__ import annotations

import re

import json
from pathlib import Path
from typing import Any, Optional
from core.hooks.contract import CommitPhase, HookResult  # type: ignore


def _rewrite_direction_and_name(tactic: object) -> Optional[tuple[str, str]]:
    text = str(tactic or "").strip()
    text = re.sub(r"^[+\-*]\s*", "", text)
    text = re.sub(r"^(?:by\s+)+", "", text)
    m = re.match(
        r"rewrite\s+(-)?\s*\(?\s*([A-Za-z_][A-Za-z0-9_'.]*)",
        text,
    )
    if not m:
        return None
    direction = "backward" if m.group(1) else "forward"
    name = m.group(2).rstrip(".").rsplit(".", 1)[-1]
    return direction, name


_CALL_CALLEE = re.compile(r"<@\s*([A-Z][A-Za-z0-9_']*)\s*[(.]")
_GLOB_MENTION = re.compile(r"\bglob\s+([A-Z][A-Za-z0-9_']*)")

def _bridge_reverses_latest_rewrite(candidate: object, latest: object) -> bool:
    cand = _rewrite_direction_and_name(candidate)
    prev = _rewrite_direction_and_name(latest)
    if not cand or not prev:
        return False
    return cand[1] == prev[1] and cand[0] != prev[0]


def try_bridge_suggest(self, raw_goal: str,
                        h: Optional[DaemonHandle]) -> Optional[HookResult]:
    """Pr-level bridge options compiled from source structure.

    Narrative may contribute clean semantic signatures, but executable
    route authority comes from deterministic candidates verified by the
    daemon against the current goal.
    """
    if not raw_goal:
        return None
    pr_count = raw_goal.count("Pr[")
    has_relation = ("=" in raw_goal or "<=" in raw_goal)
    if not (2 <= pr_count <= 3 and has_relation):
        return None
    narrative = self.session._load_narrative()
    source_path = ""
    try:
        candidate_path = getattr(self.session, "context_file", None)
        if (
            candidate_path
            and Path(candidate_path).exists()
            and Path(candidate_path).stat().st_size > 0
        ):
            source_path = str(candidate_path)
    except Exception:
        source_path = ""
    if not source_path:
        try:
            source_path, _ = self.session._get_daemon_meta()
        except Exception:
            source_path = ""
    # bridge_options candidates come solely from ProofIR's typed Pr-bridge
    # frontend (endpoint typing + name resolution + instantiation binding),
    # the same way call-site options consume ProofIR.  The old regex
    # pr_bridge_compiler has been retired.  Candidates are still gated by
    # daemon verification below -- nothing is surfaced runnable unverified.
    candidates = self._dedupe_bridge_candidates(
        self._proof_ir_pr_bridge_candidates(raw_goal)
    )
    # Static endpoint pre-filter (no daemon): keep only candidates whose Pr
    # endpoints match a game in the goal, so we probe ~a handful instead of
    # the full set. The probe cap below stays as a safety net.
    _n_before = len(candidates)
    candidates, _bridge_off_goal = self._bridge_candidates_in_goal(
        candidates, raw_goal)
    context_evidence = {
        "id": "context.pr_bridge_candidates",
        "producer": "proofir_typed_bridge_frontend",
        "candidate_count": len(candidates),
        "candidates_before_scope_filter": _n_before,
        "statically_dropped_off_goal": _bridge_off_goal,
        "source_path": str(source_path or ""),
        "narrative_source": (
            "available" if narrative else
            str(getattr(
                self.session,
                "_narrative_rejection_reason",
                "",
            ) or "none")
        ),
    }
    gate_evidence = {
        "id": "deterministic.auto_bridge_gate",
        "producer": "AUTO-BRIDGE-SUGGEST",
        "pr_count": pr_count,
        "has_relation": has_relation,
    }
    if not candidates:
        _fb_text, _fb_ctx = self._named_bridge_fallback_block(raw_goal)
        return HookResult(
            text=(
                "\n[BRIDGE-OPTIONS/NO_CANDIDATES] The current goal is a "
                "Pr relation, but ProofIR's typed Pr-bridge frontend "
                "produced no type-matched bridge candidates for the current "
                "endpoints. No manager-verified bridge route is available "
                "from the current proof state.\n"
            ) + _fb_text,
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={
                "deterministic": [gate_evidence],
                "context": [context_evidence, *_fb_ctx],
            },
            notes=[{
                "code": "bridge_options.no_candidates",
                "message": (
                    "No runnable tactic is surfaced because the typed "
                    "bridge frontend could not derive a candidate bridge "
                    "from the current goal endpoints."
                ),
            }],
        )
    if h is None:
        _fb_text, _fb_ctx = self._named_bridge_fallback_block(raw_goal)
        return HookResult(
            text=(
                "\n[BRIDGE-OPTIONS/UNAVAILABLE] The manager found "
                f"{len(candidates)} type-matched Pr bridge candidate(s), "
                "but the EasyCrypt daemon is unavailable, so no executable "
                "bridge option is shown. Retry this inspect when daemon "
                "verification is available.\n"
            ) + _fb_text,
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={
                "deterministic": [gate_evidence],
                "context": [context_evidence, *_fb_ctx],
            },
            notes=[{
                "code": "bridge_options.daemon_unavailable",
                "message": (
                    "Bridge candidates are intentionally hidden until "
                    "daemon verification accepts them on the current goal."
                ),
            }],
            errors=[{
                "code": "bridge_options.daemon_unavailable",
                "message": "EasyCrypt daemon handle is unavailable.",
            }],
        )
    latest_tactic = self._latest_committed_tactic()
    verified: list[dict[str, Any]] = []
    probe_evidence: list[dict[str, Any]] = []
    # Build the probe set (cap the count, drop empty / latest-rewrite-
    # reversing chains), then probe all single-step chains in ONE warm
    # batch_try (~0.02 s/probe after a one-time warm-up vs ~1.5 s spawn-fresh).
    # The rare multi-step chains use try_chain under the wall-clock deadline.
    import time as _time
    _probe_deadline = self._resolve_probe_deadline()
    _scan = candidates[:self._INSPECT_PROBE_CAP]
    _unprobed = max(0, len(candidates) - len(_scan))
    probe_items: list[tuple[dict[str, Any], list[str]]] = []
    for candidate in _scan:
        chain = [
            str(step or "").strip()
            for step in (candidate.get("chain") or [])
            if str(step or "").strip()
        ]
        if not chain:
            continue
        if any(_bridge_reverses_latest_rewrite(step, latest_tactic)
               for step in chain):
            continue
        probe_items.append((candidate, chain))
    single_idx = [i for i, (_c, ch) in enumerate(probe_items) if len(ch) == 1]
    results: list[Any] = [None] * len(probe_items)
    if single_idx:
        try:
            batch = h.cli.batch_try(
                h.dbe._session_id, [probe_items[i][1][0] for i in single_idx])
        except Exception as exc:
            batch = [{"accepted": False,
                      "error": {"kind": type(exc).__name__,
                                 "message": str(exc)}}] * len(single_idx)
        for i, r in zip(single_idx, batch):
            results[i] = r
    for i, (candidate, chain) in enumerate(probe_items):
        if len(verified) >= 3:
            break
        ev_id = f"probe.pr_bridge.{len(probe_evidence)}"
        result = results[i]
        if result is not None:
            producer = "ec_daemon.batch_try"
        else:                                  # multi-step chain -> try_chain
            if _time.monotonic() + self._PROBE_EST_S > _probe_deadline:
                _unprobed += 1
                continue
            try:
                result = h.cli.try_chain(h.dbe._session_id, chain)
                producer = "ec_daemon.try_chain"
            except Exception as exc:
                probe_evidence.append({
                    "id": ev_id,
                    "producer": "ec_daemon.exception",
                    "accepted": False,
                    "chain": chain,
                    "error_kind": type(exc).__name__,
                    "error_message": str(exc),
                })
                continue
        if not (isinstance(result, dict) and result.get("accepted")):
            err = (result or {}).get("error") or {}
            err_kind = "unknown"
            err_message = ""
            if isinstance(err, dict):
                err_kind = str(err.get("kind") or "unknown")
                err_message = str(
                    err.get("message")
                    or err.get("detail")
                    or err.get("raw")
                    or ""
                )
            elif err:
                err_message = str(err)
            probe_evidence.append({
                "id": ev_id,
                "producer": producer,
                "accepted": False,
                "chain": chain,
                "error_kind": err_kind,
                "error_message": err_message,
            })
            continue
        item = dict(candidate)
        item["evidence_id"] = ev_id
        verified.append(item)
        probe_evidence.append({
            "id": ev_id,
            "producer": producer,
            "accepted": True,
            "session_id": getattr(h.dbe, "_session_id", ""),
            "chain": chain,
            "bridge_lemma": candidate.get("bridge_lemma"),
        })
        if len(verified) >= 3:
            break
    if not verified:
        first_error = next(
            (
                str(ev.get("error_message") or ev.get("error_kind") or "")
                for ev in probe_evidence
                if ev.get("accepted") is False
            ),
            "",
        )
        _fb_text, _fb_ctx = self._named_bridge_fallback_block(raw_goal)
        return HookResult(
            text=(
                "\n[BRIDGE-OPTIONS/NO_VERIFIED_ROUTE] The manager compiled "
                f"{len(candidates)} source-derived Pr bridge candidate(s), "
                "but daemon verification accepted none of the checked "
                "chains on the current goal. No executable bridge option "
                "is surfaced.\n"
                + (f"  First verifier failure: {first_error}\n"
                   if first_error else "")
            ) + _fb_text,
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={
                "deterministic": [gate_evidence],
                "context": [context_evidence, *_fb_ctx],
                "probe": probe_evidence,
            },
            notes=[{
                "code": "bridge_options.no_verified_route",
                "message": (
                    "Candidate routes exist, but none passed daemon "
                    "verification; treat direct byequiv as a fallback only "
                    "after inspecting this failure."
                ),
            }],
            errors=[{
                "code": "bridge_options.no_verified_route",
                "message": (
                    first_error
                    or "Daemon rejected every checked bridge candidate."
                ),
            }],
        )
    out_lines = [
        "",
        "[BRIDGE-OPTIONS/VERIFIED] "
        "The manager derived type-matched Pr bridge route(s) from ProofIR "
        "endpoint typing and the daemon accepted them on the current goal.",
    ]
    for idx, candidate in enumerate(verified[:3], start=1):
        chain = candidate.get("chain") or []
        joined = " ".join(str(step).strip() for step in chain)
        bindings = candidate.get("bindings") or {}
        out_lines.append("")
        out_lines.append(f"  Option {idx}: {candidate.get('semantic_objective')}")
        out_lines.append(f"     bridge: {candidate.get('bridge_lemma')}")
        if bindings:
            binding_text = ", ".join(
                f"{k}={v}" for k, v in bindings.items() if v
            )
            if binding_text:
                out_lines.append(f"     bindings: {binding_text}")
        out_lines.append("     manager intent:")
        out_lines.append(
            "       "
            + json.dumps({
                "intent": "commit_tactic",
                "payload": {"tactic": joined},
            }, ensure_ascii=True)
        )
    out_lines.append("")
    out_lines.append(
        "  Read: prefer a verified bridge route over direct "
        "`byequiv=>//.` on the full probability equality. Direct byequiv "
        "is an accepted-but-risky fallback because it can erase the "
        "high-level game-hop structure and expose low-level oracle proof "
        "obligations too early."
    )
    if _unprobed:
        out_lines.append(
            f"  ({_unprobed} further candidate(s) were not probed under the "
            "inspect time budget — re-inspect if none of the above fit.)"
        )
    recommendations: list[dict] = []
    for idx, candidate in enumerate(verified[:3]):
        chain = [
            str(step or "").strip()
            for step in (candidate.get("chain") or [])
            if str(step or "").strip()
        ]
        joined = " ".join(chain)
        ev_id = str(candidate.get("evidence_id") or f"probe.pr_bridge.{idx}")
        name = str(candidate.get("bridge_lemma") or candidate.get("base_lemma") or "")
        recommendations.append({
            "id": f"bridge_options.verified.{idx}",
            "kind": "tactic_chain",
            "producer": str(candidate.get("producer") or "proofir_typed_bridge_frontend"),
            "action": joined,
            "why": (
                str(candidate.get("semantic_objective") or "")
                + " The full chain was accepted by the daemon on the live goal."
            ),
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": [
                "proof_state.status == open",
                "current goal still has the same Pr relation shape",
            ],
            "source_refs": [{
                "kind": "lemma",
                "id": name,
                "details": {
                    "bindings": candidate.get("bindings") or {},
                    "source": candidate.get("source") or "",
                    "intermediate_equality": (
                        candidate.get("intermediate_equality") or {}
                    ),
                },
            }],
            "evidence_refs": [ev_id],
            "metadata": {
                "bridge_kind": candidate.get("kind"),
                "lemma": name,
                "bindings": candidate.get("bindings") or {},
                "chain": chain,
                "submit": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": joined},
                },
                "risk_rank": "preferred_over_direct_byequiv",
                "effect": (
                    "commits a verified Pr bridge route; proof state changes "
                    "only if the agent submits the shown manager intent"
                ),
            },
        })
    return HookResult(
        text="\n".join(out_lines) + "\n",
        layer=2,
        kind="recommendation",
        recommendations=recommendations,
        evidence={
            "deterministic": [gate_evidence],
            "context": [context_evidence],
            "probe": probe_evidence,
        },
        notes=[{
            "code": "bridge_options.daemon_verified",
            "message": (
                "Every surfaced bridge option was accepted by the daemon "
                "against the current goal. Direct byequiv remains a risky "
                "fallback, not the preferred route."
            ),
        }],
    )


def bridge_candidates_in_goal(
    candidates: "list[dict[str, Any]]", raw_goal: str,
) -> "tuple[list[dict[str, Any]], int]":
    """Static endpoint pre-filter — drop bridge candidates whose Pr endpoints
    are disjoint from the goal WITHOUT a daemon probe.

    A bridge applies here only if one of its endpoints' game matches a game
    already in the goal's `Pr[...]` terms; a candidate targeting unrelated
    games (a wrapper branch not in this goal) cannot apply, so we read that
    off the goal instead of paying a ~1.5 s probe to learn it (the same idea
    as the relational scope filter). SAFETY: a candidate whose endpoints we
    cannot parse is KEPT — never drop on uncertainty. Returns (kept, dropped).
    """
    try:
        from core.easycrypt.analysis.ec_pr_canonical import (  # type: ignore
            game_key, pr_game_keys_from_text)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_pr_canonical import (
                game_key, pr_game_keys_from_text)
        except Exception:
            return candidates, 0
    goal_keys = set(pr_game_keys_from_text(raw_goal or ""))
    if not goal_keys:
        return candidates, 0            # cannot read goal games -> keep all
    kept: "list[dict[str, Any]]" = []
    dropped = 0
    for cand in candidates:
        ie = cand.get("intermediate_equality") or {}
        endpoints = [ie.get("from"), ie.get("to"),
                     cand.get("source_pr"), cand.get("target_pr")]
        keys = [k for k in (game_key(e) for e in endpoints if e) if k]
        if not keys or any(k in goal_keys for k in keys):
            kept.append(cand)           # in-goal, or unparseable (safety)
        else:
            dropped += 1
    return kept, dropped


def scan_named_bridge_fallback(self, raw_goal: str) -> list[dict[str, Any]]:
    """Unverified Pr=Pr rewrite-lemma candidates from the SAME scan goal-info uses
    for `pr_rewrite_candidates` — a fallback for when the typed Pr-bridge frontend
    yields nothing (it does not template wrapper-to-wrapper Pr=Pr bridges). Mirrors
    the goal-info channel exactly so the two surfaces never diverge."""
    try:
        from core.easycrypt.session_projection import (  # local: avoid import cycle
            _projection_pr_rewrite_candidates,
            parse_goal,
            read_session_state,
        )
        state = read_session_state(self.session.dir)
        raw = state.raw_for_goal_tools or raw_goal
        info = parse_goal(raw)
        return list(_projection_pr_rewrite_candidates(state, info, raw) or [])
    except Exception:
        return []


def named_bridge_fallback_block(
    self, raw_goal: str,
) -> tuple[str, list[dict[str, Any]]]:
    """(text, context-entries) for the named-lemma fallback at the typed-frontend
    empty exits, or ("", []). CANDIDATES ONLY — surfaced as context, never as a
    daemon-verified runnable recommendation, so the agent gets the named lemma the
    typed frontend cannot template instead of an empty panel."""
    named = self._scan_named_bridge_fallback(raw_goal)
    if not named:
        return "", []
    names = ", ".join(str(c.get("name") or "?") for c in named[:8])
    text = (
        "\n[BRIDGE-OPTIONS/NAMED-CANDIDATES] Same-file/context Pr=Pr rewrite-lemma "
        "candidate(s) whose endpoints match this goal (CANDIDATE, NOT daemon-verified "
        "— inspect with lookup_symbol and verify with probe_tactic before "
        f"committing): {names}\n"
    )
    ctx = [{
        "id": "context.pr_bridge_named_scan",
        "producer": "scan_pr_bridge_lemmas",
        "verification": "candidate_uncertified",
        "candidates": named[:8],
    }]
    return text, ctx


def proof_ir_pr_bridge_candidates(self, raw_goal: str) -> list[dict[str, Any]]:
    """Type-matched Pr bridge candidates from ProofIR.

    Mirrors ``_proof_ir_call_site_route``: build the typed ProofIR for the
    current proof state and read its typed Pr-bridge handles
    (``pr_typed_bridge_frontend`` and ``pr_wrapper_bridge_candidates``).
    Those come from endpoint typing, name resolution, and instantiation
    binding -- not a game-family regex template.  This is the sole source
    of bridge_options candidates; the old regex pr_bridge_compiler has been
    retired.  Returns ``[]`` on any failure (no ProofIR / no typed
    candidates), in which case ``_try_bridge_suggest`` surfaces a
    no-candidates result instead of an unverified guess.
    """
    try:
        from core.easycrypt.session_projection import (  # type: ignore
            projection_to_goal_info,
            read_proof_state_projection,
        )
        from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # type: ignore
    except Exception:
        try:
            from core.easycrypt.session_projection import (
                projection_to_goal_info,
                read_proof_state_projection,
            )
            from core.easycrypt.analysis.ec_proof_ir import build_proof_ir
        except Exception:
            return []
    try:
        projection = read_proof_state_projection(
            self.session.dir,
            live_tool_name="pivot-pr-bridge",
        )
        proof_state = projection_to_goal_info(projection)
        proof_ir = build_proof_ir(
            session_dir=self.session.dir,
            proof_state=proof_state,
            current_goal=projection.goal.to_dict(),
        )
        handles = dict(
            dict(proof_ir.get("resources") or {}).get("handles") or {}
        )
    except Exception:
        return []
    return self._typed_bridge_candidates_from_handles(handles)


def typed_bridge_candidates_from_handles(
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    """Adapt ProofIR typed Pr-bridge handles into bridge_options candidate
    dicts (``chain`` + typed metadata).

    Pure: no daemon and no I/O, so it is unit-testable for any game family.
    The runnable authority still comes from the daemon probe in
    ``_try_bridge_suggest``; this only proposes type-derived chains.
    """
    frontend = handles.get("pr_typed_bridge_frontend") or {}
    entries: list[dict[str, Any]] = []
    # wrapper_bridges carry endpoint-anchored runnable `have ->` tactics
    # (incl. scheme normalizations); read them before the generic
    # instantiated_rewrites so the highest-priority chains are probed first.
    for key in ("wrapper_bridges", "instantiated_rewrites"):
        for item in (frontend.get(key) or []):
            if isinstance(item, dict):
                entries.append(item)
    for item in (handles.get("pr_wrapper_bridge_candidates") or []):
        if isinstance(item, dict):
            entries.append(item)
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        chain = typed_bridge_chain(entry)
        if not chain:
            continue
        lemma = str(
            entry.get("bridge_lemma")
            or entry.get("lemma")
            or entry.get("name")
            or ""
        )
        bindings = {
            key: entry.get(key)
            for key in ("adapter_module", "lhs_game", "rhs_game")
            if entry.get(key)
        }
        source_pr = str(entry.get("source_pr") or "")
        target_pr = str(entry.get("target_pr") or "")
        intermediate = (
            {
                "from": source_pr,
                "to": target_pr,
                "closer_family": "byequiv_proc_inline_sim",
            }
            if source_pr and target_pr else {}
        )
        candidates.append({
            "kind": str(entry.get("edge_kind") or "typed_pr_bridge"),
            "producer": "proofir_typed_bridge_frontend",
            "semantic_objective": str(
                entry.get("reason")
                or "Apply a type-matched Pr bridge/rewrite derived from "
                "ProofIR endpoint typing and name resolution."
            ),
            "bridge_lemma": lemma,
            "base_lemma": lemma,
            "bindings": bindings,
            "chain": chain,
            "intermediate_equality": intermediate,
            "source": "proof_ir_typed_bridge_frontend",
        })
    return candidates


def typed_bridge_chain(entry: dict[str, Any]) -> list[str]:
    """Extract a runnable single-tactic chain from a typed bridge entry,
    stripping any trailing ``(* ... *)`` annotation.  Non-runnable
    descriptive hints (e.g. ``Pr structural bridge: ...``) are rejected so
    only daemon-checkable tactics reach verification."""
    raw = ""
    for key in ("tactic", "action_hint"):
        value = str(entry.get(key) or "").strip()
        if value:
            raw = value
            break
    if not raw:
        return []
    code = raw.split("(*")[0].strip()
    if not code or not code.endswith("."):
        return []
    if code.lower().startswith("pr structural bridge"):
        return []
    return [code]


def dedupe_bridge_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Dedupe candidates by tactic chain, preserving order so the
    highest-priority typed ProofIR candidates are kept first."""
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        key = tuple(
            str(step).strip()
            for step in (candidate.get("chain") or [])
            if str(step).strip()
        )
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def up_to_bad_call_coherence(self, raw_goal: str):
    """Mechanism CORRECT — up-to-bad call-coherence flag (flag-only, neutral).

    Sticky fact: scan the committed `byequiv`/`equiv`/`conseq` tactics (and the
    current goal head) for a TOP-LEVEL `\\/ bad` disjunct in the postcondition —
    the up-to-bad shape where the relation is allowed to break on bad. If the
    latest committed `call (_: inv)` is the LOCKSTEP single-clause form and does
    not already track an active bad name, return a `(line, rec)` pair surfacing
    the up-to-bad `call (_: bad, inv)` candidate as an UNCERTIFIED suggestion.
    Returns ``None`` when no incoherence (pure-equiv post, bad only in an
    implication, or the call is already the 2-clause form)."""
    try:
        from core.easycrypt.up_to_bad_coherence import (  # type: ignore
            coherence_flag, latest_relational_call, up_to_bad_names)
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import (  # type: ignore
                coherence_flag, latest_relational_call, up_to_bad_names)
        except Exception:
            return None
    tactics = self._committed_tactics()
    # Active bad names: union of the byequiv/equiv/conseq committed posts that
    # establish an up-to-bad disjunct, plus the current goal head's post.
    active: set[str] = set(up_to_bad_names(raw_goal or ""))
    for t in tactics:
        head = t.lower().lstrip("+-* ").split("(")[0].split()[0] if t.strip() else ""
        if head in ("byequiv", "equiv", "conseq", "byphoare"):
            active |= up_to_bad_names(t)
    if not active:
        return None
    # Key on the most recent RELATIONAL `call (_: ...)` — NOT the temporally
    # last `call` of any kind. A lemma-application call (`call (some_lemma ...).`)
    # or a one-sided phoare bad-preservation call (`call (_: UFCMA.bad1).`)
    # committed AFTER the lockstep relational call must not mask it (audit
    # 2026-06-09: step4_1 resume Tree_0_1's three lockstep calls at prefix
    # L16-18 were hidden behind L34's `call (some_lemma ...)`).
    latest_call = latest_relational_call(tactics)
    if not latest_call:
        return None
    # Build the post the flag keys on: prefer the current goal head if it carries
    # the disjunct, else a synthetic `==> ... \/ bad` from the sticky names.
    post = raw_goal if up_to_bad_names(raw_goal or "") else (
        "==> ={res} \\/ " + " \\/ ".join(sorted(active)))
    src_text = None
    try:
        ctx = (self.session.dir / "context.ec")
        if ctx.exists():
            src_text = ctx.read_text(encoding="utf-8", errors="replace")
    except Exception:
        src_text = None
    flag = coherence_flag(post, latest_call, source_text=src_text)
    if flag is None:
        return None
    line = (
        "\n  [UP-TO-BAD CALL COHERENCE — suspect] " + flag["text"]
        + "\n      candidate (UNCERTIFIED): " + str(flag.get("candidate", "")))
    rec = {
        "id": "up_to_bad_call.coherence",
        "kind": "up_to_bad_call",
        "producer": "up_to_bad_coherence",
        "action": flag.get("candidate", ""),
        "committable": False,
        "verified": "structural_candidate",
        "active_bad_events": flag.get("active_bad_events", []),
        "derivation": (
            "the upstream postcondition admits a top-level `\\/ bad` disjunct "
            "(relation may break on bad) but the committed call is lockstep "
            "single-clause — the games diverge once bad fires"),
        "guarantee": flag.get("guarantee", ""),
        "decision_context_key": flag.get("key", "up_to_bad_call"),
        "decision_context_text": flag.get("text", ""),
    }
    return line, rec


def called_adversary_roots(goal_text: str) -> "set[str]":
    """The called adversary module root(s) at a ``call (_: ...)`` obligation.
    At the call frontier the callee's own ``={glob A}`` is always rejected
    (the call rule forbids constraining the callee's glob), so it can be
    dropped from the glob singleton scan without paying a probe. Read from
    two robust signals on the goal head: the ``x <@ A(...)`` call statement
    and the callee's ``(glob A)`` equality that the call rule puts in the
    precondition (the latter survives the two-column program layout)."""
    text = goal_text or ""
    return (set(_CALL_CALLEE.findall(text))
            | set(_GLOB_MENTION.findall(text)))
