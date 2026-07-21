"""Pure-tail evidence analyzer."""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_obligation_ir import (
    build_proof_obligation_ir,
    local_order_chains,
    named_local_formulas,
    named_local_hypotheses,
    split_top_level_token,
    top_level_relation_parts,
)
from workflow.proof_management.common import coerce_string_list as _string_list
from workflow.proof_management.analyzers.common import (
    _dedupe_dicts,
    _dict,
    _drop_empty,
    _list,
    _preview,
)
from workflow.proof_management.frame_facts import view_goal_text
from workflow.proof_management.node_state import ProofNodeState


_EC_ATOM_RE = r"[A-Za-z_][A-Za-z0-9_.'`{}&]*(?:\.\`[0-9]+)?"


class PureTailAnalyzer:
    """Builds the `pure_tail_surface` L4 panel."""

    def analyze(
        self,
        *,
        state: ProofNodeState,
        view: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # The aggregate node state carries the target `.ec` `file_path`.  Only
        # local inductive-constructor analysis still needs the source here;
        # loaded conclusion matches come from the canonical lemma-index
        # projection in the workspace view.
        workspace_view = dict(view or {})
        return pure_tail_surface(workspace_view, source_path=getattr(state, "file_path", ""))


_GOAL_OP_STOPWORDS = frozenset({
    "fun", "forall", "exists", "let", "in", "if", "then", "else", "true", "false",
    "res", "glob", "with", "fst", "snd", "of", "to",
    "left", "right",  # EC relational `&1 (left )` / `&2 (right)` markers, never operators
})
# Membership / composition operators worth surfacing (lookup-able), excluding the
# trivial logical connectives (=, /\, \/, =>, +, -, *, <, <=) the agent never looks up.
_SALIENT_SYMBOLIC_OPS = (
    "\\notin", "\\in", "\\o", "\\subset", "\\cap", "\\cup", "%/", "%%",
)

# High-value LIST / membership operators that carry a dense, load-bearing lemma family
# (`filter`→`mem_filter`/`filter_*`, `mapP`/`has`→`List.hasP`/`List.mapP`, `undup`→`undup_uniq`).
# These are PLAIN named identifiers the tokeniser already finds — the defect is only that a goal
# nesting them deep inside a `map (…) (filter (…) L)` term pushes them PAST the `[:8]` operator
# cap (panel audit cc_step4_1 i94/i99: `filter` extracted at token index 9/11, dropped). When such
# an op IS literally in the conclusion it is PROMOTED ahead of the cap so its family is offered.
# Conservative: promotion only REORDERS operators already extracted from the goal — it never
# invents an operator that is not in the conclusion, so it cannot over-route.
_PRIORITY_LIST_OPS = ("filter", "mem_filter", "mapP", "hasP", "undup")

# EasyCrypt finite-map get/set is written in the SYMBOLIC notation `_.[_]` (get) and
# `_.[_ <- _]` (set/update), which the identifier-regex tokeniser above NEVER sees — so a
# goal whose load-bearing structure is a map get-of-set (`m.[k<-v].[k]`) used to surface
# only the cosmetic outer `oget`, routing the agent to `oget` lemmas instead of the
# `get_set_sameE`/`get_setE`/`mem_set` family that actually closes it (panel audit
# PRG.ec::Plog_Psample i13/i17/i19/i37/i39/i40). These synthetic `search` skeletons land on
# the right family. The exact strings were ground-truthed against EC `search` over FMap:
#   search (_.[_ <- _].[_]).  -> get-of-set family: get_set_sameE/neqE/eqE, get_setE
#   search "_.[_<-_]".        -> whole set family incl mem_set, get_setE, set_setE
# (the spaced bare-set skeleton `(_.[_ <- _])` and `(_ \in _.[_ <- _])` are REJECTED by EC
#  with "more than one operator matches"; the quoted notation is the reliable set route).
_FMAP_GET_OF_SET_SKELETON = "(_.[_ <- _].[_])"
_FMAP_SET_NOTATION = '"_.[_<-_]"'
# A map get-of-set: an update `.[ … <- … ]` immediately followed by a lookup `.[`.
_FMAP_GET_OF_SET_RE = re.compile(r"\.\[[^\]\n]*<-[^\]\n]*\]\s*\.\[")
# Any finite-map update/set `.[ … <- … ]`.
_FMAP_SET_RE = re.compile(r"\.\[[^\]\n]*<-")
# A lossless-distribution conclusion head (`islossless` / `weight d` / `mu d (fun _=>true)=1%r`)
# closes by a `*_ll` lemma (e.g. dout_ll), never by negBadE — so a standing hypothesis `Bad`
# must not be pulled onto it.
_LOSSLESS_CONCL_RE = re.compile(r"\bislossless\b|\bweight\b|\bmu\b\s+\S+\s+\(fun\b.*?\)\s*=\s*1%r")

# A local `inductive` PREDICATE used as a proof obligation (PRG.ec `inv`, `Bad`) is a
# DEAD-END `operator_lemmas` target — it has no rewrite-lemma family, so a `search` on its
# bare name returns nothing useful (`Bad` is recovered separately via its characterization
# lemma, see `_BAD_PREDICATE_RE`; the inductive's intro constructors are surfaced by
# `_inductive_intro_routes`). Such a head is dropped from the operator route — but ONLY when
# the source confirms it is declared `inductive`, never by hardcoded NAME: `inv` is also the
# field/group INVERSE operator (e.g. eval/examples/Pedersen.ec `inv (m' - m)`), a genuine
# lemma-bearing operator that must NOT be dropped. The confirmed-inductive names are computed
# per-target by `_local_inductive_predicate_names(source)` and threaded into `_goal_operators`.
_INDUCTIVE_DECL_RE = re.compile(r"\b(?:local\s+)?inductive\s+([A-Za-z_][A-Za-z0-9_']*)\b")


def _local_inductive_predicate_names(source: str) -> frozenset[str]:
    """Names declared `inductive <Name>` (optionally `local inductive`) in the target `.ec`.
    Empty when the source is unavailable — so when we cannot confirm a token is an inductive
    predicate we KEEP it (never over-drop a real operator)."""
    return frozenset(_INDUCTIVE_DECL_RE.findall(str(source or "")))
# `Bad` / `!Bad` as a proof obligation (in the conclusion OR the hypotheses): the agent
# needs the `Bad` characterization lemma family (PRG.ec `negBadE`), reachable by searching
# the predicate name `Bad` — NOT the `inv`/`oget` the conclusion tokeniser would surface.
_BAD_PREDICATE_RE = re.compile(r"(?<![A-Za-z0-9_'])!?\s*Bad\b")


def _conclusion_text(goal_text: str) -> str:
    """The goal CONCLUSION — text after the last `----` turnstile separator, with the
    EC emacs prompt marker (`[38|check]>`) stripped so it does not leak a spurious
    `check` operator into _goal_operators."""
    lines = str(goal_text or "").splitlines()
    sep = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) == {"-"} and len(stripped) >= 3:
            sep = i
    body = "\n".join(lines[sep + 1:]) if sep >= 0 else str(goal_text or "")
    return re.sub(r"\[\s*\d+\s*\|[^\]]*\]>", " ", body).strip()


def _bound_names(goal_text: str, conclusion: str) -> set[str]:
    names: set[str] = set()
    for line in str(goal_text or "").splitlines():
        m = re.match(r"\s*([A-Za-z_][\w']*)\s*:\s*\S", line)
        if m:
            names.add(m.group(1))  # context binding name (a variable, not an operator)
    for m in re.finditer(r"(?:fun|forall|exists)\s*\(?\s*([A-Za-z_][\w']*)", conclusion):
        names.add(m.group(1))      # binder-introduced variable in the conclusion
    # A binder GROUP binds EVERY space-separated name before its `:`
    # (`forall (result_L result_R : ptxt) (A_L A_R : (glob A)), …`). The regex above
    # captured only the FIRST name of the group adjacent to the keyword, so the 2nd+
    # var of a multi-name group — and every var in a later `(… : T)` group — leaked
    # into _goal_operators and was mislabeled an operator (panel re-audit FIX-4c:
    # cpa_ddh0 `result_R`/`A_R`, eq_Game1_Game2 `r_L`/`qs_L`/`m_L`/`b_L`).
    for grp in re.finditer(r"\(\s*([A-Za-z_][\w' ]*?)\s*:[^)]*\)", conclusion):
        names.update(grp.group(1).split())
    # `let x = …` / `let (a, b) = …` binders bind x / a, b — variables accessed as
    # `x.\`1` etc., NOT operators (re-audit verification follow-up: CramerShoup let-bound
    # `sk2` was surfaced as an operator).
    for m in re.finditer(r"\blet\s+\(?\s*([A-Za-z_][\w' ,]*?)\s*\)?\s*=", conclusion):
        for name in re.split(r"[\s,]+", m.group(1)):
            if name:
                names.add(name)
    # Memory / program-variable noise — NOT operators — that leaked into the "Goal operators"
    # list: `&hr`/`&m` memory labels, the `{hr}`/`{1}`/`{2}` memory annotations themselves, AND
    # the program VARIABLE carrying the annotation (`PIR.s` in `PIR.s{hr}`). A real operator is
    # never written with a `{mem}` suffix, so a token directly before `{…}` is a program var.
    # (Genuine searchable constants like `Top.N`/`zerow` have no `{…}` and survive.)
    for m in re.finditer(
        r"&([A-Za-z_][\w']*)|\{\s*([A-Za-z_][\w']*)\s*\}|([A-Za-z_][\w'.]*)\s*\{",
        goal_text,
    ):
        names.add(m.group(1) or m.group(2) or m.group(3))
    return names


