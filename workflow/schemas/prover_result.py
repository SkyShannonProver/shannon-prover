"""Schema for prover agent output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProverResult:
    """Result of a prover run."""

    session_id: str = ""
    proved: bool = False
    ec_file_verified: bool = False
    turns: int = 0
    elapsed_seconds: float = 0.0
    skipped: bool = False
    error: str = ""
    ec_session_dir: str = ""
    event_contract_checked: bool = False
    event_contract_ok: bool = False
    event_contract_errors: list[str] = field(default_factory=list)
    archived_ec_session_dirs: list[str] = field(default_factory=list)
    resume_capsules: list[str] = field(default_factory=list)
    information_source_audit: list[dict] = field(default_factory=list)
    proof_bank_recorded: bool = False
    notes: str = ""  # prover self-report (legacy free-text)
    # Structured self-report: suggestions, open_questions, discoveries,
    # agent_view_observations, commit_response_observations
    report: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ProverResult:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
