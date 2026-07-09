"""Schema for Proof Planner agent output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Literal


@dataclass
class PlanPhase:
    """One phase of a proof plan."""

    phase: int  # 1, 2, 3...
    goal: str  # e.g. "Prove losslessness of PIR.main"
    step_type: Literal["strategy", "execution"] = "execution"
    # strategy = structural choice (byequiv vs bypr, proc vs transitivity).
    #   If this fails, the prover should re-read the current state.
    # execution = tactic details within a strategy (rnd args, smt hints, auto).
    #   If this fails, the prover should try different tactic forms, NOT abandon the strategy.
    tactics: List[str] = field(default_factory=list)
    # Suggested tactic templates (may have [FILL] placeholders)
    checkpoint: str = ""
    # Expected state after this phase, e.g. "Hll : islossless PIR.main in context"
    fallback: str = ""
    # Alternative approach if primary fails
    confidence: Literal["high", "medium", "speculative"] = "medium"
    # high = verified examples; medium = reasonable inference; speculative = best guess


@dataclass
class ContextBrief:
    """Minimal planner context passed to provers.

    Source text and planner-derived summaries are intentionally not embedded in
    the prover prompt; the agent reads source files on demand.
    """
    file_content: str = ""         # legacy; no longer rendered into prompts
    goal_type: str = ""            # probability / pRHL / equiv / eager / hoare / phoare / ambient
    target_statement: str = ""     # the lemma statement
    available_lemmas: List[dict] = field(default_factory=list)
    # [{"name": "prD4", "statement": "...", "status": "proved/admit"}]
    program_summary: str = ""      # what the target program does
    irrelevant_topics: List[str] = field(default_factory=list)  # what to skip


@dataclass
class ProofPlan:
    """Full output of the Proof Planner agent."""

    target_file: str
    target_lemma: str
    difficulty: Literal["easy", "easy-medium", "medium", "medium-hard", "hard"] = "medium"
    approach_summary: str = ""  # 1-2 sentence high-level strategy
    reasoning: str = ""
    # WHY this strategy — the structural insight the planner discovered.
    # e.g. "Both games have identical structure after inlining. DDHAdv wraps
    # CPA's logic: CPA.sk maps to DDH0.x, CPA.pk = g^sk maps to g^x.
    # After inline, left has 7 statements, right has 5. Swap alignment needed."
    program_analysis: str = ""
    # Structural analysis of the programs: what each side does, how they
    # correspond, where they differ. The prover reads this instead of
    # re-analyzing the file.
    phases: List[PlanPhase] = field(default_factory=list)
    known_pitfalls: List[str] = field(default_factory=list)  # e.g. ["P1", "P9"]
    context_brief: ContextBrief = field(default_factory=ContextBrief)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ProofPlan:
        data = json.loads(path.read_text(encoding="utf-8"))
        phases_raw = data.pop("phases", [])
        brief_data = data.pop("context_brief", {})
        # Filter to known fields for backward compat
        phase_fields = {"phase", "goal", "step_type", "tactics",
                        "checkpoint", "fallback", "confidence"}
        phases = [PlanPhase(**{k: v for k, v in p.items() if k in phase_fields})
                  for p in phases_raw]
        plan_fields = {f.name for f in cls.__dataclass_fields__.values()}
        plan_fields -= {"phases", "context_brief"}
        filtered = {k: v for k, v in data.items() if k in plan_fields}
        brief_fields = {f.name for f in ContextBrief.__dataclass_fields__.values()}
        brief_filtered = {
            k: v for k, v in brief_data.items()
            if k in brief_fields
        } if isinstance(brief_data, dict) else {}
        brief = ContextBrief(**brief_filtered) if brief_filtered else ContextBrief()
        return cls(**filtered, phases=phases, context_brief=brief)
