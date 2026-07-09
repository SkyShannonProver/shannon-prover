"""Concrete-global touched frame for `call (_: ={...})` (the mechanical frame).

The agent's #1 time sink at a nested-functor call frontier is reconstructing, by
hand, the `={Module.field, ...}` frame of concrete global state the oracles
touch — e.g. for step4_badi:

    ={UFCMA_l.lbad1, UFCMA.cbad1, Mem.lc, BNR.lenc, BNR.ndec, RO.m, ROout.m, ROF.m}

`ec_call_glob_invariant` only emits `={glob <abstract module>}`; the concrete
field union over the (clone/functor-instantiated) call tree was never built.

This module is the PURE extraction core: given the FLATTENED oracle program
(what EC shows after a speculative `inline*` of an oracle obligation — the
speculative probe that produces it lives in ReplSessionManager), pull the
`Module.field` state it touches on each side and intersect to the shared `={...}`
frame. It is mechanical (type-matching), never semantic — it states which globals
are in the frame, not what the invariant should say about them.
"""
from __future__ import annotations

import re

# A module-qualified field as EC prints it: ``RO.m`` / ``UFCMA_l.lbad1`` /
# ``SplitC2.I2.RO.m`` — Capital head, one+ ``.segment``, optional ``{1}``/``{2}``.
_QUAL_FIELD = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)\s*(?:\{\s*[12]\s*\})?"
)
def _strip_side(tok: str) -> str:
    return re.sub(r"\s*\{\s*[12]\s*\}\s*$", "", tok).strip()


# --- Static write-map (source-scan, no speculative probe) -------------------
#
# The agent's single biggest time sink (step4_badi turn 8, ~145s of a 412s turn;
# turn 11) is head-simulating "who writes Mem.lc / does UFCMA_li write
# UFCMA_l.lbad1 / what state does set_bad1i touch". That is mechanical and static:
# scan each module BODY for writes. The earlier probe-based frame failed at a
# nested-abstract-adversary frontier (`call (_: true)` does not apply); this needs
# no probe — it reads the source directly.
#
# Two write forms appear:
#   * qualified   `UFCMA_l.lbad1 <- ...`, `Mem.k <@ ...`  -> field is explicit.
#   * bare own-var `lbad1 <- []`, `badi <- ...`           -> resolve via the
#     declaring module's `var` table; skip if shadowed by a proc-local.
# Fields written only inside cloned theories (e.g. `Mem.lc`) are NOT in any scanned
# body; we report them as "not written here" — itself the useful answer (the
# oracle does not touch it, so `={Mem.lc}` is preserved trivially).

_MODULE_HEAD = re.compile(r"\b(?:local\s+)?module\s+([A-Z][A-Za-z0-9_]*)\b")
_PROC_HEAD = re.compile(r"\bproc\s+([A-Za-z_][\w']*)\s*\(")
# A module-state `var` (depth-0, TYPED): `var lenc : nonce list` / `var a, b : T`.
_STATE_VAR = re.compile(r"\bvar\s+([A-Za-z_][\w',\s]*?)\s*:")
# Any `var` decl (state or proc-local), names up to `:` or `;`.
_ANY_VAR = re.compile(r"\bvar\s+([A-Za-z_][\w',\s]*?)\s*[:;]")
# Write LHS at a statement boundary: `<name> <- / <$ / <@`, where `<name>` is a
# qualified `Mod.field` or a bare own-var, with an optional fmap-index suffix
# (`UFCMA.log.[n] <- v` mutates `UFCMA.log`).
_WRITE_LHS = re.compile(
    r"(?:^|[;{}])\s*"
    r"([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][\w']*)+|[a-z_][\w']*)"  # name (qualified/bare)
    r"(?:\s*\.?\[[^\]]*\])?"                                     # optional `.[k]` map index
    r"\s*<[-$@]",
    re.MULTILINE,
)


