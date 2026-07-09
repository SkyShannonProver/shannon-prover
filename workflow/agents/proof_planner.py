"""Proof research module: gather context for provers (pure Python, no LLM).

Replaces the former LLM-based Proof Planner. All research is mechanical:
- Read target file, extract lemmas/helpers/operators
- Classify difficulty from statement pattern

The prover does its own strategic analysis (Mode 1: compose holistically).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from workflow.schemas.config import RunConfig
from workflow.schemas.proof_plan import ContextBrief, PlanPhase, ProofPlan

logger = logging.getLogger("workflow.agents.proof_planner")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_file_content(path: str, max_lines: int = 500) -> str:
    """Read a file relative to project root, truncating if needed.

    Truncation is a LAST RESORT. For project-sized files (>500 lines),
    prefer `_scoped_file_content(path, lemma_name)` which uses
    `lemma_extract` to build a target-scoped standalone file — that
    preserves the surrounding declarations the prover actually needs
    (clones, ops, types, previous proofs) and admits only unrelated
    lemmas, rather than silently dropping the second half of the file.
    """
    full = _PROJECT_ROOT / path
    if not full.exists():
        return f"(file not found: {path})"
    lines = full.read_text(encoding="utf-8").splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} total lines)"
    return "\n".join(lines)


def _scoped_file_content(path: str, lemma_name: str, threshold_lines: int = 500) -> str:
    """Return file content scoped to the target lemma when the file is large.

    For small files (< threshold_lines): return the whole file verbatim.

    For big files (>= threshold_lines): use `lemma_extract.extract_lemma`
    to produce a standalone version that:
      - Keeps all clones, ops, types, axioms (structural context)
      - Keeps proved sibling lemmas' bodies (the prover legitimately uses
        them via `apply`/`have`/`byequiv`)
      - Replaces unrelated admit lemmas with `admit.` (same as the
        original — their bodies are absent, so no loss)
      - Opens the target lemma's proof (suitable for prover context)

    Silent truncation of a 2339-line ChaChaPoly to 500 lines hid the
    target lemma's declaration entirely — scoped extraction fixes that.
    Falls back to the old truncation on any extract error.
    """
    full = _PROJECT_ROOT / path
    if not full.exists():
        return f"(file not found: {path})"
    raw = full.read_text(encoding="utf-8")
    n_lines = raw.count("\n") + 1
    if n_lines < threshold_lines:
        return raw
    # Large file — try lemma_extract
    try:
        from core.easycrypt.lemma_extract import extract_lemma
        return extract_lemma(full, lemma_name, open_proof=True)
    except Exception as e:
        logger.warning(
            "scoped extract failed for %s:%s (%s); falling back to "
            "truncate-first-%d lines", path, lemma_name, e, threshold_lines
        )
        lines = raw.splitlines()
        return "\n".join(lines[:threshold_lines]) + f"\n... (truncated, {n_lines} total lines)"


# ---------------------------------------------------------------------------
# Context brief extraction (Python, no LLM)
# ---------------------------------------------------------------------------


def _statement_end_dot(content: str, start: int) -> int:
    """Find the terminating '.' of an EC declaration starting at ``start``.

    A terminating dot is one at bracket depth 0 (all ``()``, ``[]``, ``{}``
    closed) followed by whitespace or EOF. Module-qualified names like
    ``A.main`` don't qualify — the dot is followed by a letter, not space.
    """
    paren = 0
    bracket = 0
    brace = 0
    n = len(content)
    i = start
    while i < n:
        c = content[i]
        if c == '(':
            paren += 1
        elif c == ')' and paren > 0:
            paren -= 1
        elif c == '[':
            bracket += 1
        elif c == ']' and bracket > 0:
            bracket -= 1
        elif c == '{':
            brace += 1
        elif c == '}' and brace > 0:
            brace -= 1
        elif c == '.' and paren == 0 and bracket == 0 and brace == 0:
            nxt = content[i + 1:i + 2]
            if not nxt or nxt.isspace():
                return i + 1
        i += 1
    return n


def _extract_lemmas_from_ec(content: str) -> list[dict]:
    """Extract declarations from .ec file content.

    Includes ``lemma``, ``theorem``, ``axiom``, and top-level ``equiv``
    declarations. Axioms are "assumed true" — usable identically to
    proved lemmas via ``apply``/``rewrite``. ``equiv`` declarations are
    named relational judgments (``local equiv CCP_OCCP : A.main ~ B.main
    : … ==> …``) that are first-class pivots for ``byequiv``.

    Statement text is extracted up to the terminating ``.`` with bracket
    counting so module paths (``A.main``) don't truncate the statement
    prematurely (the old regex cut at the first dot, losing the body of
    every lemma whose statement mentions a module-qualified name).
    """
    lemmas: list[dict] = []
    decl_re = re.compile(
        r"(?:local\s+)?(lemma|theorem|axiom|equiv)\s+(\w+)\b",
    )
    for m in decl_re.finditer(content):
        kind = m.group(1)
        name = m.group(2)
        stmt_end = _statement_end_dot(content, m.start())
        statement = content[m.start():stmt_end].strip()
        if len(statement) > 400:
            statement = statement[:400] + "..."

        if kind == "axiom":
            status = "axiom"
        else:
            after = content[stmt_end:stmt_end + 500]
            has_admit = bool(re.search(r"\badmit\b", after))
            has_qed = bool(re.search(r"\bqed\b", after))
            if has_qed and not has_admit:
                status = "proved"
            elif has_admit:
                status = "admit"
            else:
                status = "unknown"

        lemmas.append({
            "name": name,
            "statement": statement,
            "status": status,
            "kind": kind,
        })
    return lemmas


def _find_proof_body(content: str, lemma_name: str) -> str:
    """Extract the proof body for a lemma (between proof. and qed./admit.)."""
    # Find the lemma declaration
    pattern = re.compile(
        rf"(?:local\s+)?(?:lemma|theorem)\s+{re.escape(lemma_name)}\b",
    )
    m = pattern.search(content)
    if not m:
        return ""
    # Find proof. after the declaration
    after = content[m.end():]
    proof_match = re.search(r"\bproof\b", after[:500])
    if not proof_match:
        return ""
    proof_start = m.end() + proof_match.end()
    # Find qed. or admit.
    rest = content[proof_start:]
    end_match = re.search(r"\b(?:qed|admit)\s*\.", rest)
    if not end_match:
        return rest[:2000]
    return rest[:end_match.start()]


def _detect_admit_dependencies(content: str, lemmas: list[dict]) -> dict:
    """Detect which admitted lemmas depend on other admitted lemmas.

    Returns a dict: {lemma_name: {"deps": [names], "can_prove": bool}}
    - deps: other lemma names referenced in the proof body (or section)
    - can_prove: True if all dependencies are proved, False if some are admitted

    For admitted lemmas with admit-only proof bodies, we check if other
    admitted lemma names appear in the same section, suggesting they're
    dependencies for the final reduction lemma.
    """
    admitted = [l["name"] for l in lemmas if l["status"] == "admit"]
    proved = {l["name"] for l in lemmas if l["status"] == "proved"}
    all_names = {l["name"] for l in lemmas}

    result = {}
    for name in admitted:
        # Get the proof body (may be just "admit." for unproved lemmas)
        body = _find_proof_body(content, name)

        # Find references to other lemmas in the body
        # For an "admit." body, also scan the broader section context
        deps = []
        for other in all_names:
            if other == name:
                continue
            if re.search(rf"\b{re.escape(other)}\b", body):
                deps.append(other)

        # If proof body is just admit (no real tactics), check if this
        # is a "final" lemma that would reference other section lemmas.
        # Heuristic: later lemmas depend on earlier ones (by file order).
        body_no_comments = re.sub(r"\(\*.*?\*\)", "", body)
        if not deps and len(body_no_comments.strip()) < 20:
            # Find file position of this lemma vs other admits
            name_pos = content.find(f"lemma {name}")
            deps = [a for a in admitted if a != name
                    and content.find(f"lemma {a}") < name_pos]

        # Can prove if all deps are proved (not admitted)
        unproved_deps = [d for d in deps if d in admitted and d != name]
        can_prove = len(unproved_deps) == 0

        result[name] = {
            "deps": deps,
            "unproved_deps": unproved_deps,
            "can_prove": can_prove,
        }

    return result


def _suggest_proving_order(dep_info: dict) -> list[str]:
    """Suggest an order for proving admitted lemmas based on dependencies.

    Returns lemma names in order: prove independent ones first, then dependent ones.
    """
    if not dep_info:
        return []

    # Separate into provable (no unproved deps) and blocked
    provable = [name for name, info in dep_info.items() if info["can_prove"]]
    blocked = [name for name, info in dep_info.items() if not info["can_prove"]]

    # Simple topological sort: provable first, then blocked
    # (blocked ones become provable after their deps are proved)
    order = provable + blocked
    return order


def _extract_modules_from_ec(content: str) -> str:
    """Extract a brief summary of module definitions."""
    modules = []
    for m in re.finditer(r"module\s+(\w+)\s*=\s*\{", content):
        name = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            i += 1
        body = content[start:i - 1].strip()
        if len(body) > 300:
            body = body[:300] + "..."
        modules.append(f"module {name}: {body}")
    return "\n".join(modules) if modules else ""


# ---------------------------------------------------------------------------
# Difficulty heuristic
# ---------------------------------------------------------------------------


def _classify_difficulty(
    lemma_name: str,
    lemma_statement: str,
    available_lemmas: list[dict],
    content: str,
) -> str:
    """Classify proof difficulty from the lemma statement and file context.

    Returns: "easy", "easy-medium", "medium", "medium-hard", "hard"
    """
    stmt = lemma_statement.lower()
    # Normalize "Pr [" to "Pr[" for pattern matching
    stmt_norm = re.sub(r"pr\s*\[", "pr[", stmt)

    # Easy: islossless
    if "islossless" in stmt:
        return "easy"

    # Easy: pure logic (no Pr, no equiv, no hoare)
    if "pr[" not in stmt_norm and "equiv" not in stmt and "hoare" not in stmt:
        return "easy"

    # Count local lemmas in same section — more = more complex proof
    n_local = len([l for l in available_lemmas if l["status"] == "proved"])

    # Has while loop in any module definition?
    has_while = "while" in content and "while" in _extract_modules_from_ec(content).lower()

    # Check if there's a probability inequality in the CONCLUSION (not preconditions)
    # Split on => to get the conclusion part
    conclusion = stmt_norm.split("=>")[-1] if "=>" in stmt_norm else stmt_norm

    # Probability inequality (check BEFORE equality — <= contains =)
    if "<=" in conclusion and "pr[" in conclusion:
        pr_terms = re.findall(r"Pr\s*\[\w+", lemma_statement)
        if len(pr_terms) >= 2 or n_local >= 3:
            return "medium-hard"
        return "medium"

    # Probability = 1 (correctness)
    if "= 1%r" in conclusion and "pr[" in conclusion:
        if has_while:
            return "medium-hard"
        return "medium"

    # Probability = 1/2 (coin flip)
    if ("1%r/2%r" in conclusion or "1/2" in conclusion) and "pr[" in conclusion:
        return "easy-medium"

    # Probability equality (two games)
    if "pr[" in conclusion and "=" in conclusion:
        pr_terms = re.findall(r"Pr\[\w+", lemma_statement)
        if len(pr_terms) >= 2:
            return "easy-medium"

    # Equiv
    if "equiv" in stmt:
        return "easy-medium"

    # Default
    if n_local >= 4:
        return "medium-hard"
    if n_local >= 2:
        return "medium"
    return "easy-medium"


# ---------------------------------------------------------------------------
# Main research function (replaces LLM planner)
# ---------------------------------------------------------------------------


def build_context_brief(
    config: RunConfig,
    target_content: str,
) -> ContextBrief:
    """Build the context brief from pre-read data. Pure Python."""
    available_lemmas = _extract_lemmas_from_ec(target_content)
    program_summary = _extract_modules_from_ec(target_content)

    target_statement = ""
    for lem in available_lemmas:
        if lem["name"] == config.lemma:
            target_statement = lem["statement"]
            break

    return ContextBrief(
        file_content="",
        target_statement=target_statement,
        available_lemmas=available_lemmas,
        program_summary=program_summary,
    )


def run(
    config: RunConfig,
    run_dir: Path,
) -> Optional[ProofPlan]:
    """Run proof research (pure Python — no LLM call).

    Reads the target file, extracts context, and classifies difficulty.
    Returns a ProofPlan with difficulty + context_brief (no phases — prover
    figures out strategy on its own).
    """
    from workflow.progress import status as pstatus

    # Target-scoped file content (keeps surrounding clones/ops/siblings the
    # prover legitimately uses, but replaces unrelated admits with `admit.`
    # and cuts the trailing part of the file when large). Small files
    # (<500 lines) still come through verbatim.
    target_content = _scoped_file_content(config.file, config.lemma)

    # Use the full file for internal classification/dependency checks. The
    # prover prompt no longer embeds this inventory.
    full_content = _read_file_content(config.file, max_lines=10_000)
    available_lemmas = _extract_lemmas_from_ec(full_content)

    # Find target lemma statement
    target_statement = ""
    for lem in available_lemmas:
        if lem["name"] == config.lemma:
            target_statement = lem["statement"]
            break

    # Classify difficulty
    difficulty = _classify_difficulty(
        config.lemma, target_statement, available_lemmas, target_content,
    )
    pstatus("Research", f"Difficulty: {difficulty}")

    # Dependency detection: check if target lemma has unproved dependencies
    dep_info = _detect_admit_dependencies(target_content, available_lemmas)
    proving_order = _suggest_proving_order(dep_info)

    target_dep = dep_info.get(config.lemma, {})
    if target_dep and not target_dep.get("can_prove", True) and not getattr(config, "eval_mode", False):
        unproved = target_dep.get("unproved_deps", [])
        pstatus("Research",
                f"WARNING: {config.lemma} depends on unproved lemmas: {unproved}")
        pstatus("Research",
                f"Suggested proving order: {proving_order}")

    # Build context brief
    context_brief = build_context_brief(config, target_content)

    # Save dependency info
    if dep_info:
        (run_dir / "dependencies.json").write_text(
            json.dumps({"deps": dep_info, "proving_order": proving_order}, indent=2),
            encoding="utf-8",
        )

    # Build plan (no phases — prover does strategy)
    # Note: dependency info is saved to dependencies.json for user reference
    # but NOT passed to the prover — admitted lemmas are valid in EC and
    # the prover should use them freely via smt().
    plan = ProofPlan(
        target_file=config.file,
        target_lemma=config.lemma,
        difficulty=difficulty,
        approach_summary="(prover determines strategy from context)",
        context_brief=context_brief,
    )
    return plan
