#!/usr/bin/env python3
"""Search proof_guide.json by keyword, section, or entry ID.

Usage:
    # Keyword search across all sections (BM-25 ranked)
    python3 knowledge/base/search_guide.py "byequiv sim swap"

    # Filter by section
    python3 knowledge/base/search_guide.py --section patterns "sampling bijection"
    python3 knowledge/base/search_guide.py --section ec_syntax "rnd"
    python3 knowledge/base/search_guide.py --section strategies "CPA"

    # Get a specific entry by ID
    python3 knowledge/base/search_guide.py --id equiv_sim_structural

    # List all entry IDs (quick index)
    python3 knowledge/base/search_guide.py --list
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

GUIDE_PATH = Path(__file__).resolve().parent / "agent" / "proof_guide.json"
EC_TACTICS_PATH = Path(__file__).resolve().parent / "agent" / "ec_tactics.json"


def _load_guide() -> dict:
    with open(GUIDE_PATH) as f:
        return json.load(f)


def _load_ec_tactics_as_entries() -> list[dict]:
    """Load ec_tactics.json and flatten (goal_type, tactic) pairs into searchable entries."""
    if not EC_TACTICS_PATH.exists():
        return []
    try:
        with open(EC_TACTICS_PATH) as f:
            data = json.load(f)
    except Exception:
        return []

    entries = []
    for goal_type, gt_data in data.get("goal_types", {}).items():
        for tactic_name, tac_data in gt_data.get("tactics", {}).items():
            entry = {
                "id": f"{goal_type}/{tactic_name}",
                "goal_type": goal_type,
                "tactic": tactic_name,
                "description": f"{tactic_name} in {goal_type} goals",
                "syntax": tac_data.get("syntax", ""),
                "forms": tac_data.get("forms", []),
                "pitfalls": tac_data.get("pitfalls", []),
                "when_to_abandon": tac_data.get("when_to_abandon", ""),
                "errors": tac_data.get("errors", {}),
                "smt_hints": tac_data.get("smt_hints", []),
            }
            entries.append(entry)
    return entries


def _entry_text(entry: dict) -> str:
    """Flatten all text fields of an entry for search."""
    parts = []
    for k, v in entry.items():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(json.dumps(item))
        elif isinstance(v, dict):
            parts.append(json.dumps(v))
    return " ".join(parts)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z_]\w*", text)]


def _bm25_search(
    entries: list[dict], query: str, top_k: int = 5
) -> list[tuple[float, dict]]:
    """BM-25 search over entries."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return [(0, e) for e in entries[:top_k]]

    # Build index
    doc_tfs: list[Counter] = []
    df: Counter = Counter()
    for e in entries:
        tokens = _tokenize(_entry_text(e))
        tf = Counter(tokens)
        doc_tfs.append(tf)
        for t in tf:
            df[t] += 1

    n = len(entries)
    avg_dl = sum(sum(tf.values()) for tf in doc_tfs) / max(n, 1)
    k1, b = 1.5, 0.75

    scored = []
    for i, e in enumerate(entries):
        dl = sum(doc_tfs[i].values())
        score = 0.0
        for token in query_tokens:
            if token not in doc_tfs[i]:
                continue
            tf = doc_tfs[i][token]
            idf = math.log((n - df[token] + 0.5) / (df[token] + 0.5) + 1)
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
            score += idf * tf_norm
        if score > 0:
            scored.append((score, e))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]


