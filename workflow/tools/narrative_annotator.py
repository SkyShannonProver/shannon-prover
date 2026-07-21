#!/usr/bin/env python3
"""Legacy generator for structured proof narratives.

This tool is not wired into the managed prover prompt path.
Historical artifacts may still contain ``<file>.narrative.json`` files, but
new L4 runs should rely on source context, structural diffs, workspace views,
and runtime context topics instead of injecting a file-level proof story.

Motivation
----------

A human cryptographer reading an EasyCrypt development does not start from
tactics. They read the file and reconstruct a *story*: which games appear,
which declarations mark semantic bridge checkpoints, and which top-level
lemmas move the argument from one security claim to the next. Once that story
is in their head, tactic choices become mechanical translations of the story.

Our prover is trained bottom-up (pick a tactic, see the goal, pick
another tactic). It never gets the top-down story. This tool fills
that gap: it reads a ``.ec`` file, asks Claude to narrate the proof
arc structurally, and writes the narrative as a sibling
``<file>.narrative.json``. A retired workflow planner used to inject this into
the prover prompt as "project semantics"; that injection path has been removed
because it was large, strategy-shaping, and not competitive with the L1
baseline in recent ChaChaPoly comparisons.

Strict eval safety starts here: the default input mode strips every proof
body to ``admit.`` before sending content to the annotator. Raw-source
annotation is still available for research/debugging, but the output is
marked as tainted and eval loaders must reject it.

Usage
-----

    python3 -m workflow.tools.narrative_annotator \\
        --file path/to/project.ec \\
        [--out path/to/project.narrative.json] \\
        [--model claude-opus-4-8] \\
        [--input-mode proof-stripped|raw-source]

One-time cost per file (~2-5 min, one Claude Opus call).
Re-run when the file changes; output carries provenance hashes so consumers
and runtime hooks can detect staleness and proof-body contamination.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from core.easycrypt.narrative_safety import (
    CLEAN_INPUT_MODE,
    RAW_INPUT_MODE,
    build_provenance,
    normalize_input_mode,
    proof_stripped_text,
)


_CLAUDE_BIN = shutil.which("claude") or "claude"
_DEFAULT_MODEL = "claude-opus-4-8"
_ANNOTATOR_VERSION = "v1"


_PROMPT_TEMPLATE = """You are reading an EasyCrypt file that formalizes a cryptographic security proof. Your job is to produce a structured "proof narrative" — the high-level story of what this file is doing — in strict JSON format.

The downstream consumer is an LLM prover that otherwise sees this file as an unstructured lemma dump. Your narrative gives it the top-down semantic layer it is missing: what games appear, what each bridge lemma bridges, what each top-level step is doing in the game-hopping arc.

INPUT FILE: {file_path}
INPUT MODE: {input_mode}
PROOFS REPLACED BEFORE ANNOTATION: {proofs_replaced}
FILE LENGTH: {n_lines} lines
FILE CONTENT:
```easycrypt
{content}
```

Input contract:
- In proof-stripped mode, proof bodies have been replaced with admit blocks.
  Infer the proof story only from declarations, module structure, statements,
  names, imports, and types.
- Do not output proof-body-derived tactics, closing tails, invariant sketches,
  call templates, or "typical proof" scripts. Executable proof moves belong to
  the manager/proof compiler and must be verified separately against a live
  EasyCrypt session.
- Raw-source mode is for research only and is not valid for strict eval.

OUTPUT: a single JSON object with the schema below. Return ONLY the JSON — no preamble, no markdown fences, no commentary after.

