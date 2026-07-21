"""Relational-invariant skeleton: discover named coupling predicates and the
state-field footprint, so the compiler can hand the agent a *field-correct*
``call (_: <pred> <fields>)`` carrier — not only the ``={glob ...}`` frame.

This is the second rung of the call-invariant scaffold (the first, the glob
frame, lives in ``ec_call_glob_invariant``). Per the framework principle:

  * Mechanical (this module): which named predicates are in scope, their typed
    signatures, the ``{1}``/``{2}`` side pattern (read off the parameter names —
    ``x1``/``x2`` is a relational pair, a lone ``x1`` is single-side), the
    in-scope mutable state fields, and the type-matched instantiation candidates.
  * Semantic (left to the agent, who can backtrack-and-adjust): which predicate
    is right, the extra side conditions, and how the invariant evolves.

Nothing is hard-coded — predicates, modules, and aliases are read from the
loaded session source. Candidate instantiations are *daemon-filtered* downstream
(``call (_: <inst>)`` must apply); "applies" is necessary, not sufficient, so the
carrier is surfaced as a revisable starting point, never a committed invariant.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    collapse_ws as _norm_ws,
    delimited_region as _delimited_region,
)

from core.easycrypt.analysis.ec_pr_bridge_frontend import _session_source_texts


def _relational_source_texts(session_dir: Any) -> "list[tuple[str, Any, str]]":
    """Source texts for footprint extraction: the session context/target plus
    the *sibling* ``.ec`` files in the same source dir.

    A shared state module like ``Mem`` is often defined in a ``require``d sibling
    (e.g. ``ske.ec``), not the target file, and ``session_context_files`` returns
    only ``context.ec`` + the target — so we additionally read the sibling ``.ec``
    files. Only directories of *existing* source paths are scanned, so synthetic
    (non-existent) test paths never trigger globbing.
    """
    texts = list(_session_source_texts(session_dir))
    seen: "set[Path]" = set()
    sib_dirs: "set[Path]" = set()
    for _t, p, _k in texts:
        try:
            pp = Path(p).resolve()
            seen.add(pp)
            if pp.suffix == ".ec" and pp.exists():
                sib_dirs.add(pp.parent)
        except Exception:
            continue
    for d in sorted(sib_dirs):
        try:
            for f in sorted(d.glob("*.ec")):
                rf = f.resolve()
                if rf in seen:
                    continue
                seen.add(rf)
                texts.append((f.read_text(encoding="utf-8", errors="replace"),
                              f, "sibling"))
        except Exception:
            continue
    return texts


RELATIONAL_INVARIANT_KIND = "relational_invariant_skeleton"

_PRED_DECL = re.compile(
    r"\b(?:local\s+)?(?P<kw>op|pred|abbrev)\s+(?P<name>[A-Za-z_][A-Za-z0-9_']*)")
# ``module M (args) = {`` — a state-bearing module definition.
# Matches a module head and captures its name across the forms in the corpus:
#   module M = {                         module M : Sig = {
#   module M(P : T) = {                  module M(P : T) : Sig = {   (functor + result sig)
#   module (M(P : T) : Sig) (Q : U) = {  (parenthesized functored name — reductions)
# The result-signature annotation (`: POracle`) is what older corpora omit and
# MLKEM-style functors carry; without it the body's `var`s never get scanned.
_MODULE_HEAD = re.compile(
    r"\b(?:local\s+)?module\s+\(?\s*"
    r"(?P<name>[A-Z][A-Za-z0-9_']*)"
    r"(?:\s*\([^{}]*?\))?"                                 # functor params
    r"(?:\s*:\s*[A-Za-z_][\w'.]*(?:\s*\([^{}]*?\))?)?"     # optional result signature
    r"(?:\s*\))?"                                          # close parenthesized functored name
    r"(?:\s*\([^{}]*?\))?"                                 # optional outer functor params
    r"\s*=\s*\{")
# ``var v : t`` inside a module body (type runs to end of line / ``;``).
_VAR_DECL = re.compile(r"\bvar\s+(?P<field>[a-z_][A-Za-z0-9_']*)\s*:\s*(?P<type>[^\n;}]+)")
# ``local module ROin = SplitC2.I1.RO.`` — a state alias (no body).
_MODULE_ALIAS = re.compile(
    r"\b(?:local\s+)?module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*=\s*"
    r"(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*\.")
_RELATIONAL_BODY = re.compile(r"/\\|\\in\b|\bforall\b|={")


def _header_body(text: str, start: int) -> "tuple[str | None, str]":
    """From just after a predicate name, return ``(param_header, body_chunk)``.

    ``param_header`` is the text up to the definition ``=`` (the parenthesized
    parameter groups + an optional ``: restype``); ``body_chunk`` is a short peek
    at the body for relational classification. Returns ``(None, "")`` if neither
    a top-level ``=`` (defined op) nor a clean declaration is found.
    """
    depth = 0
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "=" and depth == 0:
            prv = text[i - 1] if i else " "
            nxt = text[i + 1] if i + 1 < n else " "
            if nxt != "=" and prv not in "<>=!":
                return text[start:i], text[i + 1:i + 401]
        elif c == "." and depth == 0 and (i + 1 >= n or text[i + 1] in " \t\r\n"):
            return text[start:i], ""        # bare declaration, no body
        i += 1
    return None, ""


def _split_param_groups(header: str) -> "list[tuple[list[str], str]]":
    """Balanced ``(names : type)`` groups from a predicate parameter header."""
    out: "list[tuple[list[str], str]]" = []
    i, n = 0, len(header)
    while i < n:
        if header[i] == "(":
            depth, j = 1, i + 1
            while j < n and depth:
                depth += (header[j] == "(") - (header[j] == ")")
                j += 1
            inner = header[i + 1:j - 1]
            if ":" in inner:
                names_part, type_part = inner.split(":", 1)
                names = names_part.split()
                if names:
                    out.append((names, _norm_ws(type_part)))
            i = j
        else:
            i += 1
    return out


def _params_with_sides(groups: "list[tuple[list[str], str]]") -> "list[dict[str, Any]]":
    """Flatten groups to params and fold ``x1``/``x2`` siblings into pairs.

    A param ``x1`` immediately followed by ``x2`` of the same type is a
    relational pair ({1},{2}); anything else is a single side (the left/{1}
    reference side, like ``inv_cpa``'s lone ``mr1``/``ms1``).
    """
    flat: "list[tuple[str, str]]" = []
    for names, typ in groups:
        for nm in names:
            flat.append((nm, typ))
    out: "list[dict[str, Any]]" = []
    k = 0
    while k < len(flat):
        nm, typ = flat[k]
        if (k + 1 < len(flat) and nm.endswith("1")
                and flat[k + 1][0] == nm[:-1] + "2" and flat[k + 1][1] == typ):
            out.append({"kind": "pair", "base": nm[:-1], "type": typ,
                        "names": [nm, flat[k + 1][0]]})
            k += 2
        else:
            out.append({"kind": "single", "base": nm, "type": typ, "names": [nm]})
            k += 1
    return out


def relational_predicates(session_dir: Any) -> "list[dict[str, Any]]":
    """Named coupling predicates in scope (``op``/``pred``/``abbrev`` that look
    relational), de-duplicated by name, with typed + side-paired parameters."""
    out: "dict[str, dict[str, Any]]" = {}
    order: list[str] = []
    for text, _path, _kind in _relational_source_texts(session_dir):
        for m in _PRED_DECL.finditer(text):
            name = m.group("name")
            if name in out:
                continue
            header, body = _header_body(text, m.end())
            if not header:
                continue
            params = _params_with_sides(_split_param_groups(header))
            has_pair = any(p["kind"] == "pair" for p in params)
            if not (has_pair or (len(params) >= 2 and _RELATIONAL_BODY.search(body))):
                continue
            order.append(name)
            out[name] = {
                "name": name,
                "params": params,
                "arity": sum(len(p["names"]) for p in params),
                "body_preview": _norm_ws(body)[:160],
            }
    return [out[n] for n in order]


def state_field_pool(session_dir: Any) -> "dict[str, Any]":
    """The mutable state footprint: ``Module.field : type`` from module ``var``
    declarations, plus ``local module A = B`` aliases (so ``A.field`` resolves to
    ``B.field`` for the agent / the daemon-filtered instantiator)."""
    fields: "dict[str, dict[str, str]]" = {}
    aliases: "dict[str, str]" = {}
    for text, _path, _kind in _relational_source_texts(session_dir):
        for m in _MODULE_HEAD.finditer(text):
            modname = m.group("name")
            body = _delimited_region(text, m.end() - 1, "{", "}")
            for vm in _VAR_DECL.finditer(body):
                q = f"{modname}.{vm.group('field')}"
                fields.setdefault(q, {
                    "qualified": q, "module": modname,
                    "field": vm.group("field"), "type": _norm_ws(vm.group("type")),
                })
        for am in _MODULE_ALIAS.finditer(text):
            aliases.setdefault(am.group("name"), am.group("target"))
    return {"fields": list(fields.values()), "aliases": aliases}


def ro_map_fields(pool: "dict[str, Any]") -> "list[str]":
    """``<alias>.m`` candidates for the un-var-declared RO/PROM map slots — the
    ``fmap`` parameters (like ``inv_cpa``'s ``mr1``/``ms1``) that don't match any
    module ``var`` because the map lives in a clone instance. Source typing of an
    RO instance is unavailable, so these fill ``fmap`` slots as a typed MENU; which
    one is poly_in vs poly_out is the agent's semantic pick (it reads the slot type
    and the RO aliases — a trivial read, not worth a daemon probe per candidate)."""
    out: list[str] = []
    for alias, target in (pool.get("aliases") or {}).items():
        if "RO" in alias or "RO" in str(target):
            out.append(f"{alias}.m")
    return out


def _field_candidates(param_type: str, fields: "list[dict[str, str]]",
                      ro_maps: "list[str]") -> "list[str]":
    pt = _norm_ws(param_type)
    exact = [f["qualified"] for f in fields if _norm_ws(f["type"]) == pt]
    if exact:
        return exact
    if pt.endswith("fmap"):            # un-var-declared map slot → RO instances
        return list(ro_maps)
    cons = pt.split()[-1] if pt else ""   # coarse fallback by type constructor
    return [f["qualified"] for f in fields
            if _norm_ws(f["type"]).split()[-1:] == [cons]]


def slot_field_options(pred: "dict[str, Any]",
                       pool: "dict[str, Any]") -> "list[tuple[dict[str, Any], list[str]]]":
    """Per-slot type-correct field candidates — *pure* type matching, no
    relevance heuristic. Each entry is ``(param, [field, ...])``: every field
    whose type matches that slot's type (exact, with the RO-alias ``.m`` fallback
    for un-var-declared map slots). Returns ``[]`` if any slot is unfillable."""
    fields = pool.get("fields") or []
    ro_maps = ro_map_fields(pool)
    slots: "list[tuple[dict[str, Any], list[str]]]" = []
    for p in pred.get("params") or []:
        cands = _field_candidates(p.get("type", ""), fields, ro_maps)
        if not cands:
            return []
        slots.append((p, cands))
    return slots


def _render_call(pred_name: str,
                 picks: "list[tuple[dict[str, Any], str]]") -> str:
    args: list[str] = []
    for p, field in picks:
        if p.get("kind") == "pair":
            args.append(f"{field}{{1}} {field}{{2}}")
        else:
            args.append(f"{field}{{1}}")
    return f"call (_: {pred_name} " + " ".join(args) + ")."


def instantiate_predicate(pred: "dict[str, Any]", pool: "dict[str, Any]",
                          *, max_candidates: int = 24) -> "list[str]":
    """All type-matched ``call (_: <pred> <fields>)`` candidates (bounded
    Cartesian over the per-slot options). Pure type matching — no relevance
    narrowing; the daemon resolves which actually type-check downstream."""
    import itertools
    slots = slot_field_options(pred, pool)
    if not slots:
        return []
    out: list[str] = []
    names = [p for p, _ in slots]
    for combo in itertools.product(*[c for _, c in slots]):
        out.append(_render_call(pred["name"], list(zip(names, combo))))
        if len(out) >= max_candidates:
            break
    return out


# ── scope resolution: read the goal EC already printed, don't probe ───────────

_GOAL_SYM = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)\b")


def goal_scope_symbols(goal_text: str) -> "set[str]":
    """The ``Module.field`` symbols actually in scope at the current goal, parsed
    from the goal text EC already printed (its memory / program listing). A field
    NOT here is out of scope — EC would reject it as ``unknown variable``. This is
    scope resolution by *reading the goal*, not by daemon-probing each candidate:
    the answer is already on the goal head, so we never spend a probe to learn it.
    """
    return set(_GOAL_SYM.findall(goal_text or ""))


def _resolve_alias(field: str, aliases: "dict[str, str]") -> str:
    """``ROin.m`` -> ``SplitC2.I1.RO.m`` when ``ROin`` aliases ``SplitC2.I1.RO``
    (the goal prints the resolved form, the source/menu uses the friendly alias)."""
    mod, _dot, rest = field.partition(".")
    target = aliases.get(mod)
    return f"{target}.{rest}" if target and rest else field


def _in_scope(field: str, scope: "set[str]", aliases: "dict[str, str]") -> bool:
    # No goal text -> cannot scope-filter; fall back to type-only (keep).
    if not scope:
        return True
    return field in scope or _resolve_alias(field, aliases) in scope


def _example_pick(param: "dict[str, Any]", fields: "list[str]") -> str:
    """Best-effort *illustrative* pick among equally-typed fields: the field whose
    name overlaps the param's type tokens (a ``poly_in`` slot leans to an
    ``...in...`` map, ``poly_out`` to ``...out...``). Illustrative ONLY — the menu
    keeps every option; the real semantic pick is the agent's."""
    if len(fields) == 1:
        return fields[0]
    toks = [t for t in re.findall(r"[a-z]+", str(param.get("type", "")).lower())
            if len(t) >= 2]
    best, best_score = fields[0], -1
    for f in fields:
        fl = f.lower()
        score = sum(1 for t in toks if t in fl)
        if score > best_score:
            best, best_score = f, score
    return best


