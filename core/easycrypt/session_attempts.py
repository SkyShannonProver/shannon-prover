"""Recent tactic-attempt facts for EasyCrypt sessions.

This pass reads failed speculative tactics and groups similar failures. It is
behavioral evidence only: it does not know which failures are strategically
important, and it does not suggest repairs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


_STRUCTURAL_ERROR_PATTERNS = (
    re.compile(r"wrong number of arguments", re.I),
    re.compile(r"not accessible by name", re.I),
    re.compile(r"unknown variable or constant.*module", re.I),
    re.compile(r"argument count mismatch", re.I),
)


@dataclass(frozen=True)
class FailedTacticAttempt:
    tactic: str
    error_text: str = ""
    error_kind: str = ""
    event_id: str = ""
    lemma: str = ""
    module_args: tuple[str, ...] = ()
    structural_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tactic": self.tactic,
            "error_text": self.error_text,
            "error_kind": self.error_kind,
            "event_id": self.event_id,
            "lemma": self.lemma,
            "module_args": list(self.module_args),
            "structural_error": self.structural_error,
        }


@dataclass(frozen=True)
class TacticAttemptCluster:
    lemma: str
    module_args: tuple[str, ...]
    attempts: tuple[FailedTacticAttempt, ...] = field(default_factory=tuple)
    structural_error: bool = True

    @property
    def count(self) -> int:
        return len(self.attempts)

    @property
    def sample_tactics(self) -> tuple[str, ...]:
        samples: list[str] = []
        seen: set[str] = set()
        for attempt in self.attempts[:3]:
            tactic = attempt.tactic.strip()
            if tactic and tactic not in seen:
                seen.add(tactic)
                samples.append(tactic)
        return tuple(samples)

    @property
    def source_event_ids(self) -> tuple[str, ...]:
        return tuple(a.event_id for a in self.attempts if a.event_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lemma": self.lemma,
            "module_args": list(self.module_args),
            "count": self.count,
            "sample_tactics": list(self.sample_tactics),
            "source_event_ids": list(self.source_event_ids),
            "structural_error": self.structural_error,
            "attempts": [a.to_dict() for a in self.attempts],
        }


@dataclass(frozen=True)
class BranchExperimentCluster:
    """A repeated failed strategy-family experiment.

    This is deliberately tactic-generic: it records that recent speculative
    attempts tried the same proof-structure family and hit the same failure
    shape. Downstream code may use it to avoid spawning another identical
    subtree, but the fact itself does not prescribe a repair.
    """

    experiment_kind: str
    failure_shape: str
    subject: str
    attempts: tuple[FailedTacticAttempt, ...] = field(default_factory=tuple)

    @property
    def count(self) -> int:
        return len(self.attempts)

    @property
    def sample_tactics(self) -> tuple[str, ...]:
        samples: list[str] = []
        seen: set[str] = set()
        for attempt in self.attempts[:3]:
            tactic = attempt.tactic.strip()
            if tactic and tactic not in seen:
                seen.add(tactic)
                samples.append(tactic)
        return tuple(samples)

    @property
    def source_event_ids(self) -> tuple[str, ...]:
        return tuple(a.event_id for a in self.attempts if a.event_id)

    @property
    def module_args(self) -> tuple[str, ...]:
        out: list[str] = []
        seen: set[str] = set()
        for attempt in self.attempts:
            for module in attempt.module_args:
                if module and module not in seen:
                    seen.add(module)
                    out.append(module)
        return tuple(out)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_kind": self.experiment_kind,
            "failure_shape": self.failure_shape,
            "subject": self.subject,
            "count": self.count,
            "sample_tactics": list(self.sample_tactics),
            "module_args": list(self.module_args),
            "source_event_ids": list(self.source_event_ids),
            "attempts": [a.to_dict() for a in self.attempts],
        }


def read_failed_tactic_attempts(session_dir: str | Path) -> list[FailedTacticAttempt]:
    events_path = Path(session_dir) / "events.jsonl"
    if not events_path.exists():
        return []
    attempts: list[FailedTacticAttempt] = []
    try:
        lines = events_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    for line in lines:
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") != "tactic.try_result":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if payload.get("accepted"):
            continue
        attempts.append(failed_tactic_attempt_from_dict({
            "event_id": event.get("event_id") or "",
            "tactic": payload.get("tactic") or "",
            "error_text": payload.get("report") or payload.get("error") or "",
            "error_kind": payload.get("error_kind") or "",
        }))
    return attempts


def failed_tactic_attempt_from_dict(data: dict[str, Any]) -> FailedTacticAttempt:
    tactic = str(data.get("tactic") or "").strip()
    error_text = str(data.get("error_text") or data.get("report") or data.get("error") or "")
    error_kind = str(data.get("error_kind") or "")
    event_id = str(data.get("event_id") or "")
    lemma = ""
    module_args: tuple[str, ...] = ()
    extracted = extract_lemma_and_modules(tactic)
    if extracted is not None:
        lemma, modules = extracted
        module_args = tuple(modules)
    return FailedTacticAttempt(
        tactic=tactic,
        error_text=error_text,
        error_kind=error_kind,
        event_id=event_id,
        lemma=lemma,
        module_args=module_args,
        structural_error=failure_matches_structural(error_text),
    )


def cluster_recent_failed_tactic_attempts(
    failures: list[dict[str, Any]] | list[FailedTacticAttempt],
    *,
    min_consecutive: int = 3,
    lookback: int = 6,
) -> list[TacticAttemptCluster]:
    if not failures:
        return []
    attempts: list[FailedTacticAttempt] = []
    for failure in failures[-lookback:]:
        if isinstance(failure, FailedTacticAttempt):
            attempt = failure
        else:
            attempt = failed_tactic_attempt_from_dict(failure)
        if not attempt.tactic or not attempt.lemma or not attempt.structural_error:
            continue
        attempts.append(attempt)

    grouped: dict[str, list[FailedTacticAttempt]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt.lemma, []).append(attempt)

    clusters: list[TacticAttemptCluster] = []
    for lemma, group in grouped.items():
        if len(group) < min_consecutive:
            continue
        module_args: list[str] = []
        seen: set[str] = set()
        for attempt in group:
            for module in attempt.module_args:
                if module and module not in seen:
                    seen.add(module)
                    module_args.append(module)
        clusters.append(TacticAttemptCluster(
            lemma=lemma,
            module_args=tuple(module_args),
            attempts=tuple(group),
            structural_error=True,
        ))
    return clusters


def cluster_failed_branch_experiments(
    failures: list[dict[str, Any]] | list[FailedTacticAttempt],
    *,
    min_consecutive: int = 2,
    lookback: int = 8,
) -> list[BranchExperimentCluster]:
    """Cluster repeated failed proof-branch experiments by shape.

    Unlike ``cluster_recent_failed_tactic_attempts``, this does not require a
    named lemma. It catches generic proof-shape failures such as repeated
    ``byequiv`` probes, bridge rewrites with proof-term mismatches, or call
    lowering attempts that all fail for the same reason.
    """
    if not failures:
        return []

    attempts: list[FailedTacticAttempt] = []
    for failure in failures[-lookback:]:
        attempt = (
            failure
            if isinstance(failure, FailedTacticAttempt)
            else failed_tactic_attempt_from_dict(failure)
        )
        if attempt.tactic:
            attempts.append(attempt)

    grouped: dict[tuple[str, str, str], list[FailedTacticAttempt]] = {}
    for attempt in attempts:
        experiment_kind = classify_branch_experiment_kind(attempt.tactic)
        failure_shape = classify_failure_shape(attempt.error_text)
        subject = branch_experiment_subject(attempt)
        if not experiment_kind or not failure_shape or not subject:
            continue
        grouped.setdefault(
            (experiment_kind, failure_shape, subject),
            [],
        ).append(attempt)

    clusters: list[BranchExperimentCluster] = []
    for (experiment_kind, failure_shape, subject), group in grouped.items():
        if len(group) < min_consecutive:
            continue
        clusters.append(BranchExperimentCluster(
            experiment_kind=experiment_kind,
            failure_shape=failure_shape,
            subject=subject,
            attempts=tuple(group),
        ))
    clusters.sort(key=lambda c: (c.count, c.experiment_kind, c.subject), reverse=True)
    return clusters


def extract_lemma_and_modules(tactic_text: str) -> Optional[tuple[str, list[str]]]:
    """Extract a tactic's apparent lemma/surrogate and module arguments."""
    text = tactic_text.strip().rstrip(".").rstrip(";")
    if not text:
        return None

    m = re.search(r"Pr\[\s*([A-Z][A-Za-z0-9_]*)\s*\(([^)]+)\)", text)
    if m:
        lemma = m.group(1)
        args = split_module_args(m.group(2))
        return (lemma, args)

    m = re.search(r"\b([A-Z][A-Za-z0-9_']*)\s*\(([^)]*)\)\s*\.", text)
    if m:
        subject = m.group(1)
        args = split_module_args(m.group(2))
        return (subject, args)

    body = text
    body = re.sub(r"^\s*have\s+(?:[A-Za-z_][A-Za-z0-9_']*)\s*:\s*[^.]*?by\s+", "", body)
    body = re.sub(r"^\s*(apply|rewrite|have|conseq|byequiv|elim)\s+", "", body)
    body = body.strip().lstrip("-").lstrip("(").rstrip(")")

    tokens = body.split(None, 1)
    if not tokens:
        return None
    lemma = tokens[0].rstrip(".").rstrip(",").strip()
    arg_str = tokens[1] if len(tokens) > 1 else ""
    if not lemma:
        return None
    return (lemma, split_module_args(arg_str))