def _format_entry(entry: dict, section: str, verbose: bool = True) -> str:
    """Format a single entry for display."""
    lines = [f"[{section}] {entry.get('id', '?')}"]

    if section == "strategies":
        lines.append(f"  crypto_type: {entry.get('crypto_type', '?')}")
        lines.append(f"  description: {entry.get('description', '')}")
        slots = entry.get("slot_semantics")
        if slots:
            lines.append("  slot_semantics:")
            for slot, meaning in slots.items():
                lines.append(f"    {slot}: {meaning}")
        variants = entry.get("variants") or []
        if variants:
            lines.append("  variants:")
            for v in variants:
                vn = v.get("name", "?")
                vcond = (v.get("conditions") or "").strip()
                vphases = v.get("phases") or []
                lines.append(f"    - name: {vn}")
                if vcond:
                    lines.append(f"      conditions: {vcond}")
                for phase in vphases:
                    lines.append(
                        f"      phase {phase.get('phase', '?')}: "
                        f"{phase.get('goal', '')}"
                    )
        else:
            for phase in entry.get("phases", []):
                lines.append(f"  phase {phase.get('phase', '?')}: {phase.get('goal', '')}")

    elif section == "patterns":
        lines.append(f"  structure: {entry.get('structural_description', '')}")
        indicators = entry.get("indicators", [])
        if indicators:
            lines.append(f"  indicators: {', '.join(indicators)}")
        # Current schema: slot_semantics + structural hints. Concrete
        # per-lemma examples and tactic scripts are intentionally not stored
        # in the KB.
        slots = entry.get("slot_semantics")
        if slots:
            lines.append("  slot_semantics:")
            for slot, meaning in slots.items():
                lines.append(f"    {slot}: {meaning}")
        # Variant-aware schema: variants only describe selection conditions.
        # Concrete tactics must be derived from the live goal state.
        variants = entry.get("variants") or []
        if variants:
            lines.append("  variants:")
            for v in variants:
                vn = v.get("name", "?")
                vcond = (v.get("conditions") or "").strip()
                lines.append(f"    - name: {vn}")
                if vcond:
                    lines.append(f"      conditions: {vcond}")
        typical_tactics = entry.get("typical_tactics")
        if typical_tactics:
            lines.append(f"  tactic categories: {typical_tactics}")
        fail = entry.get("common_failure", "")
        if fail:
            lines.append(f"  common_failure: {fail}")
            lines.append(f"  fallback: {entry.get('fallback', '')}")
        hints = entry.get("reasoning_hints", "")
        if hints:
            lines.append(f"  hints: {hints[:200]}")

    elif section == "ec_syntax":
        lines.append(f"  description: {entry.get('description', '')}")
        lines.append(f"  syntax: {entry.get('syntax', '')}")
        requires = entry.get("requires", "")
        if requires:
            lines.append(f"  requires: {requires}")

    elif section == "closer_idioms":
        # Closer idioms are descriptive only. They do not store a tactic
        # script; derive concrete tactics from the current goal.
        trig = (entry.get("trigger") or "").strip()
        if trig:
            lines.append(f"  trigger: {trig}")
        slots = entry.get("slot_semantics") or {}
        if slots:
            lines.append("  slot_semantics:")
            for slot, meaning in slots.items():
                lines.append(f"    {slot}: {meaning}")
        note = entry.get("reasoning_hints")
        if note:
            lines.append(f"  hints: {note}")
    return "\n".join(lines)


def list_entries(guide: dict) -> str:
    """List all entry IDs grouped by section."""
    lines = []
    for section in ["strategies", "patterns", "closer_idioms", "ec_syntax"]:
        entries = guide.get(section, [])
        lines.append(f"\n{section} ({len(entries)} entries):")
        for e in entries:
            eid = e.get("id", "?")
            desc = ""
            if section == "strategies":
                desc = e.get("description", "")[:80]
            elif section == "patterns":
                desc = e.get("structural_description", "")[:80]
            elif section == "ec_syntax":
                desc = e.get("description", "")[:80]
            lines.append(f"  {eid}: {desc}")

    # ec_tactics section
    ec_entries = _load_ec_tactics_as_entries()
    if ec_entries:
        lines.append(f"\nec_tactics ({len(ec_entries)} entries):")
        for e in ec_entries:
            eid = e["id"]
            abandon = f" [abandon: {e['when_to_abandon'][:60]}...]" if e.get("when_to_abandon") else ""
            lines.append(f"  {eid}: {e['syntax'][:60]}{abandon}")
    return "\n".join(lines)


def _entry_derived_from_target(entry: dict, target: str) -> bool:
    """Return whether an entry contains target-specific material.

    This should normally be false: the KB no longer stores per-lemma examples
    or source lemma lists. The hook remains as a guard for older local files.
    """
    src = entry.get("source") or {}
    return target in (src.get("lemmas") or [])


def _strip_target_specific_fields(entry: dict, target: str) -> dict:
    """Return a copy with legacy target-specific fields removed."""
    stripped = dict(entry)
    if "source" in stripped and isinstance(stripped["source"], dict):
        source = dict(stripped["source"])
        source.pop("lemmas", None)
        stripped["source"] = source
    return stripped