SCHEMA:
{{
  "file": "{file_path}",

  "file_purpose": "...",
    // 1-3 sentence plain-English summary of the top-level theorem this
    // file ultimately proves. What cryptographic scheme? What security
    // notion? Under what assumption?

  "main_theorem": {{
    "name": "...",             // the top-level lemma name — usually "conclusion",
                               // "main", or the last lemma in the section
    "informal_statement": "..." // plain English version of what it asserts
  }},

  "proof_strategy_overview": "...",
    // 3-5 sentences describing the high-level proof arc. "The proof
    // decomposes the advantage via a game sequence G0 -> G1 -> ... -> Gn.
    // step1 proves the first reduction [from what to what]. step2
    // handles [which hop] by [which technique]. ..." — do NOT give
    // tactics. Give the SEMANTIC arc.

  "game_chain": [
    {{
      "id": "G0",              // short symbolic identifier
      "role": "...",            // e.g. "real_cca", "ideal_cca",
                               // "prf_real", "prf_random",
                               // "intermediate_abstraction", ...
      "description": "..."      // 1 sentence: what is this game, what
                               // does the adversary see
    }},
    ...
  ],
    // Your best reconstruction of the game-hopping sequence from the
    // file's structure. Infer game identities from module names, lemma
    // statements, imports, clone/module structure, and declarations.
    // 3-6 games is typical. If the file does NOT
    // use game-hopping, return [] for this field and explain in
    // proof_strategy_overview.

  "lemma_catalog": [
    {{
      "name": "...",
      "role": "main_theorem | main_reduction | intermediate_step | bridge_lemma | oracle_equiv | helper | unclear_role",
        // - main_theorem: the top-level claim the file is proving
        // - main_reduction: a "step*" lemma that turns one advantage into another
        // - intermediate_step: a helper `step*` that bounds part of the proof
        // - bridge_lemma: typically `pr_*`, asserts two Pr terms are equal
        //   (usually = game-hop edge between two games)
        // - oracle_equiv: typically `equiv_*` or a small named pRHL
        //   equivalence between oracle pairs, used under `call`
        // - helper: anything else (algebraic helpers, lossless lemmas, etc.)
        // - unclear_role: you can't tell
      "narrative": "...",
        // 1-2 sentences: in the PROOF ARC, what job does this lemma do?
        // If bridge_lemma, which two games does it bridge and in which
        // direction? If oracle_equiv, which call sites in which main
        // proof use it? If main_reduction, which game-hop deltas does it
        // equate?
      "hop": ["G_i", "G_j"],
        // ONLY if role is "bridge_lemma" — which two game ids from
        // game_chain it bridges. Omit for other roles.
      "semantic_delta": "...",
        // REQUIRED for bridge_lemma and oracle_equiv. A SHORT, PRECISE
        // description of the ONE thing this lemma changes between its
        // LHS and RHS. Keep it atomic — a bridge_lemma SHOULD do
        // exactly one semantic delta (that's why the author wrote it).
        // Good examples:
        //   "replaces a concrete oracle wrapper with an abstract wrapper;
        //    does NOT change game architecture or adversary interface"
        //   "switches from a finite-map oracle implementation to an
        //    operator-based oracle instance; preserves observable oracle
        //    semantics"
        //   "equivalence between two encryption oracle procedures under
        //    matched state; both call the same primitive with the same key"
        // Bad examples (too vague or multi-delta):
        //   "bridges real and RO games" (too vague)
        //   "unifies the two sides via byequiv and call" (describes
        //    HOW it would be used, not WHAT it changes)
        //   "changes wrapper AND key material AND oracle behaviour"
        //    (multi-delta — if the lemma really does this, split it
        //    into sub-deltas in the narrative)
      "statement_cues": [...]
        // OPTIONAL. Non-tactic cues visible in the declaration or module
        // names, such as important wrapper/module names, endpoints, or
        // oracle names. Do NOT include tactics, invariant sketches,
        // proof scripts, smt lemma lists, closing tails, or call templates.
    }},
    ...
  ],
    // EVERY top-level lemma / equiv / hoare declared in the file.
    // Skip nothing, including ones with role "helper" or "unclear_role".
    // If the file has >30 lemmas and most are clearly helpers, you may
    // collapse a group with role="helper" and narrative="algebraic
    // helpers".

  "glossary": {{
    "ModuleOrTypeName": "semantic explanation",
    ...
  }}
    // 5-20 key NAMES used in the file that a newcomer wouldn't immediately
    // understand. Prefer ones that show up in the main theorem or the
    // bridge lemmas. For each, 1 sentence: "CCA_game(A, R)" -> "Standard
    // IND-CCA2 game with adversary A and oracle stack R (enc/dec
    // provided by R)". Skip trivial stdlib names (Int, Real, ...).
}}

Accuracy > coverage. If you are unsure about a game-hop edge or a
lemma's role, use "unclear_role" or omit the hop field. Do NOT invent
cryptographic facts not supported by the file content.

Forbidden output fields in proof-stripped/eval-clean narratives:
closer_hints, typical_tail, closing_tail, call_template, invariant_sketch,
proof_script, proof_sketch, tactic, tactics, script.