def split_module_args(arg_str: str) -> list[str]:
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in arg_str:
        if ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == " " and depth == 0:
            tok = "".join(buf).strip()
            if tok:
                out.append(tok)
            buf = []
        elif ch == "," and depth == 0:
            tok = "".join(buf).strip()
            if tok:
                out.append(tok)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)

    cleaned: list[str] = []
    for tok in out:
        t = tok.strip().strip(",").strip(".").strip(";")
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1].strip()
        if not t:
            continue
        if t.startswith("&"):
            continue
        if t.startswith("fun ") or t.startswith("(fun "):
            continue
        if re.match(r"^[0-9]", t):
            continue
        if t in {"//", "tt", "_", "*"}:
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_'.]*$", t):
            cleaned.append(t)
    return cleaned


def failure_matches_structural(error_text: str) -> bool:
    if not error_text:
        return False
    return any(pattern.search(error_text) for pattern in _STRUCTURAL_ERROR_PATTERNS)


def classify_failure_shape(error_text: str) -> str:
    """Return a stable, low-cardinality failure-shape label."""
    text = error_text or ""
    if re.search(r"wrong number of arguments|argument count mismatch", text, re.I):
        return "wrong_number_of_arguments"
    if re.search(r"proof-?term|not a formula|not a proof", text, re.I):
        return "proof_term_mismatch"
    if re.search(
        r"not accessible by name|unknown variable|unknown constant|unbound",
        text,
        re.I,
    ):
        return "name_scope_error"
    if re.search(r"cannot unify|unification|does not match|type mismatch", text, re.I):
        return "unification_mismatch"
    if re.search(
        r"invalid goal|goal shape|not.*goal|expecting a goal of the form",
        text,
        re.I,
    ):
        return "goal_shape_mismatch"
    if text.strip():
        return "rejected_tactic"
    return ""