def _match_brace_body(text: str, open_idx: int) -> "tuple[str, int]":
    """Given the index of a `{`, return (body_without_braces, index_after_close)."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
        i += 1
    return text[open_idx + 1 :], n


def _module_bodies(text: str) -> "list[tuple[str, str]]":
    """`(module_name, body)` for each brace-bodied module (skips alias `module X = Y.`)."""
    out: "list[tuple[str, str]]" = []
    for m in _MODULE_HEAD.finditer(text):
        name = m.group(1)
        # find the `=` then the first `{` that opens the body, but stop at `.`/`;`
        rest = text[m.end():]
        eq = rest.find("=")
        if eq < 0:
            continue
        brace = rest.find("{", eq)
        semi = rest.find(".", eq)
        if brace < 0 or (0 <= semi < brace):
            continue  # alias form `module X = Y.` — no body
        open_idx = m.end() + brace
        body, _ = _match_brace_body(text, open_idx)
        out.append((name, body))
    return out


def _names(blob: str) -> "list[str]":
    return [t.strip() for t in str(blob or "").split(",") if t.strip()]


def _state_vars_at_depth0(body: str) -> "set[str]":
    """Module-state var names: TYPED `var` decls at body brace-depth 0 only."""
    out: "set[str]" = set()
    depth = 0
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "{":
            depth += 1
            i += 1
            continue
        if c == "}":
            depth -= 1
            i += 1
            continue
        if depth == 0 and body.startswith("var", i) and (i == 0 or not body[i - 1].isalnum()):
            m = _STATE_VAR.match(body, i)
            if m:
                out.update(_names(m.group(1)))
        i += 1
    return out


def _proc_local_names(proc_body: str) -> "set[str]":
    """Local var names declared at the proc body's depth 0 (shadow module state)."""
    out: "set[str]" = set()
    depth = 0
    i = 0
    n = len(proc_body)
    while i < n:
        c = proc_body[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0 and proc_body.startswith("var", i) and (
            i == 0 or not proc_body[i - 1].isalnum()
        ):
            m = _ANY_VAR.match(proc_body, i)
            if m:
                out.update(_names(m.group(1)))
        i += 1
    return out


def _proc_bodies(module_body: str) -> "list[str]":
    out: "list[str]" = []
    for m in _PROC_HEAD.finditer(module_body):
        brace = module_body.find("{", m.end())
        if brace < 0:
            continue
        body, _ = _match_brace_body(module_body, brace)
        out.append(body)
    return out


def module_write_map(source_texts: "Iterable[Any]") -> "dict[str, Any]":
    """Static `field -> {writer modules}` / `module -> {written fields}` from source.

    Pure source scan — no speculative probe, robust at nested-functor frontiers.
    Handles qualified writes and bare own-var writes (resolved via the declaring
    module's state-var table, skipping proc-local shadows). Returns
    ``{by_field, by_module, owners}`` (each value sorted) — mechanical, no semantics.
    """
    mods: "list[tuple[str, str]]" = []
    for item in source_texts:
        text = item[0] if isinstance(item, (list, tuple)) and item else str(item)
        mods.extend(_module_bodies(str(text)))
    # state-var owner table (name -> declaring modules)
    state_of: "dict[str, set[str]]" = {}
    owners: "dict[str, set[str]]" = {}
    for name, body in mods:
        sv = _state_vars_at_depth0(body)
        state_of[name] = sv
        for v in sv:
            owners.setdefault(v, set()).add(name)
    by_field: "dict[str, set[str]]" = {}
    by_module: "dict[str, set[str]]" = {}
    for name, body in mods:
        own_state = state_of.get(name, set())
        for pbody in _proc_bodies(body):
            locals_ = _proc_local_names(pbody)
            for w in _WRITE_LHS.finditer(pbody):
                lhs = w.group(1)
                if "." in lhs:  # qualified -> a global, take as-is
                    field = lhs
                elif lhs in locals_:  # proc-local shadow -> not a global
                    continue
                elif lhs in own_state:  # this module's own state var
                    field = f"{name}.{lhs}"
                elif lhs in owners and len(owners[lhs]) == 1:  # uniquely-owned state
                    field = f"{next(iter(owners[lhs]))}.{lhs}"
                else:
                    continue  # unknown bare token -> skip (likely an unseen local)
                by_field.setdefault(field, set()).add(name)
                by_module.setdefault(name, set()).add(field)
    return {
        "by_field": {k: sorted(v) for k, v in sorted(by_field.items())},
        "by_module": {k: sorted(v) for k, v in sorted(by_module.items())},
        "owners": {k: sorted(v) for k, v in sorted(owners.items())},
    }


def write_map_for_goal(
    source_texts: "Iterable[Any]",
    *,
    field_universe: "Iterable[str]",
    focus_modules: "Iterable[str] | None" = None,
) -> "dict[str, Any]":
    """Goal-relevant slice of the write-map: for each frame-candidate field, who
    writes it; plus the write-sets of the divergent (focus) modules.

    ``field_universe`` = the candidate frame fields (from ``state_field_pool`` /
    the goal). ``focus_modules`` = the divergent oracle modules (from oracle_diff).
    Surfaces the mechanical answer to "who writes X", so the agent stops simulating
    it. Returns ``{}`` if nothing resolves.
    """
    wm = module_write_map(source_texts)
    by_field = wm["by_field"]
    by_module = wm["by_module"]
    universe = [_strip_side(f) for f in (field_universe or [])]
    rows: "list[dict[str, Any]]" = []
    for f in sorted(set(universe)):
        if "." not in f:
            continue
        # state fields are lowercase-headed (`UFCMA_l.lbad1`); a qualified name
        # whose last segment is Uppercase is a sub-MODULE ref (`UFCMA_l.O`), not
        # state — drop it so the panel does not mislabel it "clone-owned field".
        if f.rsplit(".", 1)[-1][:1].isupper():
            continue
        writers = by_field.get(f, [])
        rows.append({
            "field": f,
            "written_by": writers,
            "status": ("read-only here (clone-owned / preserved → safe `={%s}`)" % f)
            if not writers else "mutated",
        })
    focus = [m for m in (focus_modules or []) if m in by_module]
    focus_rows = [{"module": m, "writes": by_module[m]} for m in focus]
    if not rows and not focus_rows:
        return {}
    return {
        "fields": rows,
        "divergent_module_writes": focus_rows,
        "note": (
            "Mechanical write-map (static source scan, no probe). `written_by` is "
            "every module body that mutates the field. A field with NO writer here "
            "is preserved by the call (clone-owned / read-only) → `={field}` holds "
            "trivially. Fields a divergent module writes are where the coupling "
            "lives. This is the frame skeleton — DON'T re-derive it in your head."
        ),
    }
