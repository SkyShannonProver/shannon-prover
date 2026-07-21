"""Static EasyCrypt declaration inventory for project-level batch runs.

This module reads source text only.  It does not plan proofs, classify proof
difficulty, build agent prompts, or participate in the managed prover runtime.
The project driver uses the inventory to order admitted declarations before
launching independent prover runs.
"""

from __future__ import annotations

import re


def _mask_comments(content: str) -> str:
    """Replace nested EasyCrypt comments with spaces while preserving offsets."""
    masked = list(content)
    depth = 0
    i = 0
    while i < len(content):
        pair = content[i:i + 2]
        if pair == "(*":
            depth += 1
            masked[i:i + 2] = "  "
            i += 2
            continue
        if pair == "*)" and depth:
            depth -= 1
            masked[i:i + 2] = "  "
            i += 2
            continue
        if depth and content[i] != "\n":
            masked[i] = " "
        i += 1
    return "".join(masked)


def _statement_end_dot(content: str, start: int) -> int:
    """Find a declaration's terminating top-level dot."""
    paren = 0
    bracket = 0
    brace = 0
    i = start
    while i < len(content):
        char = content[i]
        if char == "(":
            paren += 1
        elif char == ")" and paren > 0:
            paren -= 1
        elif char == "[":
            bracket += 1
        elif char == "]" and bracket > 0:
            bracket -= 1
        elif char == "{":
            brace += 1
        elif char == "}" and brace > 0:
            brace -= 1
        elif char == "." and paren == bracket == brace == 0:
            following = content[i + 1:i + 2]
            if not following or following.isspace():
                return i + 1
        i += 1
    return len(content)


def extract_declarations(content: str) -> list[dict]:
    """Extract lemma-like declarations and their source status.

    The inventory includes lemmas, theorems, axioms, and named top-level
    equivalences.  It is deliberately a source inventory rather than an
    agent-facing lemma index.
    """
    declarations: list[dict] = []
    searchable = _mask_comments(content)
    declaration_re = re.compile(
        r"(?:local\s+)?(lemma|theorem|axiom|equiv)\s+(\w+)\b",
    )
    matches = list(declaration_re.finditer(searchable))
    for index, match in enumerate(matches):
        kind = match.group(1)
        name = match.group(2)
        statement_end = _statement_end_dot(searchable, match.start())
        statement = content[match.start():statement_end].strip()
        if len(statement) > 400:
            statement = statement[:400] + "..."

        if kind == "axiom":
            status = "axiom"
        else:
            declaration_end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(searchable)
            )
            following = searchable[statement_end:declaration_end]
            has_admit = bool(re.search(r"\badmit\s*\.", following))
            has_qed = bool(re.search(r"\bqed\s*\.", following))
            if has_qed and not has_admit:
                status = "proved"
            elif has_admit:
                status = "admit"
            else:
                status = "unknown"

        declarations.append(
            {
                "name": name,
                "statement": statement,
                "status": status,
                "kind": kind,
            }
        )
    return declarations


def _proof_body(content: str, declaration_name: str) -> str:
    """Return the proof body of a lemma or theorem when one is present."""
    searchable = _mask_comments(content)
    declaration_re = re.compile(
        rf"(?:local\s+)?(?:lemma|theorem)\s+{re.escape(declaration_name)}\b",
    )
    declaration = declaration_re.search(searchable)
    if not declaration:
        return ""

    following = searchable[declaration.end():]
    proof = re.search(r"\bproof\b", following[:500])
    if not proof:
        return ""
    body_start = declaration.end() + proof.end()
    remainder = searchable[body_start:]
    end = re.search(r"\b(?:qed|admit)\s*\.", remainder)
    if not end:
        return content[body_start:body_start + 2000]
    return content[body_start:body_start + end.start()]


def detect_admit_dependencies(
    content: str,
    declarations: list[dict],
) -> dict[str, dict]:
    """Build the project driver's heuristic dependency inventory.

    This is scheduling metadata only.  It is not shown to the prover and is
    never used to select tactics or to gate a managed proof session.
    """
    admitted = [item["name"] for item in declarations if item["status"] == "admit"]
    all_names = {item["name"] for item in declarations}
    source_order = {item["name"]: index for index, item in enumerate(declarations)}

    result: dict[str, dict] = {}
    for name in admitted:
        body = _mask_comments(_proof_body(content, name))
        dependencies = [
            other
            for other in all_names
            if other != name and re.search(rf"\b{re.escape(other)}\b", body)
        ]

        body_without_comments = re.sub(r"\(\*.*?\*\)", "", body)
        if not dependencies and len(body_without_comments.strip()) < 20:
            dependencies = [
                other
                for other in admitted
                if other != name and source_order[other] < source_order[name]
            ]

        unproved = [dependency for dependency in dependencies if dependency in admitted]
        result[name] = {
            "deps": dependencies,
            "unproved_deps": unproved,
            "can_prove": not unproved,
        }
    return result