def classify_branch_experiment_kind(tactic_text: str) -> str:
    """Classify the proof-structure family a tactic is probing."""
    text = tactic_text.strip()
    if not text:
        return ""
    first = _first_word(text)
    if first in {"byequiv", "bypr", "byphoare", "conseq"}:
        return "proof_mode_lowering"
    if first in {"call", "ecall"} or re.search(r"\bcall\s*\(", text):
        return "call_lowering"
    if first in {"proc", "inline", "wp", "sp", "rnd", "seq", "while", "swap"}:
        return "procedure_lowering"
    if "Pr[" in text or first in {"have", "rewrite", "apply"}:
        return "bridge_rewrite"
    return first or "tactic"


def branch_experiment_subject(attempt: FailedTacticAttempt) -> str:
    """Stable subject for grouping semantically similar branch failures."""
    if attempt.lemma:
        return attempt.lemma
    text = attempt.tactic.strip()
    first = _first_word(text)
    m = re.search(
        r"\b(?:call|ecall|inline)(?:\{\d+\})?\s+([A-Za-z_][A-Za-z0-9_'.]*)",
        text,
    )
    if m:
        return f"{first}:{m.group(1)}" if first else m.group(1)
    if first:
        return first
    return normalize_tactic_shape(text)[:60]


def normalize_tactic_shape(tactic_text: str) -> str:
    text = re.sub(r"\s+", " ", tactic_text.strip())
    text = re.sub(r"@[ \t]*&[A-Za-z0-9_']+", "@ &m", text)
    return text[:160]


def _first_word(tactic_text: str) -> str:
    m = re.match(r"\s*([A-Za-z]+)", tactic_text)
    return m.group(1) if m else ""
