"""Canonical terminal result for one complete Shannon prover run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROVER_RUN_VERIFIED = "verified"
PROVER_RUN_INCOMPLETE = "incomplete"
PROVER_RUN_INFRASTRUCTURE_INVALID = "infrastructure_invalid"
PROVER_RUN_STATUSES = frozenset({
    PROVER_RUN_VERIFIED,
    PROVER_RUN_INCOMPLETE,
    PROVER_RUN_INFRASTRUCTURE_INVALID,
})


@dataclass
class ProverResult:
    """Only run-level owner of the terminal proof outcome.

    Session and tree layers may produce completion candidates.  They cannot set
    this result to ``verified``.  A verified result requires the run coordinator
    to bind an exact candidate (or an already-verified precheck) to EasyCrypt
    verification evidence.
    """

    status: str = PROVER_RUN_INCOMPLETE
    session_id: str = ""
    turns: int = 0
    elapsed_seconds: float = 0.0
    skipped: bool = False
    error: str = ""
    selected_node_id: str = ""
    ec_session_dir: str = ""
    completion_candidate: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    infrastructure_errors: list[str] = field(default_factory=list)
    event_contract_checked: bool = False
    event_contract_ok: bool = False
    event_contract_errors: list[str] = field(default_factory=list)
    archived_ec_session_dirs: list[str] = field(default_factory=list)
    resume_capsules: list[str] = field(default_factory=list)
    information_source_audit: list[dict] = field(default_factory=list)
    notes: str = ""
    report: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in PROVER_RUN_STATUSES:
            raise ValueError(f"unsupported prover run status: {self.status!r}")
        verification_status = str(self.verification.get("status") or "")
        if self.status == PROVER_RUN_VERIFIED and verification_status != "pass":
            raise ValueError("verified prover run requires passing verification")
        if self.status == PROVER_RUN_INFRASTRUCTURE_INVALID and not (
            self.infrastructure_errors or self.error
        ):
            raise ValueError("infrastructure-invalid run requires an error")
        if self.status != PROVER_RUN_VERIFIED and verification_status == "pass":
            raise ValueError("passing verification must produce a verified run")

    @property
    def is_verified(self) -> bool:
        return self.status == PROVER_RUN_VERIFIED

    @property
    def result_id(self) -> str:
        payload = self._payload()
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _payload(self) -> dict[str, Any]:
        return asdict(self)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "result_id": self.result_id, **self._payload()}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "ProverResult":
        data = json.loads(path.read_text(encoding="utf-8"))
        if type(data) is not dict or data.get("schema_version") != 1:
            raise ValueError("unsupported ProverResult schema")
        result = cls(**{
            key: value
            for key, value in data.items()
            if key in cls.__dataclass_fields__
        })
        if data.get("result_id") != result.result_id:
            raise ValueError("ProverResult identity hash mismatch")
        return result


__all__ = [
    "PROVER_RUN_INCOMPLETE",
    "PROVER_RUN_INFRASTRUCTURE_INVALID",
    "PROVER_RUN_STATUSES",
    "PROVER_RUN_VERIFIED",
    "ProverResult",
]
