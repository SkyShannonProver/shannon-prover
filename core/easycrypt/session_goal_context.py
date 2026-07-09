"""Goal-context helper scans for EasyCrypt session tools.

These helpers inspect goal text, session history, and context files.  They do
not own session mutation or CLI dispatch, so command handlers and hooks can
use them without importing ``session_cli.py`` as a utility module.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_pr_canonical import (
    first_pr_equality_terms,
    pr_game_keys_from_text,
)


LARGE_GOAL_BYTES = 8000
PR_BRIDGE_STOPWORDS = {"Some", "None", "Pr", "True", "False"}


def goal_size(raw_goal: str) -> int:
    """Active goal byte size, 0 on empty."""
    return len(raw_goal.encode("utf-8")) if raw_goal else 0


def is_goal_too_large(raw_goal: str) -> bool:
    return goal_size(raw_goal) > LARGE_GOAL_BYTES


def too_large_warning_block(raw_goal: str) -> str:
    """Compact warning emitted when active goal text is too large."""
    sz = goal_size(raw_goal)
    return (
        f"[GOAL-TOO-LARGE] active goal is {sz} bytes "
        f"(threshold {LARGE_GOAL_BYTES}). This usually means "
        f"`inline *` (or a chain of `inline{{N}} K`) has expanded "
        f"the program tree past the point where one tactic can "
        f"productively reason about it. Recovery moves, in order of "
        f"preference: (1) `-prev` to revert the last expansion and "
        f"look for a named oracle equiv to apply via `call <name>` / "
        f"`ecall (<name> args)` (run `-sig <name>` for the arity, or "
        f"check `[AUTO-PIVOT-CALL-READY]` if it appeared on the "
        f"PRE-inline state). (2) If you must continue from this "
        f"state, narrow with `seq K K : (Inv)` to make each leg "
        f"tractable. Downstream emit blocks below are abbreviated to "
        f"reduce scroll — re-run `-goal-info` AFTER `-prev` for the "
        f"non-abbreviated view of the smaller state.\n"
    )


def scan_local_equiv_lemmas(context_file: Path | str) -> list[str]:
    """Scan a context .ec file for local equiv lemma names."""
    try:
        p = Path(context_file)
        if not p.exists():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
        names = re.findall(r"\blocal\s+equiv\s+(\w+)", text)
        return list(dict.fromkeys(names))
    except Exception:
        return []


def scan_local_equiv_details(context_file: Path | str) -> list[dict[str, str]]:
    """Return local equiv names and connected procedure paths."""
    try:
        p = Path(context_file)
        if not p.exists():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r"\blocal\s+equiv\s+(\w+)(?:\s+\w+)*\s*(?:\[[^\]]*\])?\s*:[ \t\n]*([^~]+?)\s*~\s*([^:]+?)\s*:",
            text,
            re.DOTALL,
        ):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            results.append({
                "name": name,
                "lhs_proc": m.group(2).strip(),
                "rhs_proc": m.group(3).strip(),
            })
        return results
    except Exception:
        return []


def match_equivs_to_calls(
    call_procs: list[Any],
    equiv_details: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Map each CALL procedure path to local equiv lemmas with matching tokens."""
    result: dict[str, list[str]] = {}
    for proc in call_procs:
        proc_s = str(proc)
        tokens = [t.lower() for t in re.findall(r"[A-Za-z]{3,}", proc_s)]
        candidates: list[str] = []
        for e in equiv_details:
            both = (str(e["lhs_proc"]) + " " + str(e["rhs_proc"])).lower()
            if any(t in both for t in tokens):
                candidates.append(str(e["name"]))
        if candidates:
            result[proc_s] = list(dict.fromkeys(candidates))
    return result