def typed_field_resolution(
    pred: "dict[str, Any]", pool: "dict[str, Any]", goal_text: str = "",
    *, verify: Any = None,
) -> "Optional[dict[str, Any]]":
    """STATIC field resolution — type matching (source) + scope resolution (goal),
    *no enumeration probing*. For each predicate slot:

      * candidates are the type-correct fields (``slot_field_options``), then
        filtered to those IN SCOPE at the current goal (``goal_scope_symbols``,
        alias-resolved) — an out-of-scope field is dropped WITHOUT a daemon probe,
        because EC already told us, in the goal text, that it is not live here;
      * a slot left with ONE in-scope field is filled; SEVERAL -> a typed MENU
        (the semantic pick, e.g. ``poly_in`` vs ``poly_out`` RO map, is the
        agent's, never the compiler's);
      * a slot with ZERO in-scope fields means the predicate does not apply at
        this goal -> ``None``.

    Types come from the source field pool, scope from the goal text — both static,
    so the cost no longer grows with the number of candidate fields (the old
    enumerate-and-probe was O(candidates) daemon round-trips). ``verify(tactic) ->
    bool``, if given, is called AT MOST ONCE on the assembled witness to confirm it
    applies on the live goal; otherwise the natural commit-time type-check
    verifies it. Returns ``{name, menus, template, fully_determined, witness,
    preflight_count}`` (``menus[i] = {param, fields, filled}``).
    """
    slots = slot_field_options(pred, pool)
    if not slots:
        return None
    scope = goal_scope_symbols(goal_text)
    aliases = pool.get("aliases") or {}
    names = [p for p, _ in slots]
    menus: "list[dict[str, Any]]" = []
    for p, cands in slots:
        in_scope = [c for c in cands if _in_scope(c, scope, aliases)]
        if not in_scope:
            return None     # a slot has no in-scope field -> predicate not live here
        menus.append({"param": p, "fields": in_scope,
                      "filled": len(in_scope) == 1})

    template = render_template(pred["name"], menus)
    fully = all(m["filled"] for m in menus)
    witness = _render_call(
        pred["name"],
        [(m["param"], _example_pick(m["param"], m["fields"])) for m in menus],
    )
    res: "dict[str, Any]" = {
        "name": pred["name"],
        "menus": menus,
        "template": template,
        "fully_determined": fully,
        "witness": witness,
        "preflight_count": 0,
    }
    if verify is not None:
        try:
            res["verified_applies"] = bool(verify(witness))
            res["preflight_count"] = 1
        except Exception:
            res["verified_applies"] = None
    return res


