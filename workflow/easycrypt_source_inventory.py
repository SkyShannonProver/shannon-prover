"""Static EasyCrypt declaration inventory for project-level batch runs.

This module reads source text only.  It does not plan proofs, classify proof
difficulty, build agent prompts, or participate in the managed prover runtime.
The project driver uses the inventory to order admitted declarations before
launching independent prover runs.
"""

from __future__ import annotations

import re
from bisect import bisect_right

from core.easycrypt.lemma_decls import target_declaration
from core.easycrypt.proof_text import sentence_ends, strip_comments


def extract_declarations(content: str) -> list[dict]:
    """Extract lemma-like declarations and their source status.

    The inventory includes lemmas, theorems, axioms, and named top-level
    equivalences.  It is deliberately a source inventory rather than an
    agent-facing lemma index.
    """
    declarations: list[dict] = []
    searchable = strip_comments(content)
    ends = list(sentence_ends(content))
    declaration_re = re.compile(
        r"(?:local\s+)?(lemma|theorem|axiom|equiv)\s+(\w+)\b",
    )
    matches = list(declaration_re.finditer(searchable))
    for index, match in enumerate(matches):
        kind = match.group(1)
        name = match.group(2)
        position = bisect_right(ends, match.start())
        statement_end = ends[position] if position < len(ends) else len(content)
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
    """Return the tactics of the declaration's own proof, after `proof.` and
    before the first `admit.` or `qed.`."""
    declaration = target_declaration(content, declaration_name)
    if declaration is None or declaration.proof is None:
        return ""
    proof = content[declaration.proof.start:declaration.proof.end]
    searchable = strip_comments(proof)
    opener = re.match(r"proof\s*\.", searchable)
    end = re.search(r"\b(?:qed|admit)\s*\.", searchable)
    return proof[opener.end() if opener else 0:end.start() if end else len(proof)]


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
        body = strip_comments(_proof_body(content, name))
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