def _type_names(goal_text: str, conclusion: str) -> set[str]:
    """Symbols appearing in TYPE position — the RHS of a binder/context annotation
    `x : T` (`int`, `bool`, `list`, `ptxt`, `rand`, `fmap`, `ZModE.exp`, `C.counter`,
    …). These are TYPES, not operators; the old extractor surfaced them under the
    "Goal operators" panel, which the re-audit confirmed as 误导 (FIX-4c), so
    _goal_operators drops them. Conclusion binder-group RHS and bare-type context
    lines only — a context line whose RHS is a PROPOSITION (a hypothesis) is left
    for _visible_hypotheses and never harvested as a type."""
    types: set[str] = set()

    def _harvest(rhs: str) -> None:
        for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", rhs):
            types.add(m.group(0))

    # Conclusion binder groups: the text between `:` and the group's closing paren.
    # Allow ONE level of nested parens in the type so a tuple/constructor type keeps
    # its outer head — `(m_L : (rand, ptxt) fmap)` must harvest `fmap`, not stop at the
    # inner `)` (panel re-audit FIX-4c: eq_Game1_Game2 leaked `fmap`).
    for grp in re.finditer(
        r"\(\s*[A-Za-z_][\w' ]*?:\s*((?:[^()]|\([^()]*\))*)\)", conclusion
    ):
        _harvest(grp.group(1))
    # Context type bindings `name : T` (skip propositional hypotheses).
    for line in str(goal_text or "").splitlines():
        s = line.strip()
        if s and set(s) == {"-"} and len(s) >= 3:
            break  # turnstile reached; the conclusion is below it
        m = re.match(r"[A-Za-z_][\w']*\s*:\s*(.+)$", s)
        if m and not any(
            op in m.group(1)
            for op in ("<=", "<", ">", "=", "\\in", "=>", "<>", "/\\", "\\/")
        ):
            _harvest(m.group(1))
    return types


def _hypotheses_text(goal_text: str) -> str:
    """The CONTEXT region above the `----` turnstile (named hypotheses / bindings).
    `_goal_operators` reads this to surface a `Bad`-in-hypotheses obligation that the
    conclusion alone does not show (PRG.ec `! Bad …` in H/H5 closed by `smt(negBadE)`)."""
    lines = str(goal_text or "").splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) == {"-"} and len(stripped) >= 3:
            return "\n".join(lines[:i])
    return ""  # no turnstile seen → no separable hypothesis region


def _goal_operators(
    goal_text: str,
    *,
    inductive_heads: "frozenset[str]" = frozenset(),
) -> list[str]:
    """The named OPERATOR symbols that ACTUALLY appear in the goal conclusion — a
    tokenisation FACT so the agent knows what it can `lookup_symbol`. Free operator
    identifiers only: bound variables, binders, logical keywords AND type names are
    dropped (a TYPE — `int`, `bool`, `ptxt`, `ZModE.exp`, … — is not an operator and
    listing it here was confirmed 误导 in the panel re-audit, FIX-4c). NOT ranked,
    NOT a recommendation, NOT a goal-shape classification.

    Two SYMBOLIC structures the identifier tokeniser cannot see are added as synthetic
    search routes (panel audit PRG.ec::Plog_Psample): EasyCrypt finite-map get/set
    (`m.[k<-v].[k]`, `m.[k<-v]`) → the get_set/mem_set lemma family, surfaced AHEAD of the
    cosmetic `oget` so the route lands on the family that actually closes the goal; and a
    `Bad`/`!Bad` proof obligation visible in the hypotheses or conclusion → the `Bad`
    characterization (`negBadE`). Dead-end local-predicate heads (`inv`) are dropped."""
    concl = _conclusion_text(goal_text)
    if not concl:
        return []
    bound = _bound_names(goal_text, concl)
    types = _type_names(goal_text, concl)
    ops: list[str] = []
    seen: set[str] = set()

    def _add(op: str) -> None:
        if op and op not in seen:
            seen.add(op)
            ops.append(op)

    # SYMBOLIC finite-map get/set comes FIRST so its lemma family (get_set_sameE/get_setE/
    # mem_set) is the route, not the cosmetic outer `oget` the conclusion tokeniser finds.
    # A get-of-set (`m.[k<-v].[k]`) is matched by the focused get_set skeleton; a plain
    # set/update (`m.[k<-v]`, e.g. a membership `r \in m.[k<-v]`) by the whole-set notation.
    if _FMAP_GET_OF_SET_RE.search(concl):
        _add(_FMAP_GET_OF_SET_SKELETON)
    if _FMAP_SET_RE.search(concl):
        _add(_FMAP_SET_NOTATION)
    # A `Bad`/`!Bad` obligation: route to the predicate's characterization (`negBadE`),
    # reachable by searching `Bad`. In the CONCLUSION it IS the obligation — always surface.
    # In the HYPOTHESES `! Bad …` is a STANDING hypothesis on nearly every frontier of an
    # up-to-bad proof, so surface it only as a FALLBACK — when the conclusion has no more-
    # specific load-bearing route. On a get-of-SET FMap equality (get_set_sameE), a SET /
    # membership (mem_set), or a lossless head (dout_ll), pulling hypothesis-`Bad` in
    # mis-routes the close toward negBadE (panel re-audit over-correction: i45/48/49/69/78/88
    # had `! Bad` only in hypotheses while the conclusion closed by get_set/mem_set/lossless).
    # A BARE get (`(oget m.[k]).…`, no set) is NOT a specific route — it genuinely closes by
    # negBadE there (i21), so Bad must stay; we cannot distinguish that from a bare get that
    # closes by a hypothesis (i81) on goal text alone, so we keep Bad on bare gets.
    _concl_has_specific_route = bool(
        _FMAP_GET_OF_SET_RE.search(concl) or _FMAP_SET_RE.search(concl)
        or "\\in" in concl or _LOSSLESS_CONCL_RE.search(concl)
    )
    if _BAD_PREDICATE_RE.search(concl) or (
        _BAD_PREDICATE_RE.search(_hypotheses_text(goal_text)) and not _concl_has_specific_route
    ):
        _add("Bad")

    # NOTE — sub-cluster (b), a type-carried GROUP-op route for a project group type's infix
    # `+`/`-` (ChaChaPoly `poly_out` ← `poly_out_sub_add`/`poly_out_add_sub`/`poly_out_swap`), was
    # investigated and DELIBERATELY NOT SHIPPED. A `poly_out`-typed variable is carried through ~29
    # step4_1 goals, but the cancellation family is the actual closing move on only ~4 of them; a
    # source-gated `((+) (-))` route therefore fired as NOISE on 25/29 steps (verified by capture).
    # No goal-text-only signal separates the pivot `+`/`-` from an incidental carried-along one — so
    # routing it is a net over-router, which the panel-audit history (PIR `(+^)` mis-route; the prior
    # broad-operator fix's 8/16 over-corrections) flags as the #1 risk. Under-deliver instead.

    extracted: list[str] = []
    for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", concl):
        tok = m.group(0)
        if (len(tok) < 2 or tok in seen or tok in bound or tok.split(".")[0] in bound
                or tok in types or tok.lower() in _GOAL_OP_STOPWORDS
                # a SOURCE-confirmed local inductive-predicate head (`inv`/`Bad`) has no
                # rewrite-lemma family — routing operator_lemmas to it is a dead end (panel
                # audit i25/i44/i48). Gated on the source so a real operator named `inv`
                # (Pedersen's field inverse) is never dropped.
                or tok in inductive_heads):
            continue
        seen.add(tok)
        extracted.append(tok)
    # PROMOTE high-value list/membership ops that are literally in the conclusion ahead of the
    # `[:8]` cap (panel audit cc_step4_1 i94/i99: `filter` extracted at token index 9/11, lost to
    # the cap, so its `mem_filter`/`filter_*` family was never offered though `map`/`has` were).
    # This only REORDERS already-extracted operators — it cannot introduce a token not in the goal.
    promoted = [t for t in extracted if t in _PRIORITY_LIST_OPS]
    rest = [t for t in extracted if t not in _PRIORITY_LIST_OPS]
    ops.extend(promoted + rest)
    for sym in _SALIENT_SYMBOLIC_OPS:
        if sym in concl and sym not in seen:
            seen.add(sym)
            ops.append(sym)
    return ops[:8]


# ---------------------------------------------------------------------------
# Source-keyed routes (panel-audit 2026-06-13, PRG.ec::Plog_Psample strands).
#
# These read the target `.ec` file directly off the node state's `file_path` and
# NAME the mechanical move (the closing lemma / the intro constructor) instead of
# dumping the conclusion head (`Plog.prg`, `P0`, `Bad`) as a searchable operator.
# Both are best-effort and never raise: an absent / unreadable file, a relational
# goal, or no local match all collapse to `[]`.
# ---------------------------------------------------------------------------

# A file-relative source-text cache so re-rendering the same node's panels does not
# re-read the `.ec` from disk on every turn. Keyed by (path, mtime).
_SOURCE_TEXT_CACHE: dict[tuple[str, float], str] = {}


def _read_source_text(source_path: str) -> str:
    """Best-effort read of the target `.ec`. Returns '' on any failure (missing
    path, unreadable file). Caches on (path, mtime) so repeat panel renders for the
    same node do not re-hit the disk."""
    path = str(source_path or "").strip()
    if not path:
        return ""
    try:
        import os

        mtime = os.path.getmtime(path)
    except OSError:
        return ""
    cache_key = (path, mtime)
    cached = _SOURCE_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        text = ""
    _SOURCE_TEXT_CACHE[cache_key] = text
    return text


