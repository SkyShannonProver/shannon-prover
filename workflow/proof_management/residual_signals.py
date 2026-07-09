"""Residual-goal signal helpers used by manager-side diagnostics."""
from __future__ import annotations

import re


_SIDE_TOKEN = re.compile(r"([A-Za-z_][\w'.]*)\s*\{\s*([12])\s*\}")
_FRAME_EQ = re.compile(r"=\s*\{([^}]*)\}")
_EXPANDED_FRAME_EQ = re.compile(
    r"([A-Za-z_][\w'.]*)\s*\{\s*1\s*\}\s*=\s*\1\s*\{\s*2\s*\}")
_EXPANDED_FRAME_TUPLE = re.compile(
    r"\(([^()]*\{\s*1\s*\}[^()]*)\)\s*=\s*\(([^()]*\{\s*2\s*\}[^()]*)\)")
_STRIP_SIDE = re.compile(r"\s*\{\s*[12]\s*\}\s*$")
_QUAL_NAME = re.compile(r"\b([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\b")
_SMT_ARGS = re.compile(r"smt\s*\(([^)]*)\)", re.IGNORECASE)
_APPLY_LIKE = re.compile(
    r"\b(?:apply|rewrite|exact|elim|case|have|conseq)\b[^.;]*?"
    r"\b([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
)
_STOP = {
    "Pr", "Top", "let", "in", "forall", "exists", "fun", "if", "then", "else",
    "true", "false", "glob", "res", "pre", "post", "Current", "goal", "Type",
}


def classify_call_subgoal(goal_type: str) -> str:
    """Classify a subgoal spawned by ``call(I)`` for admit-skeleton checks."""
    return "oracle" if str(goal_type or "").strip().lower() == "equiv" else "continuation"


def extract_residual_signals(residual: str, tactic: str = "") -> dict:
    """Extract compact, deterministic residual-goal signals.

    The result records raw syntactic signals only: side-tagged relational terms,
    frame equalities, identifiers, and tactic lemma references.
    """
    residual = str(residual or "")
    tactic = str(tactic or "")

    side_tokens_all = {
        f"{m.group(1)}{{{m.group(2)}}}" for m in _SIDE_TOKEN.finditer(residual)
    }
    frame_set = {
        part.strip()
        for m in _FRAME_EQ.finditer(residual)
        for part in m.group(1).split(",")
        if part.strip()
    }
    mpre = re.search(r"\bpre\s*=", residual)
    if mpre:
        start = mpre.end()
        mpost = re.search(r"\bpost\s*=", residual[start:])
        hyp_text = residual[start: start + mpost.start()] if mpost else residual[start:]
    else:
        hyp_text = ""
    expanded_frame = {m.group(1) for m in _EXPANDED_FRAME_EQ.finditer(hyp_text)}
    for m in _EXPANDED_FRAME_TUPLE.finditer(hyp_text):
        for part in m.group(1).split(","):
            base = _STRIP_SIDE.sub("", part.strip())
            if base:
                expanded_frame.add(base)
    frame_eqs = sorted(frame_set | expanded_frame)
    side_tokens = sorted(
        t for t in side_tokens_all if _STRIP_SIDE.sub("", t) not in expanded_frame
    )
    identifiers = sorted({
        m.group(1) for m in _QUAL_NAME.finditer(residual)
        if m.group(1) not in _STOP and not m.group(1).isdigit()
    })

    tac_lemmas: list[str] = []
    for m in _SMT_ARGS.finditer(tactic):
        tac_lemmas += [a for a in re.split(r"[,\s]+", m.group(1)) if a]
    tac_lemmas += [m.group(1) for m in _APPLY_LIKE.finditer(tactic)]
    tactic_lemmas = sorted({t for t in tac_lemmas if t and t not in _STOP})

    return {
        "side_tokens": side_tokens[:40],
        "frame_eqs": frame_eqs[:20],
        "identifiers": identifiers[:40],
        "tactic_lemmas": tactic_lemmas[:20],
    }
