"""Hint generation dispatcher — Layer-1 of the 4-layer hint pipeline.

The 4-layer hint generation pipeline (see
``memory/project_hint_generation_design.md`` and the design notes in
the README) splits prover hint production into:

  Layer 1 — Hint Source: produce candidate tactics from the goal
            (deterministic, no LLM, no daemon).
  Layer 2 — Daemon Verification: probe each candidate via
            ``daemon.try_tactic`` and stamp epistemic status.
  Layer 3 — ProofContextView Surface: route accepted candidates into
            canonical prover actions.
  Layer 4 — Confidence-aware Surface: ladder runnable / probe / hint
            by confidence so the agent can override.

Until this module landed, every Layer-1 producer was a hand-rolled
``CommitPhase`` that re-implemented its own gate, daemon loop, and rec
shape. New shapes (e.g. ``AbstractAdvCallHintPhase``,
``SwapAlignHintPhase``) duplicated that machinery. This dispatcher
centralizes:

  * goal-shape gating via ``applies_to_shape`` → no per-phase if/elif
  * the daemon-verify gate (Layer 2) so every generator gets the same
    epistemic stamping
  * the ``HookResult`` rec shape so generators only need to produce
    ``Candidate`` tuples

Existing legacy phases (``PivotStrategyPhase``, ``AutoDiffPhase``,
``AutoSigPhase``) are left in place to avoid a risky big-bang refactor;
new generators should be added by registering a ``HintGenerator``
implementation here and the dispatcher will wire it into the commit
pipeline automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class Candidate:
    """A single tactic candidate emitted by a Layer-1 generator.

    ``tactic`` must be a complete, syntactically valid EasyCrypt tactic
    string ending in ``.``. ``why`` is human-readable rationale shown
    to the agent. ``source_modules`` and ``metadata`` are optional
    structured tags surfaced in the eventual recommendation; they let
    the agent (and replay tools) understand the candidate's origin.
    """
    tactic: str
    why: str
    source_modules: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class HintGenerator(Protocol):
    """Protocol for Layer-1 hint generators.

    A generator declares the goal shapes it applies to and produces a
    list of ``Candidate`` tactics from the current commit context.
    Daemon verification is centralized in the dispatcher — generators
    must NOT call the daemon themselves.
    """

    producer_name: str
    """Identifier for the producer field on emitted recommendations
    (e.g., ``"AUTO-ABSTRACT-ADV-CALL"``)."""

    marker: str
    """Display marker prefix (e.g., ``"[AUTO-ABSTRACT-ADV-CALL]"``)."""

    layer: int
    """Default display layer for this generator's HookResult."""

    def applies_to_shape(self, goal_type: str) -> bool:
        """Return True iff this generator should run on a goal whose
        ``classify_goal`` output is ``goal_type``."""
        ...

    def generate(self, ctx: Any) -> list[Candidate]:
        """Produce candidate tactics. Pure: no daemon, no I/O beyond
        reading ``ctx.active_goal`` and the session's static context
        files. Returning ``[]`` means "no candidates for this commit"."""
        ...


@dataclass
class DispatchResult:
    """Output of ``dispatch_hints`` for a single generator.

    Generators that produce no candidates or whose candidates are all
    rejected by the daemon yield ``accepted=[]``; the caller chooses
    whether to suppress the entire HookResult in that case.
    """
    producer: "HintGenerator"
    accepted: list[Candidate]
    rejected: list[Candidate]


def dispatch_hints(
    ctx: Any,
    generators: list[HintGenerator],
    *,
    goal_type: Optional[str] = None,
    probe_budget_per_generator: int = 6,
) -> list[DispatchResult]:
    """Run Layer-1 generators that match the current goal shape and
    Layer-2 daemon-verify each candidate they produce.

    Generators are filtered by ``applies_to_shape(goal_type)`` so each
    generator sees only goals it can reason about. ``goal_type`` is
    derived from ``ctx.active_goal`` via ``classify_goal`` if not
    supplied. ``probe_budget_per_generator`` caps daemon calls so a
    generator that produces a long list of speculative candidates
    cannot stall the commit pipeline.

    Returns one ``DispatchResult`` per generator that ran; generators
    that did not match the shape, raised, or had no daemon are simply
    omitted.
    """
    if goal_type is None:
        goal_type = _classify(ctx)
    h = ctx.daemon() if hasattr(ctx, "daemon") else None
    if h is None:
        return []
    out: list[DispatchResult] = []
    for gen in generators:
        try:
            if not gen.applies_to_shape(goal_type):
                continue
            candidates = gen.generate(ctx) or []
        except Exception:
            continue
        if not candidates:
            continue
        accepted: list[Candidate] = []
        rejected: list[Candidate] = []
        seen: set[str] = set()
        probed = 0
        for cand in candidates:
            tac = (cand.tactic or "").strip()
            if not tac or tac in seen:
                continue
            seen.add(tac)
            if probed >= probe_budget_per_generator:
                break
            probed += 1
            try:
                vres = h.cli.try_tactic(h.dbe._session_id, tac)
            except Exception:
                continue
            if vres.get("accepted"):
                accepted.append(cand)
            else:
                rejected.append(cand)
        out.append(DispatchResult(
            producer=gen, accepted=accepted, rejected=rejected,
        ))
    return out


def candidates_to_recommendations(
    result: DispatchResult,
    *,
    rec_kind: str = "tactic_candidate",
) -> list[dict[str, Any]]:
    """Convert accepted ``Candidate``s into recommendation dicts in
    the canonical Layer-3 shape (``runnable_tactic``, verified,
    ``daemon_probe_accepted``).

    Generators that need to emit a HookResult call this helper to
    avoid hand-rolling the rec dict (which historically was a frequent
    source of bucket-misclassification bugs).
    """
    producer = result.producer
    out: list[dict[str, Any]] = []
    for idx, cand in enumerate(result.accepted):
        ev_id = f"probe.{producer.producer_name.lower().replace('-', '_')}.{idx}"
        out.append({
            "id": f"{producer.producer_name.lower().replace('-', '_')}.{idx}",
            "kind": rec_kind,
            "producer": producer.producer_name,
            "action": cand.tactic,
            "why": cand.why,
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": [
                "proof_state.status == open",
            ],
            "source_refs": [
                {"kind": "module", "id": m} for m in cand.source_modules
            ],
            "evidence_refs": [ev_id],
            "metadata": {
                "epistemic_status": "daemon_probe_accepted",
                "cost": "cheap",
                **cand.metadata,
            },
        })
    return out


def _classify(ctx: Any) -> str:
    goal = getattr(ctx, "active_goal", "") or ""
    if not goal:
        return ""
    try:
        from core.easycrypt.analysis.ec_goal_parser import classify_goal  # type: ignore
    except Exception:
        try:
            from core.easycrypt.analysis.ec_goal_parser import classify_goal  # type: ignore  # noqa: E501
        except Exception:
            return ""
    try:
        return classify_goal(goal)
    except Exception:
        return ""