def _final_conclusion(goal_text: str) -> str:
    """The HEAD obligation that actually has to be proved: the conclusion text below
    the turnstile, stripped of leading `forall …,` binders and of every `… =>`
    premise (an `exact LEMMA` discharges the goal AFTER `move`-ing the premises in).
    For `forall &2, Bad … => islossless Plog.prg` this is `islossless Plog.prg`."""
    return build_proof_obligation_ir(goal_text).conclusion.text


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split `text` on `sep` only where bracket depth is 0."""
    out: list[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        elif depth == 0 and text.startswith(sep, i):
            out.append(text[start:i])
            i += len(sep)
            start = i
            continue
        i += 1
    out.append(text[start:])
    return out


def _inductive_intro_routes(goal_text: str, source_path: str) -> list[dict[str, Any]]:
    """GAP 2 — INDUCTIVE-PREDICATE intro route. When the goal conclusion's HEAD is a
    file-local `inductive <Name> … = | <Ctor> … | <Ctor> …` predicate (PRG.ec's
    `Bad`), the mechanical help is its INTRODUCTION CONSTRUCTORS, not a rewrite. Parse
    the constructors from the `.ec` and surface them as `apply <Ctor>` routes
    (i32 `Bad (P.seed{2}::P.logP{2}) F.m{2}` → `apply Cycle` / `apply Collision`)."""
    head = _conclusion_head_symbol(_final_conclusion(goal_text))
    if not head:
        return []
    source = _read_source_text(source_path)
    if not source:
        return []
    constructors = _inductive_constructors(source, head)
    if not constructors:
        return []
    return [
        {
            "constructor": ctor,
            "submit": f"apply {ctor}.",
            "why": (
                f"`{head}` is a file-local inductive predicate; `{ctor}` is one of its "
                f"introduction constructors."
            ),
        }
        for ctor in constructors[:6]
    ]


def _conclusion_head_symbol(text: str) -> str:
    """The leading applied symbol of a conclusion: `Bad (…) F.m{2}` → `Bad`. Empty
    when the head is not a bare upper/lower identifier (e.g. an `islossless …`,
    a quantifier, a parenthesised/relational head)."""
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_']*)\b", str(text or ""))
    if not m:
        return ""
    head = m.group(1)
    if head in {"forall", "exists", "islossless", "is_lossless", "let", "if"}:
        return ""
    return head


def _inductive_constructors(source: str, name: str) -> list[str]:
    """Constructor names of a file-local `inductive <name> … = | C1 … | C2 …`.
    Robust to the multi-line PRG.ec form (`inductive Bad logP (m : …) =` then the
    `| Cycle …` / `| Collision r …` arms on the next lines). Returns [] if `name`
    is not declared inductive in the source."""
    head = re.search(
        r"\binductive\s+" + re.escape(name) + r"\b[^=]*=",
        source,
    )
    if not head:
        return []
    # The constructor block runs from the `=` to the terminating `.` of the
    # declaration (a `.` not part of an EC `.\`n` projection / decimal). Scan forward.
    rest = source[head.end():]
    block = rest[:_statement_terminator_end(rest)]
    constructors: list[str] = []
    for m in re.finditer(r"\|\s*([A-Za-z_][A-Za-z0-9_']*)", block):
        ctor = m.group(1)
        if ctor not in constructors:
            constructors.append(ctor)
    return constructors


def _statement_terminator_end(text: str) -> int:
    """Index of the `.` that ends an EasyCrypt statement (an inductive body, a lemma
    signature), skipping a `.` that is NOT a statement terminator: a member access /
    dot-projection / decimal (`F.f`, `c.‘1`, `0.5`) where the `.` is followed by an
    identifier or digit, or a `.` inside brackets. A real terminator is followed by
    whitespace / a comment / end-of-text. Falls back to len(text) when none is seen."""
    depth = 0
    n = len(text)
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        elif ch == "." and depth == 0:
            nxt = text[i + 1] if i + 1 < n else ""
            # `F.f` / `Plog.prg` / `.`1` / `0.5` — the `.` glues two tokens, not the end.
            if nxt and (nxt.isalnum() or nxt in "_`'"):
                continue
            return i
    return n


def _visible_hypotheses(goal_text: str) -> list[str]:
    """Named PROPOSITIONAL hypotheses in the goal context (`name : <prop>` whose RHS
    is a proposition, not a bare type) — a fact, surfaced verbatim."""
    hyps: list[str] = []
    for line in str(goal_text or "").splitlines():
        s = line.strip()
        if s and set(s) == {"-"} and len(s) >= 3:
            break  # turnstile reached; the conclusion is below it
        m = re.match(r"([A-Za-z_][\w']*)\s*:\s*(.+)$", s)
        if not m:
            continue
        rhs = m.group(2).strip()
        if any(op in rhs for op in ("<=", "<", ">", "=", "\\in", "=>", "<>", "/\\", "\\/")):
            hyps.append(f"{m.group(1)}: {rhs}")
    return hyps[:6]


def pure_tail_surface(
    view: dict[str, Any],
    *,
    source_path: str = "",
) -> dict[str, Any]:
    goal_text = view_goal_text(view)
    if not looks_like_pure_tail_goal(goal_text, view):
        return {}
    families = _pure_tail_obligation_families(goal_text)
    # Drop a dead-end inductive-predicate head from the operator route ONLY when the target
    # source confirms it is declared `inductive` (so a real `inv` operator is never dropped).
    inductive_heads = _local_inductive_predicate_names(_read_source_text(source_path))
    operators = _goal_operators(goal_text, inductive_heads=inductive_heads)
    hypotheses = _visible_hypotheses(goal_text)
    obligation_ir = build_proof_obligation_ir(goal_text).to_dict()
    obligation_shape = _pure_logic_obligation_shape_surface(obligation_ir)
    memory = _ambient_memory_translation_surface(goal_text)
    membership = _membership_decomposition_surface(goal_text)
    witnesses = _existential_witness_surface(goal_text)
    lookup = _map_update_lookup_surface(goal_text)
    iter_successor = _iter_successor_surface(goal_text)
    integer_arithmetic = _integer_arithmetic_surface(goal_text)
    list_normalization = _list_normalization_surface(goal_text)
    hypothesis_graph = _local_hypothesis_graph(goal_text)
    app = _dict(view.get("application_context"))
    # application_context is the compact typed projection boundary for compiler
    # handles.  Preserve those fact dictionaries here instead of maintaining a
    # second field allowlist that can silently drop producer schema extensions.
    mechanical_matches = [
        dict(item)
        for item in _list(app.get("mechanical_goal_candidates"))[:16]
        if isinstance(item, dict) and item.get("lemma")
    ]
    distribution_certificates = [
        dict(item)
        for item in _list(app.get("distribution_certificates"))[:8]
        if isinstance(item, dict) and item.get("lemma")
    ]
    map_update_transport = _map_update_transport_surface(
        goal_text,
        mechanical_matches,
    )
    gaps = _pure_tail_gap_analysis(goal_text, view)
    intro_routes = _inductive_intro_routes(goal_text, source_path)
    if not any((
        families, operators, hypotheses, obligation_shape, memory, membership,
        witnesses, lookup, iter_successor, integer_arithmetic, list_normalization,
        hypothesis_graph, map_update_transport,
        mechanical_matches, distribution_certificates, gaps, intro_routes,
    )):
        return {}
    return _drop_empty({
        "state": _pure_tail_state(goal_text),
        "inductive_intro_routes": intro_routes,
        "proof_obligation_ir": obligation_ir,
        "obligation_shape_surface": obligation_shape,
        "integer_arithmetic_surface": integer_arithmetic,
        "list_normalization_surface": list_normalization,
        "map_update_transport_surface": map_update_transport,
        "iter_successor_surface": iter_successor,
        "local_hypothesis_graph": hypothesis_graph,
        "mechanical_goal_candidates": mechanical_matches,
        "distribution_certificates": distribution_certificates,
        # NEW-2 (2026-06-05): the REAL operators in the goal + the visible
        # propositional hypotheses — facts the agent can `lookup_symbol`, replacing
        # the fuzzy obligation-family BUCKET in the agent-facing panel. The family
        # list stays for internal (recovery) use only.
        "goal_operators": operators,
        "visible_hypotheses": hypotheses,
        "obligation_families": families[:6],
        "ambient_memory_translation": memory,
        "membership_decomposition_surface": membership,
        "existential_witness_surface": witnesses,
        "map_update_lookup_surface": lookup,
        "gap_analysis": gaps[:4],
        "related_checkpoints": (
            _pure_tail_checkpoint_refs(view)[:4] if gaps else []
        ),
        "effect": (
            "Summarizes verifier-visible pure-goal structure after program "
            "frontier actions have been discharged or hidden by local proof "
            "steps."
        ),
        "limitations": [
            "This panel records syntactic and proof-state facts from the current view.",
            "It does not choose a tactic or instantiate a lemma.",
        ],
    })


def _local_hypothesis_graph(goal_text: str) -> dict[str, Any]:
    """Exact local relation facts and mechanically verified order chains."""
    hypotheses = named_local_hypotheses(goal_text)
    chains = local_order_chains(goal_text)
    if not hypotheses and not chains:
        return {}
    return {
        "authority": "current_goal_context",
        "exact_hypotheses": hypotheses[:8],
        "order_chains": chains[:4],
        "effect": "Records exact outer relations and mechanically composable order chains.",
        "limitations": ["No tactic or semantic proof route is selected."],
    }


def looks_like_pure_tail_goal(goal_text: str, view: dict[str, Any]) -> bool:
    text = str(goal_text or "")
    if not text.strip():
        return False
    if _goal_text_contains_call_site(text):
        return False
    if _looks_like_procedure_equivalence_obligation(text):
        return False
    proof_status = _dict(view.get("proof_status") or view.get("proof_position"))
    current_layer = str(proof_status.get("current_layer") or "").lower()
    view_focus = str(proof_status.get("view_focus") or "").lower()
    frontier = _dict(view.get("program_frontier"))
    live_call_sites = _list(frontier.get("call_sites"))
    if live_call_sites and "ambient" not in current_layer:
        return False
    lower = text.lower()
    pure_markers = (
        "forall" in lower
        or "=>" in text
        or "/\\" in text
        or "\\in" in text
        or "::" in text
        or ".[" in text
        or ".`" in text
        or "{1}" in text
        or "{2}" in text
        or "`&" in text
        or "%/" in text
        or "%%" in text
        or "b2i" in lower
        or bool(re.search(r"\bsize\s*\(\s*drop\b", text))
        or bool(build_proof_obligation_ir(text).conclusion.relation)
    )
    ambient_focus = (
        "ambient" in current_layer
        or "ambient" in view_focus
        or proof_status.get("goal_type") in {"ambient", "unknown"}
    )
    logic_tail = any(
        token in lower
        for token in (
            "mem_set",
            "get_set",
            "lossless",
            " dpoly",
            "poly",
            "pred",
        )
    )
    return bool(pure_markers and (ambient_focus or logic_tail or "forall" in lower))


def _goal_text_contains_call_site(text: str) -> bool:
    return "<@" in str(text or "") or bool(
        re.search(r"\bcall\s+[A-Za-z_][A-Za-z0-9_.'`]*", str(text or ""))
    )


def _looks_like_procedure_equivalence_obligation(goal_text: str) -> bool:
    text = str(goal_text or "")
    lower = text.lower()
    if "pre =" not in lower or "post =" not in lower:
        return False
    if "equiv[" in lower:
        return True
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "~" not in stripped:
            continue
        if re.match(r"^(pre|post)\s*=", stripped, flags=re.IGNORECASE):
            continue
        left, _, right = stripped.partition("~")
        if left.strip() and right.strip():
            return True
    return bool(
        re.search(
            r"(?m)^\s*[A-Za-z_][A-Za-z0-9_.'`]*(?:\([^{}\n]*\))?"
            r"\s*~\s*"
            r"[A-Za-z_][A-Za-z0-9_.'`]*(?:\([^{}\n]*\))?",
            text,
        )
    )


def _pure_tail_state(goal_text: str) -> str:
    text = str(goal_text or "")
    if ".[" in text and "\\in" in text:
        return "map_membership_tail"
    if ".[" in text:
        return "map_projection_tail"
    if "forall" in text.lower():
        return "quantified_ambient_tail"
    return "ambient_pure_tail"


def _pure_tail_obligation_families(goal_text: str) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    for item in (
        _sampling_bijection_family(goal_text),
        _map_update_projection_family(goal_text),
        _constructor_projection_family(goal_text),
        _map_membership_preservation_family(goal_text),
        _quantified_residual_family(goal_text),
    ):
        if item:
            families.append(item)
    return families


def _sampling_bijection_family(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    lower = text.lower()
    # NEW-4 (2026-06-05): the old " d" token matched ANY space-d word (dom, do, div,
    # a `d`-variable) and false-asserted "distribution token seen" on goals with no
    # distribution. Match real distribution/measure tokens instead.
    has_distribution = any(token in lower for token in (
        "<$", "dword", "dpoly", "dlet", "dmap", "dunit", "duniform",
        "lossless", "mu1 ", "mu ",
    ))
    has_affine_shape = (
        "+" in text
        and "-" in text
        and any(token in lower for token in ("poly", "eval", "sub", "add"))
    )
    if not (has_distribution or has_affine_shape):
        return {}
    evidence = []
    if has_distribution:
        evidence.append("distribution or lossless token remains visible")
    if has_affine_shape:
        evidence.append("add/sub expression remains visible")
    return {
        "family": "sampling_bijection",
        "evidence": evidence,
        "effect": (
            "The remaining pure goal may include invertibility or lossless "
            "side conditions from an earlier sampling alignment."
        ),
        "limitations": "No distribution lemma is selected by this surface.",
    }


def _map_update_projection_family(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    update_keys = _map_update_keys(text)
    lookup_terms = _map_lookup_terms(text)
    if not update_keys and not lookup_terms:
        return {}
    return _drop_empty({
        "family": "map_update_projection",
        "update_count": len(update_keys),
        "lookup_count": len(lookup_terms),
        "sample_update_keys": update_keys[:4],
        "sample_lookup_terms": lookup_terms[:4],
        "visible_key_cases": _map_update_lookup_cases(text)[:4],
        "effect": (
            "The pure goal contains finite-map update or lookup structure "
            "whose key/projection equalities are verifier-visible facts."
        ),
        "limitations": "The surface does not rewrite any map expression.",
    })


def _constructor_projection_family(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    selectors = sorted(set(re.findall(r"\.\`[0-9]+", text)))
    constructors = sorted(set(re.findall(r"\bmk_[A-Za-z0-9_']+", text)))
    tuple_equalities = len(re.findall(r"=\s*\([^)\n]+,[^)\n]+\)", text))
    if not any((selectors, constructors, tuple_equalities)):
        return {}
    return _drop_empty({
        "family": "constructor_projection",
        "selectors": selectors[:4],
        "constructors": constructors[:4],
        "tuple_equality_count": tuple_equalities,
        "effect": (
            "The pure goal exposes tuple/record projections or constructor "
            "equalities that can connect program variables to map/list keys."
        ),
        "limitations": "Projection equalities are reported only when visible in the current text.",
    })


def _map_membership_preservation_family(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    if "\\in" not in text and " in " not in text:
        return {}
    update_keys = _map_update_keys(text)
    cons_heads = _cons_heads(text)
    if not update_keys and "::" not in text:
        return {}
    return _drop_empty({
        "family": "map_membership_preservation",
        "update_key_heads": [
            _first_tuple_component(key)
            for key in update_keys[:4]
            if _first_tuple_component(key)
        ],
        "cons_heads": cons_heads[:4],
        "effect": (
            "The remaining membership obligation relates an updated map key "
            "to a list or set membership fact."
        ),
        "limitations": (
            "The surface reports the alignment facts currently visible; it "
            "does not synthesize missing equalities."
        ),
    })


def _quantified_residual_family(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    lower = text.lower()
    if "forall" not in lower and "=>" not in text:
        return {}
    return {
        "family": "quantified_residual_logic",
        "evidence": [
            *(
                ["universal quantifier visible"]
                if "forall" in lower else []
            ),
            *(
                ["implication residual visible"]
                if "=>" in text else []
            ),
        ],
        "effect": (
            "The current proof point is dominated by local logical "
            "obligations rather than program-frontier movement."
        ),
        "limitations": "Quantifier names are not normalized across EasyCrypt pretty-printer variants.",
    }


def _membership_decomposition_surface(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    if "\\in" not in text and " in " not in text:
        return {}
    shapes: list[str] = []
    if "++" in text:
        shapes.append("concat_membership")
    if re.search(r"\bmap\s*\(", text):
        shapes.append("map_membership")
    if re.search(r"\bfilter\s+", text):
        shapes.append("filter_membership")
    if "::" in text:
        shapes.append("cons_membership")
    if ".[" in text and "<-" in text:
        shapes.append("map_update_membership")
    if not shapes:
        return {}
    destructors: list[dict[str, Any]] = []
    if "concat_membership" in shapes:
        destructors.append({
            "source_shape": "concat_membership",
            "source_count": text.count("++"),
            "effect": "Separates a membership fact into left-source and right-source cases.",
            "limitations": "This records the case shape only; no branch is selected.",
        })
    if "map_membership" in shapes:
        destructors.append({
            "source_shape": "map_membership",
            "source_count": len(re.findall(r"\bmap\s*\(", text)),
            "effect": "Exposes a preimage term for a mapped membership source.",
            "limitations": "The concrete preimage name depends on the local proof context.",
        })
    if "filter_membership" in shapes:
        destructors.append({
            "source_shape": "filter_membership",
            "source_count": len(re.findall(r"\bfilter\s+", text)),
            "effect": "Carries both source membership and the filter predicate fact.",
            "limitations": "Predicate simplification is left to checked local proof steps.",
        })
    if "cons_membership" in shapes:
        destructors.append({
            "source_shape": "cons_membership",
            "source_count": text.count("::"),
            "effect": "Splits list membership into head and tail cases.",
            "limitations": "The surface does not decide which case applies.",
        })
    if "map_update_membership" in shapes:
        destructors.append({
            "source_shape": "map_update_membership",
            "source_count": len(_map_update_keys(text)),
            "effect": "Keeps finite-map update keys visible beside membership obligations.",
            "limitations": "Lookup/update equalities remain verifier-checked obligations.",
        })
    return _drop_empty({
        "source_shapes": list(dict.fromkeys(shapes)),
        "membership_hypotheses": _membership_hypotheses(text)[:5],
        "visible_destructors": destructors[:6],
        "effect": (
            "Summarizes list/map/filter membership sources whose local case "
            "facts are visible in the current pure tail."
        ),
        "limitations": [
            "No destructor tactic is chosen by this surface.",
            "The panel does not assume which membership branch is true.",
        ],
    })


def _existential_witness_surface(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    if not re.search(r"\bexists\b", text):
        return {}
    binders = _existential_binders(text)
    candidates: list[dict[str, Any]] = []
    for key in _map_update_keys(text)[:5]:
        head = _first_tuple_component(key)
        candidates.append(_drop_empty({
            "source": "map_update_key",
            "term": head or key,
            "container_term": key,
            "why_visible": "Finite-map update key appears in the same pure tail.",
        }))
    for head in _cons_heads(text)[:5]:
        candidates.append({
            "source": "list_head",
            "term": head,
            "why_visible": "List head appears in a membership target.",
        })
    for term in _membership_left_terms(text)[:5]:
        candidates.append({
            "source": "membership_member",
            "term": term,
            "why_visible": "A visible membership fact binds this member term.",
        })
    providers = _witness_provider_hypotheses(text)
    for item in providers[:3]:
        candidates.append({
            "source": "quantified_hypothesis",
            "term": item.get("label") or item.get("preview"),
            "why_visible": "A visible hypothesis contains both universal and existential structure.",
        })
    return _drop_empty({
        "binders": binders[:6],
        "candidate_sources": _dedupe_dicts(candidates)[:8],
        "provider_hypotheses": providers[:4],
        "effect": (
            "Lists verifier-visible term sources that can instantiate local "
            "existentials in the pure tail."
        ),
        "limitations": [
            "No witness is selected by this surface.",
            "Candidate terms may still require local equality or membership facts.",
        ],
    })


def _map_update_lookup_surface(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    update_keys = _map_update_keys(text)
    lookup_terms = _map_lookup_terms(text)
    if not update_keys and not lookup_terms:
        return {}
    return _drop_empty({
        "update_keys": update_keys[:6],
        "lookup_terms": lookup_terms[:6],
        "key_cases": _map_update_lookup_cases(text)[:8],
        "effect": (
            "Summarizes finite-map update and lookup keys that determine "
            "same-key versus different-key local obligations."
        ),
        "limitations": [
            "This surface does not perform a rewrite or case split.",
            "A key case marked unresolved only means no equality path is visible in this goal text.",
        ],
    })


def _pure_logic_obligation_shape_surface(obligation_ir: dict[str, Any]) -> dict[str, Any]:
    if not obligation_ir:
        return {}
    binders = [
        {"shape": _obligation_shape_label(str(item.get("kind") or ""), "binder"), "text": _preview(str(item.get("text") or ""), limit=180)}
        for item in obligation_ir.get("binders") or []
        if isinstance(item, dict) and item.get("text")
    ]
    premises = [
        {"shape": _obligation_shape_label(str(item.get("kind") or ""), "premise"), "text": _preview(str(item.get("text") or ""), limit=180)}
        for item in obligation_ir.get("premises") or []
        if isinstance(item, dict) and item.get("text")
    ]
    obligations = [
        {"shape": _obligation_shape_label(str(item.get("kind") or ""), "obligation"), "text": _preview(str(item.get("text") or ""), limit=180)}
        for item in obligation_ir.get("conclusion_parts") or []
        if isinstance(item, dict) and item.get("text")
    ]
    return _drop_empty({
        "authority": obligation_ir.get("authority"),
        "binders": binders[:4],
        "implication_premises": premises[:4],
        "conclusion_obligations": obligations[:4],
    })


def _obligation_shape_label(kind: str, role: str) -> str:
    labels = {
        "forall_binder": "universal binder",
        "exists_binder": "existential binder",
        "iter_equality": "iter equality",
        "nonempty_list": "nonempty-list",
        "size_drop_inequality": "size/drop inequality",
        "let_expression": "let expression",
    }
    base = labels.get(kind, kind.replace("_", " ") or "unknown")
    return f"{base} {role}" if role in {"premise", "obligation"} else base


def _iter_successor_surface(goal_text: str) -> dict[str, Any]:
    concl = _conclusion_text(goal_text)
    if not concl:
        return {}
    calls: list[dict[str, str]] = []
    for match in re.finditer(r"\biter\b", concl):
        pos = match.end()
        while pos < len(concl) and concl[pos].isspace():
            pos += 1
        if pos >= len(concl) or concl[pos] != "(":
            continue
        count = _balanced_parenthesized_inner(concl, pos)
        if not count or not _has_top_level_one_step(count):
            continue
        item = {
            "count_shape": _preview(count, limit=180),
            "successor_offset": "+ 1",
            "lemma_family": "iter successor",
        }
        if item not in calls:
            calls.append(item)
    return _drop_empty({"successor_calls": calls[:4]})


def _has_top_level_one_step(text: str) -> bool:
    parts = [part.strip() for part in _split_top_level(str(text or ""), "+")]
    return any(part == "1" for part in parts)


def _integer_arithmetic_surface(goal_text: str) -> dict[str, Any]:
    """Mechanical structure for pure integer/list residuals.

    This deliberately reports only verifier-visible shapes: drop-length terms,
    Euclidean division/modulo symbols, boolean-to-int guards, and the branch
    boundaries implied by `size (drop n xs)`. It does not pick a branch, lemma
    instantiation, or tactic script.
    """
    # Arithmetic families describe the obligation being closed, not symbols
    # that happen to occur only in an implication premise.  Premises remain
    # available to the prover as side-condition evidence elsewhere in the
    # typed obligation surface.
    obligation = build_proof_obligation_ir(goal_text)
    concl = obligation.conclusion.text or _conclusion_text(goal_text)
    if not concl:
        return {}
    size_drop_terms = _size_drop_terms(concl)
    b2i_guards = _b2i_guards(concl)
    has_div = "%/" in concl
    has_mod = "%%" in concl
    if not any((size_drop_terms, b2i_guards, has_div, has_mod)):
        return {}

    split_candidates: list[dict[str, Any]] = []
    for term in size_drop_terms:
        amount = str(term.get("drop_amount") or "").strip()
        source = str(term.get("list_term") or "").strip()
        if not amount or not source:
            continue
        split_candidates.append({
            "condition": f"{amount} <= {_size_application(source)}",
            "source_shape": term.get("source_shape"),
            "why": (
                "The length/drop lemmas branch at the point where the drop "
                "amount reaches the source list length."
            ),
        })

    lemma_families: list[dict[str, Any]] = []
    if size_drop_terms:
        lemma_families.append({
            "shape": "size/drop",
            "lemma_names": ["size_drop", "drop_oversize"],
            "needs": [
                "nonnegative drop amount",
                "the boundary case for drop amount versus source length",
            ],
        })
    if has_div:
        lemma_families.append({
            "shape": "integer division `%/`",
            "lemma_names": ["divzMDl", "divz_small"],
            "needs": ["nonzero or positive divisor", "small-numerator branch when applicable"],
        })
    if has_mod:
        lemma_families.append({
            "shape": "integer modulo `%%`",
            "lemma_names": ["modzMDl", "modz_small"],
            "needs": ["nonzero or positive divisor", "small-numerator branch when applicable"],
        })
    if b2i_guards:
        lemma_families.append({
            "shape": "boolean-to-int guard",
            "lemma_names": ["b2i"],
            "needs": ["the truth value of the displayed guard after local rewrites"],
        })

    return _drop_empty({
        "visible_shapes": _dedupe_strings([
            *("size(drop ...)" for _ in size_drop_terms[:1]),
            *(["integer division `%/`"] if has_div else []),
            *(["integer modulo `%%`"] if has_mod else []),
            *(["b2i guard"] if b2i_guards else []),
        ]),
        "size_drop_terms": size_drop_terms[:4],
        "split_candidates": _dedupe_dicts(split_candidates)[:4],
        "b2i_guards": b2i_guards[:4],
        "lemma_families": lemma_families,
        "limitations": [
            "No branch condition is asserted true by this surface.",
            "No lemma is instantiated and no tactic script is selected.",
        ],
    })


def _list_normalization_surface(goal_text: str) -> dict[str, Any]:
    """Mechanical stdlib routes for nested list terms in a pure residual."""
    obligation_ir = build_proof_obligation_ir(goal_text)
    concl = obligation_ir.conclusion.text
    if not concl:
        return {}
    families: list[dict[str, Any]] = []
    size_inners = _size_application_inners(concl)
    if _nth_sequence_has_marker(concl, "++"):
        families.append({
            "shape": "nth over concatenation",
            "lemma_names": ["nth_cat"],
        })
    if any("++" in inner for inner in size_inners):
        families.append({
            "shape": "size of concatenation",
            "lemma_names": ["size_cat"],
        })
    if any(re.search(r"\bmap\b", inner) for inner in size_inners):
        families.append({
            "shape": "size of map",
            "lemma_names": ["size_map"],
        })

    nth_map_terms = _nth_map_terms(concl, goal_text)
    if nth_map_terms:
        if any(item.get("side_condition_status") == "visible_false" for item in nth_map_terms):
            families.append({
                "shape": "nth outside map bounds",
                "lemma_names": ["nth_out", "size_map"],
                "side_condition": "! (0 <= index < size source_list)",
            })
        if any(item.get("side_condition_status") != "visible_false" for item in nth_map_terms):
            families.append({
                "shape": "nth over map",
                "lemma_names": ["nth_map"],
                "side_condition": "0 <= index < size source_list",
            })
    prefix_successors = _mapped_take_prefix_successors(obligation_ir)
    if not families and not prefix_successors:
        return {}
    return {
        "lemma_families": families,
        "nth_map_terms": nth_map_terms[:4],
        "prefix_successor_chains": prefix_successors[:4],
        "authority": "current_goal_and_visible_hypotheses",
        "limitations": [
            "The surface identifies matching stdlib families and visible side-condition evidence only.",
            "It does not choose rewrite order or discharge a side condition.",
        ],
    }


def _mapped_take_prefix_successors(obligation_ir: Any) -> list[dict[str, Any]]:
    """Recognise ``map f (take k xs) ++ [f (nth d xs k)]`` successors.

    This is a structural identity assembled from the current conclusion and
    visible bounds.  The result names the loaded List lemma family but does
    not select a tactic or claim that unrelated conjuncts are discharged.
    """
    out: list[dict[str, Any]] = []
    parts = list(obligation_ir.conclusion_parts) or [obligation_ir.conclusion]
    visible_premises = [str(item.text or "") for item in obligation_ir.premises]
    for part in parts:
        relation = top_level_relation_parts(str(part.text or ""))
        if relation is None or relation[1] != "=":
            continue
        left, _equals, right = relation
        left_apps = _map_take_applications(left)
        right_apps = _map_take_applications(right)
        for base_side, successor_side, base_apps, successor_apps in (
            (left, right, left_apps, right_apps),
            (right, left, right_apps, left_apps),
        ):
            for base in base_apps:
                for successor in successor_apps:
                    if (
                        base["mapper"] != successor["mapper"]
                        or _normalise_logic_term(base["source_list"])
                        != _normalise_logic_term(successor["source_list"])
                        or not _one_step_successor(successor["index"], base["index"])
                        or not _mapped_nth_singleton_tail(base_side, base)
                    ):
                        continue
                    lower = f"0 <= {base['index']}"
                    upper = f"{base['index']} < {_size_application(base['source_list'])}"
                    visible = [
                        premise for premise in visible_premises
                        if _normalise_logic_term(premise) in {
                            _normalise_logic_term(lower),
                            _normalise_logic_term(upper),
                        }
                    ]
                    item = {
                        "shape": "mapped take-prefix successor",
                        "mapper": base["mapper"],
                        "index": base["index"],
                        "source_list": base["source_list"],
                        "side_condition": f"0 <= {base['index']} < {_size_application(base['source_list'])}",
                        "side_condition_status": (
                            "visible" if len(visible) == 2 else "not_established"
                        ),
                        "supporting_premises": visible,
                        "lemma_chain": [
                            {
                                "lemma": "take_nth",
                                "role": "extend take k xs with the visible next nth element",
                            },
                            {
                                "lemma": "map_rcons",
                                "role": "push map through that one-element prefix extension",
                            },
                            {
                                "lemma": "cats1",
                                "role": "normalize appended-singleton and rcons forms",
                            },
                        ],
                    }
                    if item not in out:
                        out.append(item)
    return out


def _map_take_applications(text: str) -> list[dict[str, Any]]:
    source = str(text or "")
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"\bmap\b", source):
        mapper, cursor = _term_after(source, match.end())
        take_term, end = _term_after(source, cursor)
        words = _split_top_level_words(take_term)
        if len(words) != 3 or words[0] != "take":
            continue
        out.append({
            "mapper": mapper,
            "index": _strip_enclosing_parens(words[1]),
            "source_list": words[2],
            "start": match.start(),
            "end": end,
        })
    return out


def _mapped_nth_singleton_tail(text: str, application: dict[str, Any]) -> bool:
    tail = str(text or "")[int(application.get("end") or 0):].strip()
    match = re.fullmatch(r"\+\+\s*\[(.+)\]", tail, flags=re.DOTALL)
    if not match:
        return False
    element = match.group(1).strip()
    mapper, cursor = _term_after(element, 0)
    nth_term, end = _term_after(element, cursor)
    if mapper != application.get("mapper") or element[end:].strip():
        return False
    words = _split_top_level_words(nth_term)
    if len(words) < 4 or words[0] != "nth":
        return False
    return bool(
        _normalise_logic_term(words[-2])
        == _normalise_logic_term(str(application.get("source_list") or ""))
        and _normalise_logic_term(words[-1])
        == _normalise_logic_term(str(application.get("index") or ""))
    )


def _one_step_successor(candidate: str, base: str) -> bool:
    parts = [
        _strip_enclosing_parens(item.strip())
        for item in _split_top_level(_strip_enclosing_parens(candidate), "+")
    ]
    return bool(
        len(parts) == 2
        and _normalise_logic_term(parts[0]) == _normalise_logic_term(base)
        and _normalise_logic_term(parts[1]) == "1"
    )


def _strip_enclosing_parens(text: str) -> str:
    value = str(text or "").strip()
    while value.startswith("("):
        close = _matching_parenthesis_index(value, 0)
        if close != len(value) - 1:
            break
        value = value[1:-1].strip()
    return value


def _map_update_transport_surface(
    goal_text: str,
    mechanical_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compose pointwise key transport with finite-map get/set normalization."""
    obligation_ir = build_proof_obligation_ir(goal_text)
    conclusion = obligation_ir.conclusion.text
    if "<-" not in conclusion or ".[" not in conclusion:
        return {}
    update_keys = _map_update_keys(conclusion)
    if len(update_keys) < 2:
        return {}
    outer_binders = {
        name
        for binder_part in obligation_ir.binders
        for name in re.findall(
            r"[A-Za-z_][A-Za-z0-9_']*",
            re.sub(r"^forall\s+", "", str(binder_part.text or "")),
        )
        if name not in {"forall"}
    }
    for premise in obligation_ir.premises:
        premise_text = str(premise.text or "")
        if (
            ("forall" not in premise_text and not outer_binders)
            or ".[" not in premise_text
            or "=" not in premise_text
        ):
            continue
        binder = re.search(
            r"\bforall\s+(?:\(\s*)?([A-Za-z_][A-Za-z0-9_']*)\b",
            premise_text,
        )
        variables = {binder.group(1)} if binder else outer_binders
        transforms = [
            match.group(1).rsplit(".", 1)[-1].strip("'")
            for variable in variables
            for match in re.finditer(
                rf"\b([A-Za-z_][A-Za-z0-9_.']*)\s+{re.escape(variable)}\b",
                premise_text,
            )
        ]
        for transform in transforms:
            pair = next(
                (
                    (base, transformed)
                    for base in update_keys
                    for transformed in update_keys
                    if base != transformed
                    and _normalise_logic_term(transformed)
                    == _normalise_logic_term(f"{transform} ({base})")
                ),
                None,
            )
            if pair is None:
                continue
            inverse_match = next(
                (
                    item for item in mechanical_matches
                    if item.get("match_kind") == "loaded_left_inverse_support"
                    and item.get("transform") == transform
                ),
                {},
            )
            return _drop_empty({
                "shape": "pointwise finite-map key transport",
                "pointwise_relation": premise_text,
                "key_transform": transform,
                "update_key_pair": {"source": pair[0], "transformed": pair[1]},
                "lookup_normalization_lemma": "get_setE",
                "left_inverse_lemma": inverse_match.get("lemma"),
                "left_inverse": inverse_match.get("inverse"),
                "effect": (
                    "get_setE exposes the same-key/different-key cases; a loaded "
                    "left inverse for the displayed transform supplies injectivity evidence."
                ),
                "limitations": [
                    "No key case or rewrite order is selected.",
                    "The surface does not claim that the remaining value equality is automatic.",
                ],
            })
    return {}