def render_template(pred_name: str, menus: "list[dict[str, Any]]") -> str:
    """Type fill-in template: type-unique slots filled, type-ambiguous slots shown
    as inline menus ``‹a | b | …›`` for the agent to fill BY SEMANTICS — the
    compiler does not pre-pick a default among equally-typed fields. When every
    slot is type-unique the template is a complete, directly-committable carrier.
    """
    parts: list[str] = []
    for m in menus:
        p = m.get("param") or {}
        fields = m.get("fields") or []
        pair = p.get("kind") == "pair"
        if m.get("filled") and len(fields) == 1:
            f = fields[0]
            parts.append(f"{f}{{1}} {f}{{2}}" if pair else f"{f}{{1}}")
        else:
            menu = "‹" + " | ".join(fields) + "›"
            parts.append(f"{menu}{{1}} {menu}{{2}}" if pair else f"{menu}{{1}}")
    return f"call (_: {pred_name} " + " ".join(parts) + ")."


# ── inductive side-conditions: a call invariant over an RO-querying adversary ──

# An RO clone's domain map surfaces on the goal head as a path segment beginning
# with `RO` followed by `.m` (e.g. `<Path>.RO.m`, `<Path>.ROx.RO.m`). Structural
# — keys off the RO-instance naming convention, not any family's module names.
_RO_MAP_SEG = re.compile(r"(?:^|\.)RO\w*\.")
# A "used"/"tracked" set the game maintains is a `list`- or `fset`-typed module
# var (ChaChaPoly's `lenc : nonce list`, MLKEM's `queried : ... list`).
_USED_SET_TYPE = re.compile(r"\b(?:list|fset)\b")