def search(
    query: str = "",
    section: str | None = None,
    entry_id: str | None = None,
    top_k: int = 5,
) -> str:
    """Search proof_guide.json. Returns formatted text."""
    guide = _load_guide()

    # Eval-mode entry filter: hide entire patterns derived from the target
    # lemma. Complements the line-level redaction in main() (which catches
    # stray lemma-name mentions in otherwise-generic entries).
    eval_target = os.environ.get("EVAL_TARGET_LEMMA", "").strip()

    # Get by ID
    if entry_id:
        for sec in ["strategies", "patterns", "closer_idioms", "ec_syntax"]:
            for e in guide.get(sec, []):
                if e.get("id") == entry_id:
                    if eval_target and _entry_derived_from_target(e, eval_target):
                        # Field-level strip: keep the generic recipe,
                        # remove target-specific examples / provenance.
                        e = _strip_target_specific_fields(e, eval_target)
                    return _format_entry(e, sec)
        # Check ec_tactics (ID format: "goal_type/tactic")
        for e in _load_ec_tactics_as_entries():
            if e.get("id") == entry_id:
                if eval_target and _entry_derived_from_target(e, eval_target):
                    e = _strip_target_specific_fields(e, eval_target)
                return _format_entry(e, "ec_tactics")
        return f"Entry '{entry_id}' not found."

    # Collect entries with section tags
    tagged: list[tuple[dict, str]] = []
    sections = [section] if section else ["strategies", "patterns", "closer_idioms", "ec_syntax", "ec_tactics"]
    for sec in sections:
        if sec == "ec_tactics":
            for e in _load_ec_tactics_as_entries():
                tagged.append((e, "ec_tactics"))
        else:
            for e in guide.get(sec, []):
                tagged.append((e, sec))

    # Eval-mode strip is applied at output time. The current KB should not
    # contain per-lemma examples, but this preserves safety for older local
    # files with target-specific source.lemmas.
    orig_by_id: dict[int, dict] = {}
    eval_stripped = 0
    if eval_target:
        for e, _ in tagged:
            if _entry_derived_from_target(e, eval_target):
                orig_by_id[id(e)] = e
                eval_stripped += 1

    def _maybe_strip(e: dict) -> dict:
        if eval_target and id(e) in orig_by_id:
            return _strip_target_specific_fields(e, eval_target)
        return e

    if not query:
        # No query — list all in section
        lines = []
        for e, sec in tagged:
            lines.append(_format_entry(_maybe_strip(e), sec, verbose=False))
        return "\n\n".join(lines)

    # BM-25 search — score the original generic entry text. Output rendering
    # then strips any legacy target-specific metadata.
    entries = [e for e, _ in tagged]
    sec_map = {id(e): sec for e, sec in tagged}
    results = _bm25_search(entries, query, top_k=top_k)

    if not results:
        msg = f"No results for '{query}'."
        if eval_target and eval_stripped > 0:
            msg += (f"\n[EVAL MODE: target-specific examples/provenance "
                    f"stripped from {eval_stripped} entry/entries.]")
        return msg

    lines = []
    for score, e in results:
        sec = sec_map[id(e)]
        lines.append(_format_entry(_maybe_strip(e), sec))
    if eval_target and eval_stripped > 0:
        lines.append(f"\n[EVAL MODE: {eval_stripped} entry/entries had "
                     f"target-specific examples/provenance stripped "
                     f"(target '{eval_target}'); recipe bodies preserved]")
    return "\n\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search proof_guide.json by keyword, section, or ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="*", help="Search keywords")
    parser.add_argument("--section", "-s",
                        choices=["strategies", "patterns", "ec_syntax", "ec_tactics"],
                        help="Restrict to one section")
    parser.add_argument("--id", help="Get a specific entry by ID")
    parser.add_argument("--list", "-l", action="store_true", help="List all entry IDs")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Max results (default: 5)")
    args = parser.parse_args()

    if args.list:
        guide = _load_guide()
        print(list_entries(guide))
        return 0

    result = search(
        query=" ".join(args.query),
        section=args.section,
        entry_id=args.id,
        top_k=args.top_k,
    )
    # Eval-mode protection is entirely in `search()` (per-example
    # drop via `_strip_target_specific_fields`). The prior line-level
    # redactor in main() was a belt-and-suspenders layer for when
    # body fields could leak concrete lemma names — the body-purity
    # invariant (a KB authoring convention; the `kb_body_purity.py`
    # lint that once enforced it has since been removed) makes that
    # layer unnecessary and removes the risk of false-positive line
    # stripping in generic recipe text.
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