def _size_application_inners(text: str) -> list[str]:
    out: list[str] = []
    source = str(text or "")
    for match in re.finditer(r"\bsize\s*\(", source):
        open_idx = source.find("(", match.start(), match.end())
        close_idx = _matching_parenthesis_index(source, open_idx)
        if close_idx < 0:
            continue
        inner = source[open_idx + 1:close_idx].strip()
        if inner and inner not in out:
            out.append(inner)
    return out


def _nth_sequence_has_marker(text: str, marker: str) -> bool:
    source = str(text or "")
    for match in re.finditer(r"\bnth\b", source):
        default, cursor = _term_after(source, match.end())
        if not default:
            continue
        sequence, _cursor = _term_after(source, cursor)
        if sequence and marker in sequence:
            return True
    return False


def _nth_map_terms(conclusion: str, goal_text: str) -> list[dict[str, Any]]:
    hypotheses = named_local_hypotheses(goal_text)
    formulas = named_local_formulas(goal_text)
    out: list[dict[str, Any]] = []
    source = str(conclusion or "")
    for match in re.finditer(r"\(\s*map\b", source):
        open_idx = match.start()
        close_idx = _matching_parenthesis_index(source, open_idx)
        if close_idx < 0:
            continue
        before = source[max(0, open_idx - 180):open_idx]
        if not re.search(r"\bnth\b", before):
            continue
        map_inner = source[open_idx + 1:close_idx].strip()
        words = _split_top_level_words(map_inner)
        if len(words) < 3 or words[0] != "map":
            continue
        list_term = words[-1]
        index, _end = _term_after(source, close_idx + 1)
        if not index:
            continue
        side_condition = f"0 <= {index} < {_size_application(list_term)}"
        evidence = _difference_index_evidence(index, list_term, hypotheses)
        visible_true = _matching_named_formula(formulas, side_condition)
        visible_false = _matching_named_formula(formulas, f"! ({side_condition})")
        if not visible_false:
            visible_false = _matching_named_formula(formulas, f"! {side_condition}")
        if visible_true:
            status = "visible_true"
            evidence = [visible_true]
        elif visible_false:
            status = "visible_false"
            evidence = [visible_false]
        elif evidence:
            status = "derivable_from_visible_linear_bounds"
        else:
            status = "not_established"
        item = _drop_empty({
            "source_list": _preview(list_term, limit=100),
            "index": _preview(index, limit=140),
            "side_condition": side_condition,
            "side_condition_status": status,
            "supporting_hypotheses": evidence,
        })
        if item not in out:
            out.append(item)
    return out