def scan_prob_ineq_lemmas(
    context_file: Path | str,
    exclude_name: str = "",
) -> list[dict[str, str]]:
    """Scan context file for lemmas of the form ``Pr[G1...] <= Pr[G2...]``."""
    try:
        p = Path(context_file)
        if not p.exists():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r"\blemma\s+(\w+)[^.]*Pr\s*\[\s*(\w+)[^\]]*\]\s*<=\s*Pr\s*\[\s*(\w+)",
            text,
            re.DOTALL,
        ):
            name = m.group(1)
            if name in seen:
                continue
            if exclude_name and name == exclude_name:
                continue
            seen.add(name)
            results.append({
                "name": name,
                "lhs_game": m.group(2),
                "rhs_game": m.group(3),
            })
        return results
    except Exception:
        return []


def extract_module_keywords(info: Any) -> list[str]:
    """Pull likely bridge-module keywords from a probability goal's game names."""
    blob_parts: list[str] = []
    for attr in (
        "prob_lhs_game", "prob_lhs_oracle", "prob_rhs_game",
        "prob_rhs_oracle", "diff_eq_lhs_neg_game", "diff_eq_rhs_neg_game",
    ):
        v = getattr(info, attr, "") or ""
        if v:
            blob_parts.append(v)
    for addend in (
        getattr(info, "prob_compound_lhs", [])
        + getattr(info, "prob_compound_rhs", [])
    ):
        for k in ("game", "oracle"):
            if addend.get(k):
                blob_parts.append(addend[k])

    tokens = re.findall(r"\b[A-Z][A-Za-z0-9_]{2,}\b", " ".join(blob_parts))
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        for i in range(1, len(token)):
            ch = token[i]
            if not ch.isupper():
                continue
            prev = token[i - 1]
            nxt = token[i + 1] if i + 1 < len(token) else ""
            if prev.islower() or (prev.isupper() and nxt.islower()):
                suffix = token[i:]
                if len(suffix) >= 3:
                    expanded.append(suffix)
    return list(dict.fromkeys(expanded))


