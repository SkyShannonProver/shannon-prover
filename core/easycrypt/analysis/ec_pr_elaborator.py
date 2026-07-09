"""Typed elaboration for EasyCrypt probability rewrite candidates.

This pass sits between name/type binding and the prover-facing action menu.
Its job is deliberately small: separate the concrete procedure endpoint inside
``Pr[...]`` from the value arguments used to instantiate a probability lemma.

Example:

* concrete endpoint: ``MainD(G2, FinRO).distinguish()``
* lemma template: ``MainD(D, FinRO).distinguish(x)``
* lemma value binding: ``x : unit := ()``

The elaborator records that ``()`` belongs to the lemma instantiation, not to
the concrete procedure endpoint.  This prevents the agent from inventing
``distinguish(())`` when the current EasyCrypt endpoint is no-arg syntax.
"""
from __future__ import annotations

from typing import Any

from core.easycrypt.analysis.ec_utils import as_dict as _dict, as_list as _list
from core.easycrypt.analysis.ec_pr_canonical import (
    application_root,
    compact_pr_term,
    endpoint_templates_compatible,
    endpoint_with_inserted_arg,
    event_mentions_name,
    module_application_args as _module_application_args,
    parse_pr_terms,
)


PR_ELABORATOR_SCHEMA_VERSION = 1
PR_ELABORATOR_KIND = "easycrypt_pr_elaboration"