def ro_domain_side_conditions(
    session_dir: Any, goal_text: str = "",
) -> "Optional[dict[str, Any]]":
    """Candidate inductive ``dom ⊆ used-set`` side-conditions to ADD to a named
    coupling call invariant — the conjuncts it usually still needs to be
    *inductive*, not merely type-correct.

    A ``call (_: <inv>)`` over an adversary that queries a random oracle with
    fresh keys is rarely inductive unless ``<inv>`` also constrains that oracle's
    DOMAIN to a tracked "used" set the game maintains. Two corpus families show
    the identical shape under different names::

        forall n c, (n,c) \\in <ro_map>{1} => n \\in <used_list>{1}
        perm_eq <used_list>{2} (elems (fdom <ro_map>{2}))

    So mine it STRUCTURALLY (never by name): the RO ``.m`` maps actually on the
    goal head (``RO``-prefixed clone segment + ``.m``) and the ``list``/``fset``-
    typed "used-set" module vars in scope here, then emit the domain-containment
    SHAPE. The RO↔set pairing, the key decomposition (the key may be a tuple —
    a *component* is what's tracked), the side (``{1}``/``{2}``), and which RO the
    base coupling already pins are the agent's SEMANTIC pick; the compiler points
    at the ingredients + the idiom, it asserts no specific conjunct. Returns
    ``{ro_maps, used_lists, shape}`` or ``None`` when an ingredient is absent.
    """
    scope = goal_scope_symbols(goal_text)
    if not scope:
        return None
    ro_maps = sorted({s for s in scope
                      if s.endswith(".m") and _RO_MAP_SEG.search(s)})
    try:
        pool = state_field_pool(session_dir)
    except Exception:
        pool = {"fields": [], "aliases": {}}
    aliases = pool.get("aliases") or {}
    used_lists = sorted({
        f["qualified"] for f in (pool.get("fields") or [])
        if _USED_SET_TYPE.search(_norm_ws(f.get("type", "")))
        and _in_scope(f["qualified"], scope, aliases)})
    if not ro_maps or not used_lists:
        return None
    listmenu = (used_lists[0] if len(used_lists) == 1
                else "‹" + " | ".join(used_lists) + "›")
    rohole = ro_maps[0] if len(ro_maps) == 1 else "<one of the RO maps below>"
    # `\in` carries a backslash, which a py3.9 f-string forbids — concatenate.
    shape = ("(forall k, k \\in " + rohole + "{1} => k \\in " + listmenu + "{1})")
    return {"ro_maps": ro_maps, "used_lists": used_lists, "shape": shape}


