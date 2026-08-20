"""Schema for orchestrator run configuration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

from workflow.tree.policy import DEFAULT_TREE_INITIAL_PROVERS, TREE_MAX_ACTIVE_NODES
from workflow.proof_state_compiler.profile_ids import (
    DEFAULT_CURRENT_SURFACE_PROFILE,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_public_surface_profile_id,
)


DEFAULT_CLAUDE_MODEL = "claude-opus-4-8"
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
SUPPORTED_AGENT_BACKENDS = frozenset({"claude", "codex"})


def normalize_agent_backend(value: str | None) -> str:
    backend = str(value or "codex").strip().lower()
    if backend not in SUPPORTED_AGENT_BACKENDS:
        supported = ", ".join(sorted(SUPPORTED_AGENT_BACKENDS))
        raise ValueError(
            f"unsupported prover agent backend {value!r}; expected one of: {supported}"
        )
    return backend


def default_model_for_backend(value: str | None) -> str:
    return (
        DEFAULT_CODEX_MODEL
        if normalize_agent_backend(value) == "codex"
        else DEFAULT_CLAUDE_MODEL
    )


@dataclass
class ProverConfig:
    timeout_minutes: int = 20
    max_rounds: int = 40
    max_total_tactics: int = 1000
    max_stale_rounds: int = 4
    # OpenAI Codex is the canonical proof-node agent. Claude remains an
    # explicit experiment backend, never an implicit runtime default.
    agent_backend: str = "codex"
    model: str = ""
    effort: str = "high"
    mode: str = "tree"
    # Tree mode parameters (only used when mode == "tree")
    # root provers to start simultaneously
    tree_initial_provers: int = DEFAULT_TREE_INITIAL_PROVERS
    tree_max_concurrent: int = TREE_MAX_ACTIVE_NODES  # max active provers at once
    tree_stuck_errors: int = 4         # errors since last accept to trigger spawn
    tree_stuck_idle_seconds: int = 180  # idle since last accept to trigger spawn
    tree_grace_seconds: int = 300      # grace period for stuck prover after child spawns
    tree_max_depth: int = 6            # max recursion depth (safety cap)
    tree_min_alive_seconds: int = 300  # min time before stuck detection (5 min)
    tree_progress_gap_ratio: float = 3.0  # kill laggard only if leader has 3x tactics
    tree_progress_gap_idle: int = 180  # ...and laggard idle for at least 3 min
    tree_structural_undo_spawn_delay_seconds: int = 300  # wait for self-repair after undo
    tree_undo_repair_protection_seconds: int = 900  # high-water protection after undo
    resume_root_policy: str = "score"  # "score" | "diversity"
    # Rationale: tree mode is an experiment scheduler, not a best-first
    # tactic counter.  Earlier defaults killed promising deep frontiers while
    # replay-only children inherited large tactic counts from their parents.
    # The supervisor now protects valuable frontiers and treats replayed
    # prefix tactics as state recovery, so these defaults can favor honest
    # one-hour calibration runs over aggressive early pruning.

    def __post_init__(self) -> None:
        self.agent_backend = normalize_agent_backend(self.agent_backend)
        if not str(self.model or "").strip():
            self.model = default_model_for_backend(self.agent_backend)
        if self.mode != "tree":
            raise ValueError("unsupported prover mode; only 'tree' is current")


@dataclass
class RunConfig:
    """Configuration for one orchestrator run."""

    # Target lemma
    file: str  # e.g. "eval/examples/cramer-shoup/cramer_shoup.ec"
    lemma: str  # e.g. "CCA_DDH0"
    include_dir: str = ""

    # Human proof reference (outside project dir for isolation)
    human_proof_dir: Optional[str] = None
    # e.g. "../Shannon_Prover_HumanProofs"

    # Iteration control. Retained for config back-compat; no longer drives a
    # retry loop (the analyst/improver/regression phases were removed).
    max_iterations: int = 2

    # Agent configs
    prover: ProverConfig = field(default_factory=ProverConfig)

    # Output
    output_dir: str = "workflow/runs"

    # Evaluation mode: blind the prover to the target lemma's existing proof.
    # Prompt/rendering code blocks cached or prior proof material for the
    # target lemma while leaving sibling source lemmas available.
    eval_mode: bool = False

    # Current proof-state surface profile. This controls only the
    # agent-facing proof-state surface and manager intents; EasyCrypt remains
    # the verifier, and tree/search topology is configured separately through
    # ``prover.mode`` and ``prover.tree_initial_provers``.
    surface_profile: str = DEFAULT_CURRENT_SURFACE_PROFILE

    # Proof-node resume capsules. These are produced by failed/interrupted
    # tree/eval runs and replay a verified tactic prefix before handing the
    # remaining state to the prover. They are for continuation debugging, not
    # from-scratch eval scoring.
    resume_capsules: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.surface_profile = normalize_public_surface_profile_id(
            self.surface_profile
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> RunConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        prover_data = data.pop("prover", {})
        # Drop keys not on the current schema so configs saved by older versions
        # (e.g. the removed `regression`/`analyst_mode` fields) still load
        # instead of raising TypeError on an unexpected keyword argument.
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        prover_known = {f.name for f in fields(ProverConfig)}
        prover_data = {k: v for k, v in prover_data.items() if k in prover_known}
        return cls(
            **data,
            prover=ProverConfig(**prover_data),
        )


# Singleton used by run()/run_tree_prover() signatures so tree-knob defaults
# have exactly one home (they had drifted: 3/4 and 5/4 vs the 4/6 here).
PROVER_DEFAULTS = ProverConfig()