def build_pr_elaboration(
    *,
    lemma_name: str,
    handle_kind: str,
    declaration: str,
    goal_texts: list[str],
    slot_bindings: list[dict[str, Any]],
    instantiated_templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a typed Pr elaboration record for a resolved lemma candidate."""
    if str(handle_kind or "") not in {"pr_rewrite", "have_chain"}:
        return {}
    decl_terms = parse_pr_terms(declaration)
    goal_terms = [
        term
        for text in goal_texts
        for term in parse_pr_terms(text)
    ]
    if not decl_terms or not goal_terms:
        return {}

    module_slot_names = _module_slot_names_from_bindings(slot_bindings)
    slot_rows = [
        _slot_row(
            binding,
            decl_terms=decl_terms,
            goal_terms=goal_terms,
            module_slot_names=module_slot_names,
        )
        for binding in slot_bindings
        if isinstance(binding, dict)
    ]
    endpoint_matches = _endpoint_matches(
        decl_terms,
        goal_terms,
        module_slot_names=module_slot_names,
    )
    separated = _endpoint_argument_separation(
        slot_rows,
        decl_terms=decl_terms,
        goal_terms=goal_terms,
        module_slot_names=module_slot_names,
    )
    diagnostics = _diagnostics(separated)
    if not endpoint_matches:
        diagnostics.append({
            "code": "pr_elaboration.no_matching_pr_endpoint",
            "severity": "warning",
            "message": (
                "The current Pr endpoint does not match this lemma's endpoint "
                "template. Build an intermediate Pr equality/wrapper bridge "
                "before probing the rewrite."
            ),
            "lemma_endpoint_templates": [
                str(_dict(term.get("endpoint")).get("canonical") or "")
                for term in decl_terms[:4]
            ],
            "current_endpoints": [
                str(_dict(term.get("endpoint")).get("canonical") or "")
                for term in goal_terms[:4]
            ],
        })
    return {
        "schema_version": PR_ELABORATOR_SCHEMA_VERSION,
        "kind": PR_ELABORATOR_KIND,
        "lemma": str(lemma_name or ""),
        "status": "elaborated",
        "goal_terms": [compact_pr_term(term) for term in goal_terms[:6]],
        "lemma_terms": [compact_pr_term(term) for term in decl_terms[:6]],
        "slots": slot_rows,
        "endpoint_matches": endpoint_matches,
        "endpoint_argument_separation": separated,
        "diagnostics": diagnostics,
        "runnable_tactics": [
            str(item.get("tactic") or "")
            for item in (instantiated_templates or [])[:3]
            if isinstance(item, dict) and str(item.get("tactic") or "")
        ],
    }


def _slot_row(
    binding: dict[str, Any],
    *,
    decl_terms: list[dict[str, Any]],
    goal_terms: list[dict[str, Any]],
    module_slot_names: set[str],
) -> dict[str, Any]:
    slot = _dict(binding.get("slot"))
    selected = _dict(binding.get("selected_candidate"))
    kind = str(slot.get("kind") or "")
    name = str(slot.get("name") or "")
    value = str(selected.get("value") or slot.get("placeholder") or "")
    role = _slot_role(kind, name, decl_terms)
    row = {
        "slot": {
            "kind": kind,
            "name": name,
            "type_or_bound": str(slot.get("type_or_bound") or ""),
            "placeholder": str(slot.get("placeholder") or ""),
        },
        "selected_value": value,
        "role": role,
        "belongs_to": _slot_belongs_to(role),
        "evidence": str(selected.get("reason") or ""),
        "source": str(selected.get("source") or ""),
        "confidence": str(selected.get("confidence") or ""),
    }
    canonical = _canonical_goal_endpoint_for_slot(
        name,
        decl_terms,
        goal_terms,
        module_slot_names=module_slot_names,
    )
    if canonical:
        row["canonical_endpoint"] = canonical
    return row


def _slot_role(kind: str, name: str, decl_terms: list[dict[str, Any]]) -> str:
    if kind == "proof_arg":
        return "proof_argument"
    if kind == "module_arg":
        return "module_template_argument"
    if kind == "memory_arg":
        return "memory_argument"
    if kind != "value_arg":
        return kind or "unknown_argument"
    if not name:
        return "value_argument"
    for term in decl_terms:
        endpoint = _dict(term.get("endpoint"))
        if name in _list(endpoint.get("procedure_args")):
            return "lemma_endpoint_value_argument"
        if event_mentions_name(str(term.get("event") or ""), name):
            return "event_predicate_argument"
    return "value_argument"


def _slot_belongs_to(role: str) -> str:
    if role == "lemma_endpoint_value_argument":
        return "lemma_instantiation_not_concrete_procedure_call"
    if role == "event_predicate_argument":
        return "lemma_event_predicate"
    if role == "memory_argument":
        return "probability_memory"
    if role == "module_template_argument":
        return "module_template_instantiation"
    if role == "proof_argument":
        return "lemma_premise"
    return "lemma_instantiation"


def _endpoint_argument_separation(
    slot_rows: list[dict[str, Any]],
    *,
    decl_terms: list[dict[str, Any]],
    goal_terms: list[dict[str, Any]],
    module_slot_names: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    value_rows = [
        row for row in slot_rows
        if row.get("role") == "lemma_endpoint_value_argument"
    ]
    for row in value_rows:
        name = str(_dict(row.get("slot")).get("name") or "")
        if not name:
            continue
        for decl in decl_terms:
            decl_endpoint = _dict(decl.get("endpoint"))
            if name not in _list(decl_endpoint.get("procedure_args")):
                continue
            for goal in goal_terms:
                goal_endpoint = _dict(goal.get("endpoint"))
                if not _endpoints_compatible_for_slots(
                    decl_endpoint,
                    goal_endpoint,
                    module_slot_names=module_slot_names,
                ):
                    continue
                if _list(goal_endpoint.get("procedure_args")):
                    continue
                out.append({
                    "value_slot": name,
                    "selected_value": str(row.get("selected_value") or ""),
                    "lemma_endpoint_template": str(decl_endpoint.get("canonical") or ""),
                    "concrete_endpoint": str(goal_endpoint.get("canonical") or ""),
                    "concrete_procedure_args": [],
                    "reason": (
                        f"value slot `{name}` instantiates the lemma endpoint "
                        "template, while the concrete Pr endpoint has no "
                        "procedure arguments"
                    ),
                })
    return _dedupe_separations(out)


def _module_slot_names_from_bindings(slot_bindings: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for binding in slot_bindings:
        slot = _dict(_dict(binding).get("slot"))
        if str(slot.get("kind") or "") != "module_arg":
            continue
        name = str(slot.get("name") or "")
        if name:
            out.add(name)
    return out


def _endpoint_matches(
    decl_terms: list[dict[str, Any]],
    goal_terms: list[dict[str, Any]],
    *,
    module_slot_names: set[str],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for decl in decl_terms:
        decl_endpoint = _dict(decl.get("endpoint"))
        for goal in goal_terms:
            goal_endpoint = _dict(goal.get("endpoint"))
            if not _endpoints_compatible_for_slots(
                decl_endpoint,
                goal_endpoint,
                module_slot_names=module_slot_names,
            ):
                continue
            out.append({
                "lemma_endpoint": str(decl_endpoint.get("canonical") or ""),
                "current_endpoint": str(goal_endpoint.get("canonical") or ""),
            })
    return out


def _endpoints_compatible_for_slots(
    decl_endpoint: dict[str, Any],
    goal_endpoint: dict[str, Any],
    *,
    module_slot_names: set[str],
) -> bool:
    if not endpoint_templates_compatible(decl_endpoint, goal_endpoint):
        return False
    decl_args = _module_application_args(str(decl_endpoint.get("module_expr") or ""))
    goal_args = _module_application_args(str(goal_endpoint.get("module_expr") or ""))
    if not decl_args or not goal_args or len(decl_args) != len(goal_args):
        return True
    for decl_arg, goal_arg in zip(decl_args, goal_args):
        if _is_module_slot_arg(decl_arg, module_slot_names):
            continue
        if not _fixed_module_arg_matches(decl_arg, goal_arg):
            return False
    return True


def _is_module_slot_arg(arg: str, module_slot_names: set[str]) -> bool:
    root = application_root(str(arg or "").strip())
    return bool(root and root in module_slot_names)


def _fixed_module_arg_matches(left: str, right: str) -> bool:
    lnorm = _compact_arg(left)
    rnorm = _compact_arg(right)
    if lnorm == rnorm:
        return True
    lroot = application_root(lnorm) or lnorm
    rroot = application_root(rnorm) or rnorm
    return bool(lroot and rroot and lroot.rsplit(".", 1)[-1] == rroot.rsplit(".", 1)[-1])


def _compact_arg(value: str) -> str:
    return "".join(str(value or "").split())


def _canonical_goal_endpoint_for_slot(
    name: str,
    decl_terms: list[dict[str, Any]],
    goal_terms: list[dict[str, Any]],
    *,
    module_slot_names: set[str],
) -> str:
    if not name:
        return ""
    for decl in decl_terms:
        decl_endpoint = _dict(decl.get("endpoint"))
        if name not in _list(decl_endpoint.get("procedure_args")):
            continue
        for goal in goal_terms:
            goal_endpoint = _dict(goal.get("endpoint"))
            if _endpoints_compatible_for_slots(
                decl_endpoint,
                goal_endpoint,
                module_slot_names=module_slot_names,
            ):
                return str(goal_endpoint.get("canonical") or "")
    return ""


def _diagnostics(separated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in separated:
        value_slot = str(item.get("value_slot") or "")
        value = str(item.get("selected_value") or "")
        endpoint = str(item.get("concrete_endpoint") or "")
        if not value_slot or not endpoint:
            continue
        out.append({
            "code": "pr_elaboration.value_arg_not_proc_arg",
            "severity": "info",
            "message": (
                f"`{value_slot}` is bound as lemma argument `{value}`; keep "
                f"the concrete Pr endpoint as `{endpoint}`."
            ),
            "avoid": endpoint_with_inserted_arg(endpoint, value),
        })
    return out


def _dedupe_separations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("value_slot") or ""),
            str(item.get("selected_value") or ""),
            str(item.get("concrete_endpoint") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


__all__ = [
    "PR_ELABORATOR_KIND",
    "PR_ELABORATOR_SCHEMA_VERSION",
    "build_pr_elaboration",
]