# ── lamp (b): invariant-shape vocabulary palette ─────────────────────────────
# Show the agent, from REAL in-scope examples, that an invariant conjunct can be
# a guarded implication / a size-or-count bound / a domain-membership fact — not
# just an equality. The vocabulary is taught by the development's own predicates,
# never by prompt prose. Possibility space only: buckets list a couple of example
# predicates and assert nothing about which to use.
_SHAPE_CLASSES = (
    ("guarded_implication", re.compile(r"=>")),
    ("size_or_count_bound", re.compile(r"\bsize\b|<=|>=")),
    ("domain_membership", re.compile(r"\\in\b|\bf?dom\b|\bmem\b")),
)


def _invariant_shape_classes(body: str) -> "list[str]":
    """Shape buckets a predicate body falls into (>=1; defaults to equality)."""
    classes = [name for name, rx in _SHAPE_CLASSES if rx.search(body or "")]
    return classes or ["relational_equality"]


def invariant_shape_palette(
    session_dir: Any, goal_text: str = "",
) -> "Optional[dict[str, Any]]":
    """The invariant-shape vocabulary in scope, grouped by form (lamp b).

    Scans the named coupling predicates in scope and buckets each by the SHAPE its
    body uses, so the agent sees from real examples that an invariant conjunct can
    take richer forms than an equality. Possibility space, not a recommendation:
    each bucket lists a couple of example predicates (goal-relevant ones first,
    flagged ``relevant``) and asserts nothing about which to use. Returns
    ``{classes, predicates_examined}`` or ``None`` when no predicate is in scope.
    """
    try:
        preds = relational_predicates(session_dir)
    except Exception:
        return None
    if not preds:
        return None
    goal_tails: "set[str]" = set()
    for s in (goal_scope_symbols(goal_text) if goal_text else set()):
        tail = s.split(".")[-1]
        if len(tail) >= 3:
            goal_tails.add(tail)
        if len(s) >= 3:
            goal_tails.add(s)
    buckets: "dict[str, list[dict[str, Any]]]" = {}
    for p in preds:
        body = str(p.get("body_preview") or "")
        item = {
            "name": p.get("name"),
            "shape": body,
            "relevant": any(t in body for t in goal_tails),
        }
        for cls in _invariant_shape_classes(body):
            buckets.setdefault(cls, []).append(item)
    palette: "dict[str, list[dict[str, Any]]]" = {}
    for cls, items in buckets.items():
        items.sort(key=lambda it: (not it["relevant"], str(it["name"])))
        palette[cls] = items[:3]
    return {"classes": palette, "predicates_examined": len(preds)}
