"""Dataflow-backed invariant skeletons for EasyCrypt pRHL goals.

EasyCrypt's native pHL rules already use variable-access analyses such as
``EcPV.s_read``, ``EcPV.s_write``, and ``PV.fv``.  This pass mirrors that
compiler idea in our lightweight parsed-goal IR: start from postcondition
variables, walk program statements backward, and surface the equality resources
that an invariant/call cut is likely to need.

The pass is intentionally conservative and diagnostic.  It does not replace
EasyCrypt's typed variable-access analysis; it provides a prover-facing summary
before the agent chooses `call (_: Inv)`, `seq`, or `while`.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_stripped_strings as _dedupe_strings,
    deduped_stripped_string_list as _strings,
    infer_statement_kind as _infer_kind,
    split_flat_conjuncts as _split_flat_conjuncts,
)


DATAFLOW_INVARIANT_SCHEMA_VERSION = 1
DATAFLOW_INVARIANT_KIND = "easycrypt_dataflow_invariant"
_READ_STOP_WORDS = {
    "if",
    "then",
    "else",
    "while",
    "return",
    "true",
    "false",
    "res",
    "result",
    "witness",
    "nth",
    "size",
    "block",
}

# A token invoked as ``<@ Game(A).main()`` / ``.enc(`` is a procedure or module
# call target, never a state variable.  Backward read extraction can otherwise
# pick the callee name up as a "read" and bake a bogus ``={main}`` into the
# equality frame, which reads to the agent like a real coupling to discharge.
_PROC_CALL_RE = re.compile(r"(?:<@\s*|@\s*|\.)\s*([A-Za-z_][A-Za-z0-9_']*)\s*\(")

# A right-hand side that is a closed *initial* constant.  ``lbad1{2} = []`` /
# ``badi{2} = false`` / ``cbadi{2} = 0`` describe the program's *initial* state,
# not something a call/loop invariant preserves.  Surfacing them as invariant
# conjuncts is misleading: the agent reads the skeleton as a complete invariant,
# yet those lists/counters are not empty mid-game.
_CONST_RHS_RE = re.compile(
    r"^(?:"
    r"\[\s*\]"                                  # empty list
    r"|\{\s*\}"                                 # empty set/map literal
    r"|true|false|None"
    r"|witness"
    r"|empty|fset0|FSet\.fset0|Map\.empty|SmtMap\.empty|emptymap"
    r"|-?\d+(?:\.\d+)?"                         # numeric literal
    r"|\"[^\"]*\""                              # string literal
    r")$"
)
_TOP_LEVEL_EQ_RE = re.compile(r"(?<![<>=!])=(?![=>])")


def _called_procedure_names(text: str) -> set[str]:
    """Procedure/module call targets in the goal text (never state variables)."""
    return {m.group(1) for m in _PROC_CALL_RE.finditer(str(text or ""))}


def _is_initial_value_atom(atom: str) -> bool:
    """True for a side fact equating a variable to a closed initial constant.

    Such facts (``x{2} = []``) hold only at game start, so they are not valid
    call-invariant conjuncts; carrying them into ``suggested_invariant`` makes
    the skeleton look complete while baking in the initial state.
    """
    text = str(atom or "").strip().rstrip(".")
    parts = _TOP_LEVEL_EQ_RE.split(text, maxsplit=1)
    if len(parts) != 2:
        return False
    rhs = parts[1].strip()
    if "{" in rhs:  # RHS references a program side -> relational, keep it
        return False
    return bool(_CONST_RHS_RE.match(rhs))


def build_invariant_skeleton(
    parsed_goal: dict[str, Any],
    goal_type: str,
) -> dict[str, Any]:
    """Build a JSON-ready invariant skeleton from postcondition + statements."""
    parsed = _dict(parsed_goal)
    if goal_type not in {"pRHL", "equiv"}:
        return {"available": False}

    pre = _strip_condition_label(str(parsed.get("pre") or ""))
    post = _strip_condition_label(str(parsed.get("post") or ""))
    pre_shared = _shared_equalities(pre)
    pre_relational_atoms = _relational_atoms(pre)
    post_shared = _shared_equalities(post)
    relational_atoms = _relational_atoms(post)
    post_side_vars = _side_variables(post)
    statements = {
        "left": _normalized_statements(parsed.get("left_statements")),
        "right": _normalized_statements(parsed.get("right_statements")),
    }
    proc_names = _called_procedure_names(
        " ".join(
            str(stmt.get("text") or "")
            for side in ("left", "right")
            for stmt in statements[side]
        )
        + " " + pre + " " + post
    )
    dataflow = {
        side: _backward_liveness(
            stmts,
            _initial_live_vars(post_shared, post_side_vars, side),
        )
        for side, stmts in statements.items()
    }
    common_code_reads = _common_ordered(
        dataflow["left"]["all_reads"],
        dataflow["right"]["all_reads"],
    )
    dataflow_equalities = [
        var for var in common_code_reads
        if var not in post_shared and var not in proc_names
    ]
    equality_vars = [var for var in post_shared if var not in proc_names]
    equality_vars += dataflow_equalities

    live_names = [
        name
        for name in _dedupe_strings(
            equality_vars
            + dataflow["left"]["all_reads"]
            + dataflow["right"]["all_reads"]
            + dataflow["left"]["all_writes"]
            + dataflow["right"]["all_writes"]
            + _ordered_side_var_names(" /\\ ".join(relational_atoms))
        )
        if name not in proc_names
    ]
    carried_pre = _carried_precondition_relations(
        pre_shared,
        pre_relational_atoms,
        relational_atoms=relational_atoms,
        live_names=live_names,
        equality_vars=equality_vars,
    )
    carried_pre_shared = _list(carried_pre.get("shared_equalities"))
    carried_pre_atoms = _list(carried_pre.get("relational_atoms"))
    equality_vars += carried_pre_shared

    dropped_initial_value_atoms: list[str] = []
    conjuncts: list[dict[str, Any]] = []
    if equality_vars:
        conjuncts.append({
            "text": "={" + ", ".join(equality_vars) + "}",
            "source": "postcondition_and_code_reads",
            "vars": equality_vars,
            "reason": (
                "postcondition shared equalities plus variables read on both "
                "sides of the current code"
            ),
        })
    for atom in relational_atoms:
        if _is_initial_value_atom(atom):
            dropped_initial_value_atoms.append(atom)
            continue
        conjuncts.append({
            "text": atom,
            "source": "postcondition_relational_atom",
            "vars": _ordered_side_var_names(atom),
            "reason": "side-specific relation appears in the postcondition",
        })
    for atom in carried_pre_atoms:
        if _is_initial_value_atom(atom):
            dropped_initial_value_atoms.append(atom)
            continue
        conjuncts.append({
            "text": atom,
            "source": "carried_precondition_relational_atom",
            "vars": _ordered_side_var_names(atom),
            "reason": (
                "side-specific relation appears in the precondition and "
                "mentions live names from the current program/postcondition"
            ),
        })

    suggested = " /\\ ".join(str(item["text"]) for item in conjuncts)
    return {
        "schema_version": DATAFLOW_INVARIANT_SCHEMA_VERSION,
        "kind": DATAFLOW_INVARIANT_KIND,
        "available": bool(suggested),
        "source": "postcondition+dataflow" if suggested else "",
        "pre_shared_equalities": pre_shared,
        "pre_relational_atoms": pre_relational_atoms,
        "shared_equalities": post_shared,
        "dataflow_equalities": dataflow_equalities,
        "carried_precondition_equalities": carried_pre_shared,
        "carried_precondition_atoms": carried_pre_atoms,
        "carried_precondition_closure": carried_pre,
        "relational_atoms": relational_atoms,
        "live_reads": {
            "left": dataflow["left"]["all_reads"],
            "right": dataflow["right"]["all_reads"],
        },
        "live_writes": {
            "left": dataflow["left"]["all_writes"],
            "right": dataflow["right"]["all_writes"],
        },
        "post_side_variables": post_side_vars,
        "backward_liveness": {
            "left": dataflow["left"]["steps"],
            "right": dataflow["right"]["steps"],
        },
        "conjuncts": conjuncts,
        "dropped_initial_value_atoms": dropped_initial_value_atoms,
        "excluded_procedure_names": sorted(proc_names),
        "suggested_invariant": suggested,
        "native_reference": {
            "easycrypt_modules": [
                "EcPV.s_read",
                "EcPV.s_write",
                "EcPV.PV.fv",
                "EcPhlTrans.t_equivS_trans_eq",
            ],
            "note": (
                "This is a lightweight mirror of EasyCrypt's native access "
                "analysis, not a replacement for the typed checker."
            ),
        },
    }


def _carried_precondition_relations(
    pre_shared: list[str],
    pre_relational_atoms: list[str],
    *,
    relational_atoms: list[str],
    live_names: list[str],
    equality_vars: list[str],
) -> dict[str, Any]:
    carried_shared: list[str] = []
    carried_atoms: list[str] = []
    closure_steps: list[dict[str, Any]] = []
    live = _dedupe_strings(live_names)
    live_nodes = set(_live_nodes(live))
    remaining_shared = [
        _precondition_entry(
            kind="shared_equality",
            text=name,
            vars=[name],
            source="precondition_shared_equality",
        )
        for name in pre_shared
        if name not in equality_vars
    ]
    remaining_atoms = [
        _precondition_entry(
            kind=(
                "side_equality"
                if _is_side_equality_atom(atom) else
                "side_relation"
            ),
            text=atom,
            vars=_ordered_side_var_names(atom),
            source="precondition_relational_atom",
        )
        for atom in pre_relational_atoms
        if atom not in relational_atoms
    ]
    changed = True
    while changed:
        changed = False
        next_shared: list[dict[str, Any]] = []
        for entry in remaining_shared:
            if _entry_touches_live_frontier(entry, live, live_nodes):
                text = str(entry.get("text") or "")
                carried_shared.append(text)
                live.extend(_list(entry.get("vars")) or [text])
                live = _dedupe_strings(live)
                live_nodes.update(_list(entry.get("nodes")))
                closure_steps.append(_closure_step(
                    entry,
                    reason=(
                        "shared equality is connected to the live "
                        "postcondition/program frontier"
                    ),
                ))
                changed = True
            else:
                next_shared.append(entry)
        remaining_shared = next_shared
        next_atoms: list[dict[str, Any]] = []
        for entry in remaining_atoms:
            if _entry_touches_live_frontier(entry, live, live_nodes):
                atom = str(entry.get("text") or "")
                carried_atoms.append(atom)
                live.extend(_list(entry.get("vars")))
                live = _dedupe_strings(live)
                live_nodes.update(_list(entry.get("nodes")))
                closure_steps.append(_closure_step(
                    entry,
                    reason=(
                        "precondition relation is in the equality/liveness "
                        "closure of the current cut"
                    ),
                ))
                changed = True
            else:
                next_atoms.append(entry)
        remaining_atoms = next_atoms
    return {
        "available": bool(carried_shared or carried_atoms),
        "kind": "precondition_equality_liveness_closure",
        "shared_equalities": _dedupe_strings(carried_shared),
        "relational_atoms": _dedupe_strings(carried_atoms),
        "closure_steps": closure_steps,
        "final_live_names": live,
        "final_live_nodes": sorted(live_nodes),
        "strategy_boundary": (
            "This is a conservative dataflow/liveness closure over the "
            "current precondition. It explains which precondition resources "
            "should be kept in a seq/call/while invariant; EasyCrypt still "
            "type-checks the final tactic."
        ),
    }


def _precondition_entry(
    *,
    kind: str,
    text: str,
    vars: list[str],
    source: str,
) -> dict[str, Any]:
    clean = str(text or "").strip()
    names = _dedupe_strings(vars or [clean])
    return {
        "kind": kind,
        "text": clean,
        "vars": names,
        "source": source,
        "nodes": _entry_nodes(clean, names),
    }


def _closure_step(entry: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "kind": str(entry.get("kind") or ""),
        "text": str(entry.get("text") or ""),
        "vars": _list(entry.get("vars")),
        "nodes": _list(entry.get("nodes")),
        "source": str(entry.get("source") or ""),
        "reason": reason,
    }


def _entry_touches_live_frontier(
    entry: dict[str, Any],
    live_names: list[str],
    live_nodes: set[str],
) -> bool:
    nodes = set(_list(entry.get("nodes")))
    if nodes & live_nodes:
        return True
    return _atom_mentions_live_name(str(entry.get("text") or ""), live_names)


def _entry_nodes(text: str, names: list[str]) -> list[str]:
    nodes: list[str] = []
    for name in names:
        nodes.extend(_name_node_variants(name))
    for name, side in re.findall(
        r"([A-Za-z_][A-Za-z0-9_'.]*(?:\.[A-Za-z_][A-Za-z0-9_'.]*)*)\{([12])\}",
        str(text or ""),
    ):
        nodes.extend(_name_node_variants(name, side=side))
    return _dedupe_strings(nodes)


def _live_nodes(names: list[str]) -> list[str]:
    nodes: list[str] = []
    for name in names:
        nodes.extend(_name_node_variants(name))
    return _dedupe_strings(nodes)


def _name_node_variants(name: str, *, side: str = "") -> list[str]:
    raw = str(name or "").strip()
    if not raw:
        return []
    leaf = raw.rsplit(".", 1)[-1]
    bases = _dedupe_strings([raw, leaf])
    out: list[str] = []
    for base in bases:
        out.append(base)
        if side:
            out.append(f"{base}{{{side}}}")
        else:
            out.append(f"{base}{{1}}")
            out.append(f"{base}{{2}}")
    return _dedupe_strings(out)


def _is_side_equality_atom(atom: str) -> bool:
    text = str(atom or "")
    if "{1}" not in text and "{2}" not in text:
        return False
    if "<=" in text or ">=" in text or "=>" in text:
        return False
    return bool(re.search(r"(?<![<>=])=(?!=|>)", text))


def _backward_liveness(
    statements: list[dict[str, Any]],
    initial_live: list[str],
) -> dict[str, Any]:
    live = set(initial_live)
    steps_reversed: list[dict[str, Any]] = []
    all_reads: list[str] = []
    all_writes: list[str] = []
    for stmt in statements:
        all_reads.extend(stmt["vars_read"])
        all_writes.extend(stmt["vars_written"])
    for stmt in reversed(statements):
        reads = set(stmt["vars_read"])
        writes = set(stmt["vars_written"])
        live_after = _ordered_from_set(live, initial_live + stmt["vars_read"])
        needed_reads = bool(not writes or writes & live)
        live = (live - writes) | (reads if needed_reads else set())
        steps_reversed.append({
            "statement_id": stmt["statement_id"],
            "order": stmt["order"],
            "kind": stmt["kind"],
            "text": stmt["text"],
            "vars_read": stmt["vars_read"],
            "vars_written": stmt["vars_written"],
            "live_after": live_after,
            "live_before": _ordered_from_set(
                live,
                initial_live + stmt["vars_read"] + stmt["vars_written"],
            ),
            "read_vars_promoted": _ordered_from_set(
                reads if needed_reads else set(),
                stmt["vars_read"],
            ),
        })
    steps = list(reversed(steps_reversed))
    return {
        "steps": steps,
        "initial_live": initial_live,
        "entry_live": _ordered_from_set(live, initial_live + all_reads),
        "all_reads": _dedupe_strings(all_reads),
        "all_writes": _dedupe_strings(all_writes),
    }


def _normalized_statements(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for order, stmt in enumerate(_list(value), start=1):
        if not isinstance(stmt, dict):
            continue
        text = str(stmt.get("text") or "")
        position = str(stmt.get("pos_path") or stmt.get("pos") or order)
        out.append({
            "statement_id": str(stmt.get("statement_id") or position),
            "order": order,
            "kind": str(stmt.get("type") or _infer_kind(text)),
            "text": text,
            "vars_read": _statement_reads(stmt),
            "vars_written": _statement_writes(stmt),
        })
    return out


def _statement_reads(stmt: dict[str, Any]) -> list[str]:
    explicit = _read_vars(stmt.get("vars_read"))
    if explicit:
        return explicit
    text = str(stmt.get("text") or "")
    if "<@" in text:
        args = _call_args(text)
        return _vars_from_expr(args)
    if "<$" in text:
        return _vars_from_expr(text.split("<$", 1)[1])
    if "<-" in text:
        return _vars_from_expr(text.split("<-", 1)[1])
    return _vars_from_expr(text)


def _statement_writes(stmt: dict[str, Any]) -> list[str]:
    explicit = _strings(stmt.get("vars_written"))
    if explicit:
        return explicit
    text = str(stmt.get("text") or "")
    for marker in ("<@", "<$", "<-"):
        if marker in text:
            return _vars_from_lvalue(text.split(marker, 1)[0])
    return []


def _initial_live_vars(
    shared_equalities: list[str],
    side_variables: dict[str, list[str]],
    side: str,
) -> list[str]:
    side_key = "1" if side == "left" else "2"
    return _dedupe_strings(shared_equalities + side_variables.get(side_key, []))


def _shared_equalities(text: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(r"=\{\s*([^}]*)\s*\}", text):
        for item in match.group(1).split(","):
            name = item.strip()
            if name:
                values.append(name)
    return _dedupe_strings(values)


def _relational_atoms(text: str) -> list[str]:
    atoms: list[str] = []
    for atom in _split_flat_conjuncts(text):
        piece = _strip_condition_label(atom)
        if not piece or piece.startswith("={"):
            continue
        if "{1}" in piece or "{2}" in piece:
            atoms.append(piece)
    return _dedupe_strings(atoms)


def _side_variables(text: str) -> dict[str, list[str]]:
    out = {"1": [], "2": []}
    for name, side in re.findall(
        r"([A-Za-z_][A-Za-z0-9_'.]*(?:\.[A-Za-z_][A-Za-z0-9_'.]*)*)\{([12])\}",
        text,
    ):
        out.setdefault(side, []).append(name)
    return {side: _dedupe_strings(values) for side, values in out.items()}


def _atom_mentions_live_name(atom: str, live_names: list[str]) -> bool:
    text = str(atom or "")
    if not text:
        return False
    if not live_names:
        return True
    for name in live_names:
        raw = str(name or "").strip()
        if not raw:
            continue
        leaf = raw.rsplit(".", 1)[-1]
        for candidate in (raw, leaf):
            if candidate and re.search(
                rf"(?<![A-Za-z0-9_'.]){re.escape(candidate)}(?![A-Za-z0-9_'])",
                text,
            ):
                return True
    return False


def _ordered_side_var_names(text: str) -> list[str]:
    names: list[str] = []
    for side_names in _side_variables(text).values():
        names.extend(side_names)
    return _dedupe_strings(names)


def _common_ordered(left: list[str], right: list[str]) -> list[str]:
    right_set = set(right)
    return [name for name in _dedupe_strings(left) if name in right_set]


def _ordered_from_set(values: set[str], preferred_order: list[str]) -> list[str]:
    out = [name for name in _dedupe_strings(preferred_order) if name in values]
    out.extend(sorted(values - set(out)))
    return out


def _call_args(text: str) -> str:
    after = text.split("<@", 1)[1] if "<@" in text else text
    start = after.find("(")
    if start < 0:
        return ""
    depth = 0
    for idx in range(start, len(after)):
        char = after[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return after[start + 1:idx]
    return after[start + 1:]


def _vars_from_lvalue(text: str) -> list[str]:
    return _dedupe_strings(
        token for token in _vars_from_expr(text)
        if token not in {"_", "res", "result"}
    )


def _vars_from_expr(text: str) -> list[str]:
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",
        text,
    )
    return _dedupe_strings(
        token for token in tokens
        if _is_dataflow_read_var(token)
    )


def _strip_condition_label(text: str) -> str:
    return re.sub(
        r"^\s*(?:pre|post)\s*=\s*",
        "",
        str(text or "").strip(),
        flags=re.IGNORECASE,
    )


def _read_vars(value: Any) -> list[str]:
    return _dedupe_strings(
        token for token in _strings(value)
        if _is_dataflow_read_var(token)
    )


def _is_dataflow_read_var(token: str) -> bool:
    name = str(token or "").strip()
    if not name or name in _READ_STOP_WORDS:
        return False
    if name.endswith(".") or "<" in name or ">" in name:
        return False
    # Shallow parser reads may contain operators/types/modules such as
    # dBlock, Block., or P.f.  Equality skeletons should only synthesize
    # local-looking reads; explicit module/global relations still come from
    # the postcondition where their side annotations or ={...} shape are typed
    # proof facts rather than guessed code reads.
    if any(ch.isupper() for ch in name):
        return False
    if "." in name:
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_']*$", name))


__all__ = [
    "DATAFLOW_INVARIANT_KIND",
    "DATAFLOW_INVARIANT_SCHEMA_VERSION",
    "build_invariant_skeleton",
]