Return ONLY the JSON object. No preamble. No markdown fences."""


def _build_prompt(
    file_path: Path,
    content: str,
    input_mode: str,
    proofs_replaced: int,
) -> str:
    n_lines = len(content.splitlines())
    return _PROMPT_TEMPLATE.format(
        file_path=str(file_path),
        input_mode=normalize_input_mode(input_mode),
        proofs_replaced=proofs_replaced,
        n_lines=n_lines,
        content=content,
    )


def _extract_json_payload(raw: str) -> dict:
    """Claude sometimes wraps JSON in markdown fences or adds trailing
    text despite the "return only JSON" instruction. Strip fences, then
    parse the largest valid JSON object we can find."""
    raw = raw.strip()
    # Strip markdown fence prefix
    if raw.startswith("```"):
        first_nl = raw.find("\n")
        if first_nl > 0:
            raw = raw[first_nl + 1:]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    raw = raw.strip()
    # If there's leading 'json\n' from fence
    if raw.lower().startswith("json\n"):
        raw = raw[5:]
    raw = raw.strip()
    # Locate the outermost JSON object by brace matching
    start = raw.find("{")
    if start < 0:
        raise ValueError(f"no JSON object found in Claude output; got: {raw[:200]}")
    depth = 0
    end = -1
    in_str = False
    prev = ""
    for i, ch in enumerate(raw[start:], start=start):
        if ch == '"' and prev != "\\":
            in_str = not in_str
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        prev = ch
    if end < 0:
        raise ValueError(
            f"unterminated JSON object; got: {raw[:200]}..."
        )
    payload = raw[start: end + 1]
    return json.loads(payload)


def _prepare_annotator_input(
    raw_content: str,
    input_mode: str,
) -> tuple[str, int, str]:
    mode = normalize_input_mode(input_mode)
    if mode == CLEAN_INPUT_MODE:
        stripped, n_replaced = proof_stripped_text(raw_content)
        return stripped, n_replaced, mode
    if mode == RAW_INPUT_MODE:
        return raw_content, 0, mode
    raise ValueError(
        "input_mode must be proof-stripped/proof_stripped or raw-source/raw_source"
    )


def annotate(
    file_path: Path,
    model: str = _DEFAULT_MODEL,
    timeout: float = 600.0,
    input_mode: str = CLEAN_INPUT_MODE,
) -> dict:
    """Read the file, call Claude, return the parsed narrative dict."""
    raw_content = file_path.read_text(encoding="utf-8")
    annotator_input, proofs_replaced, mode = _prepare_annotator_input(
        raw_content,
        input_mode,
    )
    prompt = _build_prompt(file_path, annotator_input, mode, proofs_replaced)
    cmd = [
        _CLAUDE_BIN, "-p", prompt,
        "--model", model,
        "--dangerously-skip-permissions",
        "--output-format", "text",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p returned {result.returncode}\n"
            f"stderr: {result.stderr[:500]}"
        )
    narrative = _extract_json_payload(result.stdout)

    provenance = build_provenance(
        raw_text=raw_content,
        annotator_input_text=annotator_input,
        input_mode=mode,
        proofs_replaced=proofs_replaced,
        model=model,
        annotator_version=_ANNOTATOR_VERSION,
    )
    narrative["provenance"] = provenance
    # Backward-compatible top-level fields for older readers.
    narrative["_source_sha256"] = provenance["annotator_input_sha256"]
    narrative["_raw_source_sha256"] = provenance["raw_source_sha256"]
    narrative["_proof_stripped_input_sha256"] = (
        provenance["proof_stripped_input_sha256"]
    )
    narrative["_narrative_input_mode"] = provenance["input_mode"]
    narrative["_annotator_version"] = _ANNOTATOR_VERSION
    narrative["_model"] = model
    return narrative


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, type=Path,
                    help="Path to the .ec file to annotate")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output path (default: <file>.narrative.json)")
    ap.add_argument("--model", default=_DEFAULT_MODEL,
                    help=f"Claude model (default: {_DEFAULT_MODEL})")
    ap.add_argument("--timeout", type=float, default=600.0,
                    help="Timeout for the Claude call (default: 600s)")
    ap.add_argument("--input-mode", default="proof-stripped",
                    choices=["proof-stripped", "proof_stripped",
                             "raw-source", "raw_source"],
                    help=("Input sent to annotator. Default proof-stripped "
                          "is the only strict-eval-clean mode."))
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the prompt and exit without calling Claude")
    args = ap.parse_args(argv)

    if not args.file.exists():
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2

    if args.dry_run:
        raw_content = args.file.read_text(encoding="utf-8")
        annotator_input, proofs_replaced, mode = _prepare_annotator_input(
            raw_content,
            args.input_mode,
        )
        prompt = _build_prompt(args.file, annotator_input, mode, proofs_replaced)
        print(prompt)
        return 0

    out_path = args.out or args.file.with_suffix(
        args.file.suffix + ".narrative.json"
    )
    mode = normalize_input_mode(args.input_mode)
    print(
        f"annotating {args.file} with {args.model} "
        f"(input_mode={mode})...",
        file=sys.stderr,
    )
    narrative = annotate(
        args.file,
        model=args.model,
        timeout=args.timeout,
        input_mode=mode,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(narrative, indent=2), encoding="utf-8")

    print(f"wrote {out_path}", file=sys.stderr)
    # Quick summary for the user
    print(f"  file_purpose: {narrative.get('file_purpose', '?')[:120]}")
    mt = narrative.get("main_theorem", {})
    print(f"  main_theorem: {mt.get('name', '?')}"
          f" — {mt.get('informal_statement', '?')[:100]}")
    gc = narrative.get("game_chain", [])
    print(f"  game_chain: {len(gc)} games")
    for g in gc[:6]:
        print(f"    {g.get('id', '?')}: {g.get('role', '?')} — "
              f"{g.get('description', '?')[:70]}")
    lc = narrative.get("lemma_catalog", [])
    by_role: dict[str, int] = {}
    for lem in lc:
        r = lem.get("role", "?")
        by_role[r] = by_role.get(r, 0) + 1
    print(f"  lemmas: {len(lc)} total; by role: {by_role}")
    print(f"  glossary: {len(narrative.get('glossary', {}))} terms")
    prov = narrative.get("provenance") or {}
    print(
        "  provenance: "
        f"input_mode={prov.get('input_mode', '?')}, "
        f"proofs_replaced={prov.get('proofs_replaced', '?')}, "
        f"proof_stripped_hash={str(prov.get('proof_stripped_input_sha256', '?'))[:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
