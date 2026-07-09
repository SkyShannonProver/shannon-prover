"""Comment-aware lemma-declaration lookup, shared across the pipeline.

A lemma name declared more than once in a file makes every name-based
lookup ambiguous: the eval-suite scrub, the prover's proof write-back, and
the post-verify admit check can each resolve to a *different* declaration,
which turns the run structurally unwinnable (observed: `xorK1` declared in
both `theory Byte` and `abstract theory GenBlock` of
ChaChaPoly/chacha_poly.ec, 2026-06-11 — the proof closed in-session, the
write-back filled one declaration, then the admit check matched the other
still-admitted one and reverted a genuinely proved lemma).

Callers that must agree on "where is lemma X declared" should use these
helpers: `eval_suite.run` (single-target scrub guard), the orchestrator
(startup duplicate guard), and `workflow.agents.prover` (declaration
matching for write-back).
"""

from __future__ import annotations

import re


def lemma_decl_re(lemma_name: str) -> re.Pattern[str]:
    """Pattern matching a declaration of ``lemma_name`` (any decl keyword)."""
    return re.compile(
        r"(?:local\s+)?(?:lemma|theorem|equiv|hoare|phoare)\s+"
        + re.escape(lemma_name)
        + r"(?=[\s:(\[]|$)",
    )


def mask_comments(content: str) -> str:
    """Blank out ``(* ... *)`` comment interiors (nesting-aware), preserving
    every offset and newline, so declaration scans cannot match a
    commented-out lemma."""
    out = list(content)
    depth = 0
    i = 0
    n = len(content)
    while i < n:
        pair = content[i:i + 2]
        if pair == "(*":
            depth += 1
            out[i] = out[i + 1] = " "
            i += 2
            continue
        if pair == "*)" and depth:
            depth -= 1
            out[i] = out[i + 1] = " "
            i += 2
            continue
        if depth and content[i] != "\n":
            out[i] = " "
        i += 1
    return "".join(out)


def lemma_decl_matches(content: str, lemma_name: str) -> list[re.Match[str]]:
    """All (uncommented) declaration matches of ``lemma_name``.

    Matching runs over comment-masked text; because masking preserves every
    offset, ``m.start()`` is valid in the original ``content``.
    """
    return list(lemma_decl_re(lemma_name).finditer(mask_comments(content)))


def lemma_decl_lines(content: str, lemma_name: str) -> list[int]:
    """1-based line numbers of every (uncommented) declaration of ``lemma_name``."""
    masked = mask_comments(content)
    return [
        masked.count("\n", 0, m.start()) + 1
        for m in lemma_decl_re(lemma_name).finditer(masked)
    ]