def _matching_named_formula(
    formulas: list[dict[str, str]],
    expected: str,
) -> str:
    wanted = _normalise_logic_term(expected)
    for item in formulas:
        if _normalise_logic_term(item.get("formula", "")) == wanted:
            return str(item.get("hypothesis") or "")
    return ""


def _matching_parenthesis_index(text: str, open_idx: int) -> int:
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "(":
        return -1
    depth = 0
    for idx in range(open_idx, len(text)):
        if text[idx] == "(":
            depth += 1
        elif text[idx] == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _term_after(text: str, start: int) -> tuple[str, int]:
    pos = start
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text):
        return "", pos
    if text[pos] == "(":
        close = _matching_parenthesis_index(text, pos)
        return (text[pos + 1:close].strip(), close + 1) if close >= 0 else ("", pos)
    match = re.match(r"[A-Za-z_][A-Za-z0-9_.'`{}&]*", text[pos:])
    if not match:
        return "", pos
    return match.group(0), pos + match.end()


def _difference_index_evidence(
    index: str,
    list_term: str,
    hypotheses: list[dict[str, str]],
) -> list[str]:
    parts = [part.strip() for part in _split_top_level(index, "-")]
    if len(parts) != 2:
        return []
    base, offset = parts
    offset_match = re.fullmatch(r"size\s+(.+)", offset.strip())
    if not offset_match:
        return []
    prefix = offset_match.group(1).strip()
    lower_name = ""
    upper_name = ""
    for item in hypotheses:
        relation = str(item.get("outer_relation") or "")
        left = _normalise_logic_term(str(item.get("left") or ""))
        right = _normalise_logic_term(str(item.get("right") or ""))
        if (
            relation == "<="
            and left == _normalise_logic_term(_size_application(prefix))
            and right == _normalise_logic_term(base)
        ):
            lower_name = str(item.get("hypothesis") or "")
        if (
            relation == "<"
            and left == _normalise_logic_term(base)
            and right == _normalise_logic_term(
                f"{_size_application(prefix)} + {_size_application(list_term)}"
            )
        ):
            upper_name = str(item.get("hypothesis") or "")
    return [name for name in (lower_name, upper_name) if name] if lower_name and upper_name else []


