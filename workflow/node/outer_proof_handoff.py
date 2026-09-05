"""Invocation-bound handoff from an outer proof constructor to a proof node.

This is distinct from a proof-node resume capsule.  A resume capsule preserves
one manager-owned session across prover invocations.  An outer proof handoff
certifies, in a fresh manager preparation session, the longest prefix of a
same-experiment file-level candidate and lets the inner node replay that exact
prefix before continuing.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HANDOFF_KIND = "outer_proof_handoff"
HANDOFF_VERSION = 3
RESOURCE_ANCHOR_MAX = 8
CANDIDATE_SUFFIX_MAX_CHARS = 200_000
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GOAL_HASH = re.compile(r"[0-9a-f]{40,128}")
_FORBIDDEN_REPLAY = re.compile(
    r"(?i)^\s*(?:[+*\-]\s*)?(?:admit|abort|exit|qed)\s*\.\s*$"
)
_ANCHOR_USES = frozenset({"apply", "call", "exact", "rewrite", "smt", "reference"})


def _text(value: Any, *, field: str, limit: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"outer proof handoff field {field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"outer proof handoff field {field} must be non-empty")
    if len(value) > limit:
        raise ValueError(
            f"outer proof handoff field {field} exceeds {limit} characters"
        )
    return value


def _hash(value: Any, *, field: str) -> str:
    value = _text(value, field=field, limit=64, required=True)
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"outer proof handoff field {field} is not a SHA-256")
    return value


@dataclass(frozen=True)
class OuterProofResourceAnchor:
    """One EasyCrypt-resolved declaration intentionally handed to the inner node."""

    symbol: str
    intended_use: str
    role: str
    source_ref: str
    declaration_sha256: str
    declaration: str

    def manager_context(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "intended_use": self.intended_use,
            "role": self.role,
            "source_ref": self.source_ref,
            "declaration_sha256": self.declaration_sha256,
            "declaration": self.declaration,
        }


def _resource_anchors(value: Any) -> tuple[OuterProofResourceAnchor, ...]:
    if not isinstance(value, list):
        raise ValueError("outer proof handoff briefing.resource_anchors must be a list")
    if len(value) > RESOURCE_ANCHOR_MAX:
        raise ValueError(
            "outer proof handoff briefing.resource_anchors exceeds bounded budget"
        )
    anchors: list[OuterProofResourceAnchor] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"outer proof resource anchor {index} must be an object")
        prefix = f"briefing.resource_anchors[{index}]"
        symbol = _text(raw.get("symbol"), field=f"{prefix}.symbol", limit=256, required=True)
        if not all(
            part
            and (part[0].isalpha() or part[0] == "_")
            and all(char.isalnum() or char in "_'" for char in part)
            for part in symbol.split(".")
        ):
            raise ValueError(f"outer proof resource anchor {symbol!r} is not a valid symbol")
        if symbol in seen:
            raise ValueError(f"duplicate outer proof resource anchor {symbol!r}")
        intended_use = _text(
            raw.get("intended_use"),
            field=f"{prefix}.intended_use",
            limit=16,
            required=True,
        )
        if intended_use not in _ANCHOR_USES:
            raise ValueError(
                f"outer proof resource anchor {symbol!r} has invalid intended_use"
            )
        role = _text(raw.get("role"), field=f"{prefix}.role", limit=500, required=True)
        source_ref = _text(
            raw.get("source_ref"), field=f"{prefix}.source_ref", limit=2000, required=True
        )
        declaration = _text(
            raw.get("declaration"),
            field=f"{prefix}.declaration",
            limit=12000,
            required=True,
        )
        declaration_sha256 = _hash(
            raw.get("declaration_sha256"), field=f"{prefix}.declaration_sha256"
        )
        if hashlib.sha256(declaration.encode("utf-8")).hexdigest() != declaration_sha256:
            raise ValueError(
                f"outer proof resource anchor {symbol!r} declaration hash mismatch"
            )
        seen.add(symbol)
        anchors.append(OuterProofResourceAnchor(
            symbol=symbol,
            intended_use=intended_use,
            role=role,
            source_ref=source_ref,
            declaration_sha256=declaration_sha256,
            declaration=declaration,
        ))
    return tuple(anchors)


@dataclass(frozen=True)
class OuterProofHandoff:
    path: Path
    target_file: str
    lemma: str
    source_commit: str
    outer_run_dir: str
    candidate_source: str
    candidate_sha256: str
    replay_commands: tuple[str, ...]
    replay_commands_sha256: str
    committed_spine_count: int
    committed_spine_sha256: str
    boundary_goal_hash: str
    goal_identity_required: bool
    failed_tactic: str
    failure_summary: str
    strategy_note: str
    candidate_suffix: str
    current_goal_preview: str
    resource_anchors: tuple[OuterProofResourceAnchor, ...]

    def manager_context(self) -> dict[str, Any]:
        return {
            "kind": HANDOFF_KIND,
            "version": HANDOFF_VERSION,
            "manifest": str(self.path),
            "outer_run_dir": self.outer_run_dir,
            "candidate_source": self.candidate_source,
            "candidate_sha256": self.candidate_sha256,
            "accepted_command_count": len(self.replay_commands),
            "accepted_commands_sha256": self.replay_commands_sha256,
            "committed_spine_count": self.committed_spine_count,
            "committed_spine_sha256": self.committed_spine_sha256,
            "boundary_goal_hash": self.boundary_goal_hash,
            "goal_identity_required": self.goal_identity_required,
            "failed_tactic": self.failed_tactic,
            "failure_summary": self.failure_summary,
            "strategy_note": self.strategy_note,
            "candidate_suffix": self.candidate_suffix,
            "current_goal_preview": self.current_goal_preview,
            "resource_anchors": [
                anchor.manager_context() for anchor in self.resource_anchors
            ],
        }


def proof_command_sequence_sha256(
    commands: list[str] | tuple[str, ...],
) -> str:
    raw = json.dumps(
        list(commands), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_outer_proof_handoff(path: str | Path) -> OuterProofHandoff:
    manifest = Path(path).expanduser().resolve()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"could not read outer proof handoff {manifest}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("outer proof handoff must be a JSON object")
    if data.get("kind") != HANDOFF_KIND:
        raise ValueError(f"not an outer proof handoff: {manifest}")
    if data.get("version") != HANDOFF_VERSION:
        raise ValueError(
            f"unsupported outer proof handoff version: {data.get('version')!r}"
        )

    target = data.get("target")
    source = data.get("source")
    replay = data.get("replay")
    boundary = data.get("boundary")
    briefing = data.get("briefing")
    if not all(isinstance(item, dict) for item in (target, source, replay, boundary, briefing)):
        raise ValueError("outer proof handoff is missing a required object")

    commands_raw = replay.get("commands")
    if not isinstance(commands_raw, list):
        raise ValueError("outer proof handoff replay.commands must be a list")
    commands: list[str] = []
    for index, item in enumerate(commands_raw):
        command = _text(
            item, field=f"replay.commands[{index}]", limit=20000, required=True
        )
        if _FORBIDDEN_REPLAY.fullmatch(command):
            raise ValueError(
                f"outer proof handoff replay.commands[{index}] is a forbidden closer"
            )
        commands.append(command)
    claimed_commands_hash = _hash(
        replay.get("commands_sha256"), field="replay.commands_sha256"
    )
    actual_commands_hash = proof_command_sequence_sha256(commands)
    if claimed_commands_hash != actual_commands_hash:
        raise ValueError("outer proof handoff replay command hash mismatch")
    accepted_command_count = replay.get("accepted_command_count")
    if (
        isinstance(accepted_command_count, bool)
        or not isinstance(accepted_command_count, int)
        or accepted_command_count != len(commands)
    ):
        raise ValueError(
            "outer proof handoff replay accepted-command count mismatch"
        )
    committed_spine_count = replay.get("committed_spine_count")
    if (
        isinstance(committed_spine_count, bool)
        or not isinstance(committed_spine_count, int)
        or committed_spine_count < len(commands)
    ):
        raise ValueError(
            "outer proof handoff replay committed-spine count is invalid"
        )
    committed_spine_sha256 = _hash(
        replay.get("committed_spine_sha256"),
        field="replay.committed_spine_sha256",
    )

    identity_required = boundary.get("goal_identity_required")
    if type(identity_required) is not bool:
        raise ValueError(
            "outer proof handoff boundary.goal_identity_required must be boolean"
        )
    goal_hash = _text(
        boundary.get("goal_hash"), field="boundary.goal_hash", limit=128
    )
    if identity_required:
        if _GOAL_HASH.fullmatch(goal_hash) is None:
            raise ValueError("open outer proof handoff boundary requires a goal hash")
    elif goal_hash:
        raise ValueError("closed outer proof handoff boundary must omit goal hash")

    return OuterProofHandoff(
        path=manifest,
        target_file=_text(
            target.get("file"), field="target.file", limit=2000, required=True
        ),
        lemma=_text(target.get("lemma"), field="target.lemma", limit=256, required=True),
        source_commit=_text(
            source.get("commit"), field="source.commit", limit=128, required=True
        ),
        outer_run_dir=_text(
            source.get("outer_run_dir"),
            field="source.outer_run_dir",
            limit=2000,
            required=True,
        ),
        candidate_source=_text(
            source.get("candidate_source"),
            field="source.candidate_source",
            limit=2000,
            required=True,
        ),
        candidate_sha256=_hash(
            source.get("candidate_sha256"), field="source.candidate_sha256"
        ),
        replay_commands=tuple(commands),
        replay_commands_sha256=claimed_commands_hash,
        committed_spine_count=committed_spine_count,
        committed_spine_sha256=committed_spine_sha256,
        boundary_goal_hash=goal_hash,
        goal_identity_required=identity_required,
        failed_tactic=_text(
            boundary.get("failed_tactic"),
            field="boundary.failed_tactic",
            limit=20000,
        ),
        failure_summary=_text(
            boundary.get("failure_summary"),
            field="boundary.failure_summary",
            limit=8000,
        ),
        strategy_note=_text(
            briefing.get("strategy_note"),
            field="briefing.strategy_note",
            limit=8000,
        ),
        candidate_suffix=_text(
            briefing.get("candidate_suffix"),
            field="briefing.candidate_suffix",
            limit=CANDIDATE_SUFFIX_MAX_CHARS,
        ),
        current_goal_preview=_text(
            boundary.get("current_goal_preview"),
            field="boundary.current_goal_preview",
            limit=20000,
        ),
        resource_anchors=_resource_anchors(briefing.get("resource_anchors", [])),
    )