def scan_pr_bridge_lemmas(
    search_dirs: list[Path | str],
    keywords: list[str],
    *,
    goal_text: str = "",
    search_files: list[Path | str] | None = None,
    excluded_names: set[str] | list[str] | tuple[str, ...] | None = None,
    excluded_files: set[Path | str] | list[Path | str] | tuple[Path | str, ...] | None = None,
    allow_local_files: set[Path | str] | list[Path | str] | tuple[Path | str, ...] | None = None,
    max_files: int = 200,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Find cross-file ``Pr[...] = Pr[...]`` rewrite lemmas.

    ``keywords`` are a cheap lexical recall signal, but they should not be the
    authority: useful compiler bridges often have generic names such as
    ``bridge0`` or project-specific names such as ``pr_PushBound_list`` whose
    names do not mention the current endpoint tokens.  When ``goal_text`` is
    available, score candidates by the typed-looking Pr endpoints in the lemma
    declaration and surface structurally related bridges even without a name
    hit.

    Availability is deliberately conservative.  ``local lemma`` declarations
    are only returned from explicit ``allow_local_files`` such as the extracted
    session context; local declarations found by recursively scanning include
    directories are not exported handles.  ``excluded_names`` and
    ``excluded_files`` keep the current target lemma and original full source
    file from becoming self/future-proof hints.
    """
    effective = [
        k for k in keywords if len(k) >= 3 and k not in PR_BRIDGE_STOPWORDS
    ]
    goal_profile = _pr_bridge_goal_profile(goal_text)
    if not effective and not goal_profile["atoms"]:
        return []

    results: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    files_scanned = 0
    excluded_name_set = {str(name) for name in (excluded_names or []) if str(name)}
    excluded_file_set = _resolved_path_set(excluded_files or [])
    allow_local_file_set = _resolved_path_set(allow_local_files or [])
    lemma_head_pattern = re.compile(
        # Name class must include the EasyCrypt prime: `(\w+)\b` dropped the
        # trailing `'` (a non-word char) from e.g. `perm3_perm3'`, so the
        # surfaced `rewrite <name>.` candidate named a non-existent lemma.
        r"\b(?:(local)\s+)?(?:(lemma|axiom)|declare\s+axiom)\s+"
        r"([A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])"
    )
    for ec_file in _iter_pr_bridge_scan_files(
        search_dirs,
        search_files=search_files or [],
        excluded_files=excluded_file_set,
        max_files=max_files,
    ):
        files_scanned += 1
        file_key = _resolved_path_key(ec_file)
        allow_local = bool(file_key and file_key in allow_local_file_set)
        try:
            if ec_file.stat().st_size > 500_000:
                continue
            text = ec_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for head in lemma_head_pattern.finditer(text):
            name = head.group(3)
            is_local = bool(head.group(1))
            if name in excluded_name_set:
                continue
            if is_local and not allow_local:
                continue
            if name in seen_names:
                continue
            hits = [
                kw for kw in effective
                if re.search(
                    rf"(?<![A-Za-z0-9]){re.escape(kw)}(?![A-Za-z0-9])",
                    name,
                )
            ]
            body_slice = text[head.end():head.end() + 1500]
            cut = len(body_slice)
            for marker in (r"\bproof\.", r"\bqed\.", r"\blemma\s", r"\baxiom\s"):
                mm = re.search(marker, body_slice)
                if mm and mm.start() < cut:
                    cut = mm.start()
            body_slice = body_slice[:cut]
            pr_eq = first_pr_equality_terms(body_slice)
            if not pr_eq:
                continue
            lhs_term, rhs_term = pr_eq
            lhs_game = str(lhs_term.get("game_key") or "")
            rhs_game = str(rhs_term.get("game_key") or "")
            structural = _score_pr_bridge_candidate(
                lhs_game,
                rhs_game,
                goal_profile,
            )
            if not hits and structural["score"] <= 0:
                continue
            seen_names.add(name)
            results.append({
                "name": name,
                "file": str(ec_file),
                "declaration_kind": (
                    "local_lemma"
                    if is_local else
                    "axiom"
                    if head.group(2) == "axiom" or "declare axiom" in head.group(0)
                    else
                    "lemma"
                ),
                "availability": (
                    "session_local" if is_local else "exported"
                ),
                "lhs_game": lhs_game,
                "rhs_game": rhs_game,
                "matched_keywords": hits,
                "structural_score": structural["score"],
                "matched_endpoint_atoms": structural["matched_atoms"],
                "matched_by": (
                    "name_and_endpoint"
                    if hits and structural["score"] > 0 else
                    "name"
                    if hits else
                    "endpoint"
                ),
            })
        if files_scanned >= max_files or len(results) >= max_results * 2:
            break

    results.sort(key=lambda r: (
        -int(r.get("structural_score") or 0),
        0 if r.get("availability") == "exported" else 1,
        -len(r["matched_keywords"]),
        len(r["name"]),
    ))
    return results[:max_results]


def _iter_pr_bridge_scan_files(
    search_dirs: list[Path | str],
    *,
    search_files: list[Path | str],
    excluded_files: set[Path],
    max_files: int,
) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()

    def add(path_like: Path | str) -> None:
        if len(out) >= max_files:
            return
        path = Path(path_like)
        if not path.exists() or not path.is_file():
            return
        key = _resolved_path_key(path)
        if not key or key in seen or key in excluded_files:
            return
        seen.add(key)
        out.append(path)

    for path in search_files:
        add(path)

    for sd in search_dirs:
        sp = Path(sd)
        if not sp.exists() or not sp.is_dir():
            continue
        for ec_file in _iter_easycrypt_source_files(sp):
            if len(out) >= max_files:
                break
            add(ec_file)
    return out


def _resolved_path_set(paths: Any) -> set[Path]:
    return {
        key for key in (_resolved_path_key(path) for path in paths)
        if key is not None
    }


def _resolved_path_key(path_like: Path | str) -> Path | None:
    try:
        return Path(path_like).resolve()
    except Exception:
        return None


def _iter_easycrypt_source_files(root: Path) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in ("*.ec", "*.eca"):
        for path in root.rglob(pattern):
            if path in seen:
                continue
            if any(part.startswith(".ec_session") for part in path.parts):
                continue
            seen.add(path)
            out.append(path)
    return sorted(out)


def _pr_bridge_goal_profile(goal_text: str) -> dict[str, Any]:
    games = pr_game_keys_from_text(goal_text)
    atoms: set[str] = set()
    roots: set[str] = set()
    for game in games:
        atoms.update(_pr_bridge_atoms(game))
        root = _pr_bridge_root(game)
        if root:
            roots.add(root)
    return {
        "games": games,
        "game_set": set(games),
        "atoms": atoms,
        "roots": roots,
    }


def _score_pr_bridge_candidate(
    lhs_game: str,
    rhs_game: str,
    goal_profile: dict[str, Any],
) -> dict[str, Any]:
    goal_atoms = set(goal_profile.get("atoms") or set())
    if not goal_atoms:
        return {"score": 0, "matched_atoms": []}
    candidate_games = [game for game in (lhs_game, rhs_game) if game]
    candidate_atoms: set[str] = set()
    candidate_roots: set[str] = set()
    for game in candidate_games:
        candidate_atoms.update(_pr_bridge_atoms(game))
        root = _pr_bridge_root(game)
        if root:
            candidate_roots.add(root)

    matched_atoms = sorted(candidate_atoms & goal_atoms)
    score = len(matched_atoms)
    goal_games = set(goal_profile.get("game_set") or set())
    score += 12 * sum(1 for game in candidate_games if game in goal_games)
    goal_roots = set(goal_profile.get("roots") or set())
    score += 4 * len(candidate_roots & goal_roots)
    if _looks_like_ro_bridge(lhs_game, rhs_game) and "RO" in goal_atoms:
        score += 3
    return {"score": score, "matched_atoms": matched_atoms[:12]}


def _looks_like_ro_bridge(lhs_game: str, rhs_game: str) -> bool:
    lhs_atoms = _pr_bridge_atoms(lhs_game)
    rhs_atoms = _pr_bridge_atoms(rhs_game)
    return "RO" in lhs_atoms and "RO" in rhs_atoms and lhs_atoms != rhs_atoms


def _pr_bridge_root(game: str) -> str:
    match = re.match(
        r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)",
        str(game or "").strip(),
    )
    return match.group(1).rsplit(".", 1)[-1] if match else ""


def _pr_bridge_atoms(text: str) -> set[str]:
    atoms: set[str] = set()
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", str(text or "")):
        if token in PR_BRIDGE_STOPWORDS or len(token) < 2:
            continue
        atoms.add(token)
        for piece in _camel_suffixes(token):
            if piece not in PR_BRIDGE_STOPWORDS and len(piece) >= 2:
                atoms.add(piece)
    return atoms


def _camel_suffixes(token: str) -> list[str]:
    out: list[str] = []
    for idx in range(1, len(token)):
        ch = token[idx]
        if not ch.isupper():
            continue
        prev = token[idx - 1]
        nxt = token[idx + 1] if idx + 1 < len(token) else ""
        if prev.islower() or (prev.isupper() and nxt.islower()):
            suffix = token[idx:]
            if len(suffix) >= 2:
                out.append(suffix)
    if token.endswith("RO") and token != "RO":
        out.append("RO")
    return out


def infer_remaining_goals(session: Any, count: int) -> list[dict[str, Any]]:
    """Infer hidden remaining subgoal shapes from recent branching tactics."""
    if not session.history.exists():
        return []
    try:
        tactics = [
            line.strip()
            for line in session.history.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception:
        return []

    def pad_carryover(
        spawned: list[dict[str, Any]],
        count: int,
        tac: str,
    ) -> list[dict[str, Any]]:
        out = list(spawned[:count])
        if len(out) < count:
            for i in range(count - len(out)):
                out.insert(0, {
                    "subgoal_n": i + 1,
                    "predicted_type": "(carried-over from earlier branching)",
                    "description": (
                        "Pending subgoal from a branching tactic earlier "
                        "in history; this entry isn't from the latest "
                        f"`{tac.split()[0] if tac.split() else '?'}`. "
                        "Run -goal-info on each subgoal as you reach it "
                        "to see its actual shape."
                    ),
                    "origin_tactic": "(earlier branching, not tracked)",
                })
            for i, entry in enumerate(out, 1):
                entry["subgoal_n"] = i
        return out

    for tac in reversed(tactics):
        tac_lower = tac.lower().strip().rstrip(".;")
        first_word = tac_lower.split()[0] if tac_lower.split() else ""

        if first_word == "call" and "_:" in tac:
            is_3arg = tac.count(",") >= 1
            sub: list[dict[str, Any]] = []
            for i in range(count):
                if is_3arg and i == count - 1:
                    sub.append({
                        "subgoal_n": i + 1,
                        "predicted_type": "ambient",
                        "description": "Up-to-bad sidecondition (3-arg call with bad predicate)",
                        "origin_tactic": tac[:100],
                    })
                else:
                    sub.append({
                        "subgoal_n": i + 1,
                        "predicted_type": "(inherits prior goal type)",
                        "description": "Oracle equivalence or continuation (inherits parent judgment type)",
                        "origin_tactic": tac[:100],
                    })
            return sub

        if first_word == "conseq":
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": "ambient",
                 "description": "New pre ==> old pre",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "(inherits prior goal type)",
                 "description": "Main judgment under conseq's new pre/post",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word == "seq":
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": "(inherits prior goal type)",
                 "description": "Prefix 0..K (pre -> post after first K stmts)",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "(inherits prior goal type)",
                 "description": "Suffix K..end (post after K -> final post)",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word == "if":
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": "(inherits prior goal type)",
                 "description": "Then-branch (condition true)",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "(inherits prior goal type)",
                 "description": "Else-branch (condition false)",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word == "while":
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": "(inherits prior goal type)",
                 "description": "Loop body preserves invariant",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "(inherits prior goal type)",
                 "description": "(pRHL only) Second body or termination",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 3, "predicted_type": "ambient",
                 "description": "(pRHL only) Invariant => post after loop",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word == "transitivity":
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": "ambient",
                 "description": "LHS pre => M.proc pre (ambient implication)",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "ambient",
                 "description": "M.proc post => RHS post (ambient implication)",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 3, "predicted_type": "(inherits prior goal type)",
                 "description": "LHS ~ M.proc judgment (chain leg 1)",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 4, "predicted_type": "(inherits prior goal type)",
                 "description": "M.proc ~ RHS judgment (chain leg 2)",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word == "case":
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": "(inherits prior goal type)",
                 "description": "Branch where case fact holds",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "(inherits prior goal type)",
                 "description": "Branch where case fact fails",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word == "split":
            return [
                {"subgoal_n": i + 1,
                 "predicted_type": "(inherits prior goal type)",
                 "description": f"Conjunct {i + 1} of N (split decomposition)",
                 "origin_tactic": tac[:100]}
                for i in range(count)
            ]

        if first_word == "have":
            claim_is_pr = "Pr[" in tac or "Pr [" in tac
            s1_type = "probability" if claim_is_pr else "ambient"
            if "->:" in tac.replace(" ", ""):
                # EC's display after a standalone `have -> : ... .` is subtle:
                # the visible current goal is the rewrite equality claim, and
                # the continuation is not reliable enough to reconstruct from
                # the tactic text alone. Prefer no hidden-goal prediction over
                # telling the prover there is a continuation when the current
                # state may only be the claim.
                continue
            if ":=" in tac:
                continue
            return pad_carryover([
                {"subgoal_n": 1, "predicted_type": s1_type,
                 "description": f"Prove the `have` claim ({s1_type} goal based on claim shape)",
                 "origin_tactic": tac[:100]},
                {"subgoal_n": 2, "predicted_type": "(inherits prior goal type)",
                 "description": "Continuation with `have` hypothesis in context",
                 "origin_tactic": tac[:100]},
            ], count, tac)

        if first_word in (
            "proc", "inline", "wp", "rnd", "auto", "skip", "move",
            "trivial", "smt", "simplify",
        ):
            continue

    return []