def _normalise_logic_term(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").replace("(", "").replace(")", ""))


def _size_drop_terms(text: str) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    source = str(text or "")
    for match in re.finditer(r"\bsize\s*\(", source):
        open_idx = match.end() - 1
        inner = _balanced_parenthesized_inner(source, open_idx)
        if not inner:
            continue
        compact = re.sub(r"\s+", " ", inner).strip()
        if not compact.startswith("drop "):
            continue
        args = _split_top_level_words(compact[len("drop "):].strip())
        if len(args) < 2:
            continue
        drop_amount = args[0].strip()
        list_term = " ".join(args[1:]).strip()
        if not drop_amount or not list_term:
            continue
        item = {
            "source_shape": _preview(f"size (drop {drop_amount} {list_term})", limit=120),
            "drop_amount": _preview(drop_amount, limit=80),
            "list_term": _preview(list_term, limit=80),
        }
        if item not in terms:
            terms.append(item)
    return terms


def _b2i_guards(text: str) -> list[str]:
    guards: list[str] = []
    source = str(text or "")
    for match in re.finditer(r"\bb2i\s*\(", source):
        guard = _balanced_parenthesized_inner(source, match.end() - 1)
        if guard:
            preview = _preview(guard, limit=140)
            if preview not in guards:
                guards.append(preview)
    return guards


def _balanced_parenthesized_inner(text: str, open_idx: int) -> str:
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "(":
        return ""
    depth = 0
    for idx in range(open_idx, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:idx].strip()
    return ""


def _split_top_level_words(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start: int | None = None
    for idx, char in enumerate(str(text or "")):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        if char.isspace() and depth == 0:
            if start is not None and start < idx:
                parts.append(text[start:idx].strip())
            start = None
            continue
        if start is None:
            start = idx
    if start is not None:
        tail = text[start:].strip()
        if tail:
            parts.append(tail)
    return parts


def _size_application(term: str) -> str:
    raw = str(term or "").strip()
    if not raw:
        return "size _"
    if re.match(r"^[A-Za-z_][A-Za-z0-9_'.{}&]*$", raw):
        return f"size {raw}"
    return f"size ({raw})"


def _ambient_memory_translation_surface(goal_text: str) -> dict[str, Any]:
    text = str(goal_text or "")
    decorations = sorted(set(re.findall(r"\{`?&?(?:\d+|[A-Za-z_][A-Za-z0-9_']*)\}", text)))
    decorated_terms = _decorated_memory_terms(text)
    backtick_memories = sorted(set(re.findall(r"`&(?:\d+|[A-Za-z_][A-Za-z0-9_']*)", text)))
    introduced_memories = sorted(set(re.findall(r"&(?:\d+|[A-Za-z_][A-Za-z0-9_']*)\s*:", text)))
    if not any((decorations, decorated_terms, backtick_memories, introduced_memories)):
        return {}
    state = (
        "introduced_memories_visible"
        if introduced_memories else
        "decorated_memory_terms_visible"
    )
    return _drop_empty({
        "state": state,
        "visible_decorations": decorations[:6],
        "decorated_terms": decorated_terms[:8],
        "visible_memory_names": backtick_memories[:6],
        "introduced_memory_bindings": introduced_memories[:6],
        "translation_facts": [
            "Decorations identify the program memory from which a term is read.",
            "Pretty-printer memory names and introduced proof-context names can differ.",
        ],
        "effect": (
            "Local claims in the pure tail depend on the currently introduced "
            "memory binders as well as displayed term decorations."
        ),
    })


def _decorated_memory_terms(text: str) -> list[str]:
    terms: list[str] = []
    pattern = re.compile(
        r"([A-Za-z_][A-Za-z0-9_.'`]*"
        r"(?:\s*\([^{}\n]{0,120}\))?)"
        r"\s*(\{`?&?(?:\d+|[A-Za-z_][A-Za-z0-9_']*)\})"
    )
    for match in pattern.finditer(str(text or "")):
        head = re.sub(r"\s+", " ", match.group(1)).strip()
        if not head or head in {"forall", "exists", "fun"}:
            continue
        term = _preview(f"{head}{match.group(2)}", limit=120)
        if term not in terms:
            terms.append(term)
    return terms


def _pure_tail_gap_analysis(goal_text: str, view: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(goal_text or "")
    update_keys = _map_update_keys(text)
    cons_heads = _cons_heads(text)
    gaps: list[dict[str, Any]] = []
    local_decomposition = _pure_tail_local_decomposition_gap_item(
        text,
        view=view,
    )
    if local_decomposition:
        gaps.append(local_decomposition)
    for key in update_keys:
        key_head = _first_tuple_component(key)
        if not key_head:
            continue
        for cons_head in cons_heads:
            if _has_visible_equality_path(text, key_head, cons_head):
                continue
            gaps.append(_pure_tail_gap_item(
                signal="map_key_membership_head_alignment",
                gap=(
                    "Map update key head and membership/list head are both "
                    "visible, but no equality path between them is visible."
                ),
                evidence=[
                    f"map update key: {_preview(key, limit=120)}",
                    f"update key head: {_preview(key_head, limit=80)}",
                    f"membership/list head: {_preview(cons_head, limit=80)}",
                ],
                view=view,
            ))
            break

    projection_terms = _projection_terms(text)
    if update_keys and projection_terms:
        key_heads = [
            _first_tuple_component(key)
            for key in update_keys
            if _first_tuple_component(key)
        ]
        for projection in projection_terms:
            if any(_has_visible_equality_path(text, projection, key) for key in key_heads):
                continue
            if projection in key_heads:
                continue
            gaps.append(_pure_tail_gap_item(
                signal="projection_key_alignment",
                gap=(
                    "Projection terms and map-update key heads coexist, but "
                    "a direct projection/key equality is not visible."
                ),
                evidence=[
                    f"projection term: {_preview(projection, limit=80)}",
                    "map update key heads: "
                    + ", ".join(_preview(key, limit=60) for key in key_heads[:3]),
                ],
                view=view,
            ))
            break

    return _dedupe_dicts(gaps)[:4]


def _pure_tail_gap_item(
    *,
    signal: str,
    gap: str,
    evidence: list[str],
    view: dict[str, Any],
) -> dict[str, Any]:
    checkpoints = _alignment_gap_checkpoint_refs(view)
    return _drop_empty({
        "signal": signal,
        "confidence": "medium",
        "gap": gap,
        "evidence": evidence,
        "observed_risk": "pure_tail_alignment_fact_not_visible",
        "reversible_to": checkpoints[:2],
    })


def _alignment_gap_checkpoint_refs(view: dict[str, Any]) -> list[dict[str, Any]]:
    refs = _pure_tail_checkpoint_refs(view)
    if not refs:
        return []

    def has_semantic(ref: dict[str, Any], wanted: str) -> bool:
        ids = set(_string_list(ref.get("semantic_id"))) | set(
            _string_list(ref.get("semantic_ids"))
        )
        return wanted in ids

    def add_unique(out: list[dict[str, Any]], ref: dict[str, Any] | None) -> None:
        if not ref:
            return
        key = (
            str(ref.get("checkpoint_id") or ""),
            str(ref.get("semantic_id") or ""),
            str(ref.get("label") or ""),
        )
        for existing in out:
            existing_key = (
                str(existing.get("checkpoint_id") or ""),
                str(existing.get("semantic_id") or ""),
                str(existing.get("label") or ""),
            )
            if existing_key == key:
                return
        out.append(ref)

    local = next(
        (
            ref for ref in refs
            if str(ref.get("undo_scope") or "") == "branch_local"
            or has_semantic(ref, "before_branch_work")
            or has_semantic(ref, "after_seq_opened")
        ),
        None,
    )
    seq_boundary = next(
        (
            ref for ref in refs
            if str(ref.get("undo_scope") or "") == "seq_local"
            or has_semantic(ref, "before_seq_cut")
            or has_semantic(ref, "pure_tail_alignment_gap")
        ),
        None,
    )
    out: list[dict[str, Any]] = []
    add_unique(out, local)
    add_unique(out, seq_boundary)
    for ref in refs:
        add_unique(out, ref)
    return out


def _pure_tail_local_decomposition_gap_item(
    text: str,
    *,
    view: dict[str, Any],
) -> dict[str, Any]:
    membership = _membership_decomposition_surface(text)
    if not membership:
        return {}
    source_shapes = set(_string_list(membership.get("source_shapes")))
    if not source_shapes & {"concat_membership", "map_membership", "filter_membership"}:
        return {}
    update_keys = _map_update_keys(text)
    projection_terms = _projection_terms(text)
    witnesses = _existential_witness_surface(text)
    if not (update_keys or projection_terms or witnesses):
        return {}
    local_refs = [
        item
        for item in _pure_tail_checkpoint_refs(view)
        if str(item.get("undo_scope") or "") in {"branch_local", "seq_local"}
    ]
    return _drop_empty({
        "signal": "local_membership_decomposition_available",
        "confidence": "medium",
        "gap": (
            "Visible membership sources carry local case facts that can expose "
            "the key, projection, or witness relation, but those source facts "
            "are not separated in the current context."
        ),
        "evidence": [
            "membership source shapes: " + ", ".join(sorted(source_shapes)),
            *(
                [
                    "existential binders: "
                    + ", ".join(
                        str(item.get("name") or "")
                        for item in _list(witnesses.get("binders"))[:3]
                        if isinstance(item, dict) and item.get("name")
                    )
                ]
                if witnesses.get("binders") else []
            ),
            *(
                [
                    "map update keys: "
                    + ", ".join(_preview(key, limit=60) for key in update_keys[:3])
                ]
                if update_keys else []
            ),
            *(
                [
                    "membership fact: "
                    + _preview(
                        str(_list(membership.get("membership_hypotheses"))[0]),
                        limit=120,
                    )
                ]
                if _list(membership.get("membership_hypotheses")) else []
            ),
        ],
        "observed_risk": "local_membership_source_not_exposed",
        "reversible_to": local_refs[:2],
    })


def _map_update_keys(text: str) -> list[str]:
    keys: list[str] = []
    for match in re.finditer(r"\.\[([^\]\n]{1,220})<-", str(text or "")):
        key = re.sub(r"\s+", " ", match.group(1)).strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def _map_lookup_terms(text: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r"\.\[([^\]\n]{1,220})\]", str(text or "")):
        term = re.sub(r"\s+", " ", match.group(1)).strip()
        if "<-" in term:
            term = term.split("<-", 1)[0].strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def _map_update_lookup_cases(text: str) -> list[dict[str, Any]]:
    update_keys = _map_update_keys(text)
    lookup_terms = _map_lookup_terms(text)
    key_heads = [
        _first_tuple_component(key)
        for key in update_keys
        if _first_tuple_component(key)
    ]
    cases: list[dict[str, Any]] = []
    for term in lookup_terms[:8]:
        if term in update_keys:
            cases.append({
                "lookup_term": term,
                "case": "update_key",
                "evidence": "The lookup term is itself an update key.",
            })
            continue
        visible_key = ""
        for key in [*update_keys, *key_heads]:
            if _has_visible_equality_path(text, term, key):
                visible_key = key
                break
        cases.append(_drop_empty({
            "lookup_term": term,
            "case": "same_key_visible" if visible_key else "key_case_unresolved",
            "matching_key": visible_key,
            "evidence": (
                "A visible equality/projection path connects this lookup to an update key."
                if visible_key else
                "No equality/projection path to an update key is visible in this goal text."
            ),
        }))
    return _dedupe_dicts(cases)


def _membership_hypotheses(text: str) -> list[str]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    facts: list[str] = []
    for idx, line in enumerate(lines):
        if "\\in" not in line and " in " not in line:
            continue
        start = idx
        if idx > 0 and re.match(r"^[A-Za-z_][A-Za-z0-9_']*\s*:$", lines[idx - 1]):
            start = idx - 1
        block = lines[start:idx + 1]
        for next_line in lines[idx + 1:idx + 7]:
            if re.match(
                r"^(Current goal|forall\b|exists\b|[A-Za-z_][A-Za-z0-9_']*\s*:)",
                next_line,
            ):
                break
            if len(" ".join(block)) > 260:
                break
            block.append(next_line)
            if any(token in next_line for token in ("=>", "/\\", "\\/", ")")) and (
                "\\in" not in next_line
            ):
                break
        window = " ".join(block)
        if "\\in" not in window and " in " not in window:
            continue
        preview = _preview(re.sub(r"\s+", " ", window), limit=220)
        if preview not in facts:
            facts.append(preview)
    return facts


def _membership_left_terms(text: str) -> list[str]:
    terms: list[str] = []
    pattern = re.compile(r"(\([^()\n]{1,120}\)|" + _EC_ATOM_RE + r")\s+\\in\s+")
    for match in pattern.finditer(str(text or "")):
        raw = match.group(1).strip()
        raw = re.sub(r"^[A-Za-z_][A-Za-z0-9_']*\s*:\s*", "", raw).strip()
        raw = raw.rstrip(",")
        if not raw or raw in {"forall", "exists"}:
            continue
        if raw.startswith("forall "):
            continue
        term = _preview(raw, limit=100)
        if term and term not in terms:
            terms.append(term)
    return terms


def _existential_binders(text: str) -> list[dict[str, str]]:
    binders: list[dict[str, str]] = []
    for match in re.finditer(
        r"\bexists\s*\(\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*([^)]+)\)",
        str(text or ""),
    ):
        binders.append({
            "name": match.group(1).strip(),
            "type": re.sub(r"\s+", " ", match.group(2)).strip(),
        })
    for match in re.finditer(r"\bexists\s+([A-Za-z_][A-Za-z0-9_']*)\b", str(text or "")):
        name = match.group(1).strip()
        if name and not any(item.get("name") == name for item in binders):
            binders.append({"name": name})
    return binders


def _witness_provider_hypotheses(text: str) -> list[dict[str, str]]:
    providers: list[dict[str, str]] = []
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if "forall" not in lower or "exists" not in lower:
            continue
        label_match = re.match(r"([A-Za-z_][A-Za-z0-9_']*)\s*:", line)
        providers.append(_drop_empty({
            "label": label_match.group(1) if label_match else "",
            "preview": _preview(re.sub(r"\s+", " ", line), limit=180),
        }))
    return _dedupe_dicts(providers)


def _cons_heads(text: str) -> list[str]:
    pattern = re.compile(r"(" + _EC_ATOM_RE + r")\s*::")
    heads: list[str] = []
    for match in pattern.finditer(str(text or "")):
        head = match.group(1).strip()
        if head and head not in heads:
            heads.append(head)
    return heads


def _projection_terms(text: str) -> list[str]:
    pattern = re.compile(r"(" + _EC_ATOM_RE + r"\.\`[0-9]+)")
    terms: list[str] = []
    for match in pattern.finditer(str(text or "")):
        term = match.group(1).strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def _first_tuple_component(text: str) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return ""
    if raw.startswith("(") and raw.endswith(")"):
        inner = raw[1:-1].strip()
        component = _split_first_top_level_component(inner)
        return component or inner
    return _split_first_top_level_component(raw) or raw


def _split_first_top_level_component(text: str) -> str:
    depth = 0
    for idx, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            return text[:idx].strip()
    return text.strip()


def _has_visible_equality_path(text: str, left: str, right: str) -> bool:
    left_variants = _term_variants(left)
    right_variants = _term_variants(right)
    if left_variants & right_variants:
        return True
    stripped_text = _strip_memory_annotations(str(text or ""))
    for lhs in left_variants:
        for rhs in right_variants:
            if _direct_equality_visible(text, lhs, rhs):
                return True
            if _direct_equality_visible(stripped_text, lhs, rhs):
                return True
            if _projection_tuple_equality_visible(stripped_text, lhs, rhs):
                return True
            if _projection_tuple_equality_visible(stripped_text, rhs, lhs):
                return True
    return False


def _term_variants(term: str) -> set[str]:
    raw = re.sub(r"\s+", "", str(term or "").strip())
    if not raw:
        return set()
    variants = {raw}
    stripped = _strip_memory_annotations(raw)
    if stripped:
        variants.add(stripped)
    projection_base = _projection_base(raw)
    if projection_base:
        variants.add(projection_base + ".`1")
        stripped_base = _strip_memory_annotations(projection_base)
        if stripped_base:
            variants.add(stripped_base + ".`1")
            variants.add(stripped_base)
    return {item for item in variants if item}


def _strip_memory_annotations(text: str) -> str:
    return re.sub(r"\{`?&?(?:\d+|[A-Za-z_][A-Za-z0-9_']*)\}", "", str(text or ""))


def _direct_equality_visible(text: str, left: str, right: str) -> bool:
    if not left or not right:
        return False
    compact = re.sub(r"\s+", "", str(text or ""))
    forward = f"{left}={right}"
    backward = f"{right}={left}"
    return forward in compact or backward in compact


def _projection_tuple_equality_visible(text: str, projection: str, head: str) -> bool:
    base = _projection_base(projection)
    if not base or not head:
        return False
    compact = re.sub(r"\s+", "", str(text or ""))
    return (
        f"{base}=({head}," in compact
        or f"({head}," in compact and f")={base}" in compact
    )


def _projection_base(term: str) -> str:
    text = str(term or "").strip()
    match = re.match(r"(.+)\.\`1$", text)
    return match.group(1) if match else ""


def _pure_tail_checkpoint_refs(view: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoints = _list(_dict(view.get("structural_checkpoints")).get("items"))
    preferred = []
    fallback = []
    for item in checkpoints:
        if not isinstance(item, dict):
            continue
        ref = _drop_empty({
            "checkpoint_id": item.get("checkpoint_id"),
            "semantic_id": item.get("semantic_id"),
            "semantic_ids": item.get("semantic_ids"),
            "label": item.get("label"),
            "undo_scope": item.get("undo_scope"),
            "restored_affordances": item.get("restored_affordances"),
            "submit": item.get("submit"),
        })
        scopes = set(_string_list(item.get("semantic_id"))) | set(
            _string_list(item.get("semantic_ids"))
        ) | {str(item.get("undo_scope") or "")}
        if scopes & {"before_seq_cut", "after_seq_opened", "branch_local", "seq_local"}:
            preferred.append(ref)
        else:
            fallback.append(ref)
    return (preferred + fallback)[:4]



def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


# Public name for cross-package consumers (surface_action_choices).
goal_operators = _goal_operators
