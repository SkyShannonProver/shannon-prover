"""Safety helpers for proof narratives.

Strict eval narratives must be generated from proof-stripped EasyCrypt
sources.  This module is shared by the offline annotator, the planner, and
the runtime loader so they enforce the same provenance contract.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any


CLEAN_INPUT_MODE = "proof_stripped"
RAW_INPUT_MODE = "raw_source"
PROVENANCE_VERSION = 1


TACTIC_LIKE_FIELDS = frozenset({
    "closer_hints",
    "closing_tail",
    "typical_tail",
    "call_template",
    "invariant_sketch",
    "proof_script",
    "proof_sketch",
    "proof",
    "tactic",
    "tactics",
    "script",
    "rewrite_form",
    "arg_types",
})

TARGET_STRUCTURAL_FIELDS = frozenset({
    "name",
    "role",
    "hop",
    "kind",
})


def normalize_input_mode(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in {"proof_stripped", "stripped", "clean", "eval_clean"}:
        return CLEAN_INPUT_MODE
    if text in {"raw_source", "raw", "source"}:
        return RAW_INPUT_MODE
    return text


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proof_stripped_text(raw_text: str) -> tuple[str, int]:
    # core stays self-contained — the transform lives in core/easycrypt now
    # (no core -> workflow import; restores the layering invariant).
    try:
        from .proof_strip import replace_proofs
    except ImportError:  # script-path fallback
        from core.easycrypt.proof_strip import replace_proofs  # type: ignore
    return replace_proofs(raw_text)


def build_provenance(
    *,
    raw_text: str,
    annotator_input_text: str,
    input_mode: str,
    proofs_replaced: int,
    model: str,
    annotator_version: str,
) -> dict[str, Any]:
    stripped, stripped_count = proof_stripped_text(raw_text)
    mode = normalize_input_mode(input_mode)
    return {
        "version": PROVENANCE_VERSION,
        "input_mode": mode,
        "raw_source_sha256": sha256_text(raw_text),
        "proof_stripped_input_sha256": sha256_text(stripped),
        "annotator_input_sha256": sha256_text(annotator_input_text),
        "proofs_replaced": int(proofs_replaced),
        "proof_stripped_replacement_count": int(stripped_count),
        "annotator_model": model,
        "annotator_version": annotator_version,
        "tainted": mode != CLEAN_INPUT_MODE,
    }


def validate_eval_narrative(
    narrative: dict[str, Any],
    source_path: str | Path,
) -> tuple[bool, str]:
    if not isinstance(narrative, dict) or not narrative:
        return False, "missing_narrative"
    provenance = narrative.get("provenance")
    if not isinstance(provenance, dict):
        return False, "missing_provenance"
    mode = normalize_input_mode(provenance.get("input_mode"))
    if mode != CLEAN_INPUT_MODE:
        return False, f"tainted_input_mode:{mode or 'unknown'}"
    if bool(provenance.get("tainted")):
        return False, "tainted_provenance"
    path = Path(source_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"source_unreadable:{type(exc).__name__}"
    stripped, _ = proof_stripped_text(raw_text)
    current_stripped_hash = sha256_text(stripped)
    expected_stripped = str(provenance.get("proof_stripped_input_sha256") or "")
    expected_input = str(provenance.get("annotator_input_sha256") or "")
    # Raw hash is retained for audit.  Strict eval safety is governed by the
    # proof-stripped source hash, because a narrative generated from a full
    # proof file and one generated from the corresponding admit skeleton expose
    # the same annotator input when proof stripping is correct.
    if expected_stripped != current_stripped_hash:
        return False, "proof_stripped_hash_mismatch"
    if expected_input and expected_input != current_stripped_hash:
        return False, "annotator_input_not_current_proof_stripped_source"
    return True, "ok"


def sanitize_narrative_for_eval(
    narrative: dict[str, Any],
    target_lemma: str,
) -> dict[str, Any]:
    """Return a copy safe to expose in strict eval.

    All tactic-like fields are removed globally.  The target lemma entry is
    reduced further to structural metadata only.
    """
    clean = _strip_tactic_like(copy.deepcopy(narrative))
    clean.pop("proof_strategy_overview", None)
    target = str(target_lemma or "")
    catalog: list[dict[str, Any]] = []
    for item in clean.get("lemma_catalog") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if target and name == target:
            item = {
                key: value
                for key, value in item.items()
                if key in TARGET_STRUCTURAL_FIELDS
            }
            item["eval_note"] = (
                "Target lemma route text is hidden in eval mode; use manager "
                "proof options and live EasyCrypt checks for executable moves."
            )
        catalog.append(item)
    clean["lemma_catalog"] = catalog
    clean["eval_safety"] = {
        "status": "sanitized",
        "target_lemma": target,
        "removed_fields": sorted(TACTIC_LIKE_FIELDS),
    }
    return clean


def _strip_tactic_like(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_tactic_like(subvalue)
            for key, subvalue in value.items()
            if key not in TACTIC_LIKE_FIELDS
        }
    if isinstance(value, list):
        return [_strip_tactic_like(item) for item in value]
    return value
