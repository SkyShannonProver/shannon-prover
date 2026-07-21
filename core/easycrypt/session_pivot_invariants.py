"""Relational-invariant and call-glob-invariant inspection engines (pivot_context / call-invariant surfaces).

Extracted verbatim from PivotStrategyPhase (session_hook_phases.py) — the
2,900-line inspect-engine god-class. Each function's first parameter is
named ``self`` ON PURPOSE: it receives the PivotStrategyPhase instance
(for ``self.session`` and the small shared helpers that stay on the
class), so the bodies are byte-identical to the original methods and the
panel-invariance guarantee holds. De-self-ifying the signatures into
explicit params is a follow-up, not part of this carve.
"""
from __future__ import annotations

import re

from typing import Any, Optional
from core.hooks.contract import CommitPhase, HookResult  # type: ignore


def try_relational_invariant(self, raw_goal: str,
                              h: Optional[DaemonHandle]) -> Optional[HookResult]:
    """Daemon-filtered *named coupling* call carrier — the field-correct
    successor to the bare ``={glob ...}`` frame.

    Discovers the named relational predicates in scope (``inv_cpa``-style),
    type-matches their parameters to the in-scope state fields, threads the
    ``{1}``/``{2}`` sides off the parameter names, and daemon-filters the
    instantiations. Surfaces 1-2 carriers that the daemon confirms *apply*
    (+ a count of signature matches that did not), as a revisable starting
    point. "Applies" is necessary, not sufficient: the agent confirms the
    coupling is right, adds side conditions, and backtrack-adjusts.
    """
    # Pure-static now (types from source, scope from the goal head); the
    # daemon handle `h` is no longer needed to resolve fields.
    if not raw_goal:
        return None
    # Mechanism CORRECT — compute the up-to-bad call-coherence signal FIRST,
    # so it cannot be shadowed by ANY early return below. Audit 2026-06-09:
    # the emit used to live only at the tail of the resolved-carrier success
    # path; `if not cands: return <palette>/None` (and the no-predicate /
    # non-pRHL returns) skipped it on exactly the frontiers that needed it —
    # the coherence fact is history-sticky and needs no resolved carrier.
    try:
        coh = self._up_to_bad_call_coherence(raw_goal)
    except Exception:
        coh = None

    def _with_coherence_only() -> Optional[HookResult]:
        """Fallback emit when the carrier pipeline has nothing: surface the
        coherence signal alone (flag-only), else stay silent as before."""
        if coh is None:
            return None
        coh_line, coh_rec = coh
        return HookResult(
            text=coh_line + "\n", layer=2, kind="recommendation",
            recommendations=[coh_rec])

    is_prhl = (("&1" in raw_goal and "&2" in raw_goal)
               or (" ~ " in raw_goal and "==>" in raw_goal))
    if not is_prhl:
        # A pure-logic subgoal mid-proof: no relational carrier applies, but
        # the sticky coherence fact (committed byequiv post + lockstep call)
        # may still be the one structural signal worth surfacing.
        return _with_coherence_only()
    try:
        from core.easycrypt.analysis.ec_relational_invariant import (
            relational_predicates, state_field_pool, typed_field_resolution)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
                relational_predicates, state_field_pool, typed_field_resolution)
        except Exception:
            return _with_coherence_only()
    try:
        preds = relational_predicates(self.session.dir)
        pool = state_field_pool(self.session.dir)
    except Exception:
        return _with_coherence_only()
    if not preds:
        return _with_coherence_only()

    # Resolve up to 2 predicates STATICALLY: types from the source field
    # pool, scope from the goal head EC already printed — no per-candidate
    # daemon probing. A predicate whose required field is out of scope here
    # resolves to None (its field is not on the goal head) and is skipped.
    # 1. Static-resolve anchored candidates (types from the source field
    #    pool, scope from the goal head) — instant, no probing. Collect a few
    #    so the optional verify below has spares after it drops the ones that
    #    do not apply. Require >=1 type-ANCHORED (exact-type, in-scope) slot:
    #    a predicate whose every slot is an un-anchored fmap menu (only the
    #    RO-map fallback applies) carries no type info — it is menu-noise.
    cands: list[tuple[str, dict[str, Any]]] = []
    not_typed = 0
    for pred in preds:
        # Cap the batch verify at 4 witnesses: a probe is ~1.5 s and does not
        # amortize, and `call_invariant_skeleton` also runs the glob producer,
        # so keep the combined inspect under the ~10 s latency budget.
        if len(cands) >= 4:
            break
        try:
            res = typed_field_resolution(pred, pool, raw_goal)
        except Exception:
            res = None
        anchored = res and any(m.get("filled") for m in (res.get("menus") or []))
        if res and anchored:
            cands.append((pred["name"], res))
        else:
            not_typed += 1
    if not cands:
        # No carrier type-resolves at this goal, but the shape vocabulary
        # needs no carrier — surface it alone so the agent still sees the
        # forms an invariant can take (this is the common call-frontier case).
        # The coherence signal needs no carrier either: append it here too
        # instead of dying in this early return (audit 2026-06-09).
        block = self._shape_palette_block(raw_goal)
        bare_lines: list[str] = []
        bare_recs: list[dict[str, Any]] = []
        if block:
            bare_lines.extend(block[0])
            bare_recs.append(block[1])
        if coh is not None:
            coh_line, coh_rec = coh
            bare_lines.append(coh_line)
            bare_recs.append(coh_rec)
        if bare_recs:
            return HookResult(
                text="\n".join(bare_lines) + "\n", layer=2,
                kind="recommendation", recommendations=bare_recs)
        return None

    # 2. Optional ONE batch verify (the only daemon touch): a predicate whose
    #    witness does not type-check here does not apply, so drop it. This
    #    removes the coarse fmap fallback's false positives — a non-RO `fmap`
    #    slot that statically can only offer the in-scope RO maps — WITHOUT
    #    per-candidate probing: one `batch_try` round-trip over the static
    #    witnesses, vs the old ~14 sequential probes. If the daemon is
    #    unavailable (or accepts none — e.g. a witness heuristic mispick),
    #    keep the static set and mark it unverified rather than lose carriers.
    verified = False
    if h is not None:
        # batch_try cannot be interrupted mid-call, so size it to the probe
        # budget remaining after any co-running producer (the glob skeleton
        # runs first on call_invariant_skeleton): ~1.5 s/probe + margin.
        import time as _time
        _fit = max(0, int((self._resolve_probe_deadline()
                           - _time.monotonic()) / 1.6))
        verify_cands = cands[:_fit]
        if verify_cands:
            try:
                verdicts = h.cli.batch_try(
                    h.dbe._session_id,
                    [r["witness"] for _n, r in verify_cands])
                kept = [verify_cands[i] for i, v in enumerate(verdicts)
                        if isinstance(v, dict) and v.get("accepted")]
                if kept:
                    not_typed += len(verify_cands) - len(kept)
                    cands, verified = kept, True
            except Exception:
                pass

    resolved = cands[:2]

    applies_note = (
        "A single batch check then confirmed the surfaced coupling(s) APPLY "
        "here (a type-correct witness type-checks as a call invariant); "
        if verified else
        "EC type-checks it when you commit; ")
    lines = [
        "\n[RELATIONAL-INVARIANT-SKELETON] Named coupling invariant(s), "
        "field-threaded by TYPE + SCOPE, statically. Each slot's fields are "
        "type-matched (source var types) and filtered to what is IN SCOPE at "
        "this goal (read off the goal head EC printed) — no per-candidate "
        "per-candidate EasyCrypt checks. " + applies_note + "The `{1}`/`{2}` sides + state fields "
        "are mechanical. This is a revisable starting point, NOT a claim it "
        "is the right/complete coupling: confirm the coupling, fill any typed "
        "menu by SEMANTICS, add the side conditions the obligations need, and "
        "backtrack-adjust if too weak/strong.",
    ]
    recs: list[dict[str, Any]] = []
    for i, (name, res) in enumerate(resolved):
        template = res.get("template") or res.get("witness", "")
        fully = bool(res.get("fully_determined"))
        lines.append(f"  {template}")
        menus = [m for m in (res.get("menus") or [])
                 if not m.get("filled") and len(m.get("fields") or []) > 1]
        menu_payload: list[dict[str, Any]] = []
        for m in menus:
            base = (m.get("param") or {}).get("base", "?")
            typ = (m.get("param") or {}).get("type", "?")
            menu_payload.append(
                {"slot": base, "type": typ, "fields": m["fields"]})
        if fully:
            lines.append(
                "  every slot is type-unique + in scope here — syntactically "
                "complete as a starting carrier (EC checks it on commit; "
                "still confirm the coupling + add side conditions).")
        else:
            lines.append(
                "  NOTE — `‹a | b | …›` is a MENU, not literal syntax: replace "
                "each `‹…›` with exactly ONE of the `|`-separated fields (do "
                "NOT paste `‹…›` or the `|` into a tactic). For a `{1}`/`{2}` "
                "pair use the same field on both sides unless the coupling is "
                "one-sided. Choose by SEMANTICS — the compiler does not pick "
                "among equally-typed fields. Not committable until every `‹…›` "
                "is filled.")
            example = res.get("witness")
            if example:
                lines.append(
                    "  e.g. ONE type-correct way to fill it (illustrative "
                    "format only — pick the menu fields by semantics, this is "
                    f"not a recommendation):\n      {example}")
        recs.append({
            "id": f"relational_invariant_skeleton.{i}",
            "kind": "call_invariant_skeleton",
            "producer": "ec_relational_invariant",
            "action": template,
            "committable": fully,
            "verified": ("daemon_accepted_on_current_goal" if verified
                         else "unverified_suggestion"),
            "typed_menus": menu_payload,
            "derivation": (
                f"named coupling `{name}`: each slot type-matched to the "
                "in-scope state fields (source var types), the {{1}}/{{2}} "
                "sides read off its parameter names, and out-of-scope fields "
                "dropped by reading the goal head (no preflight needed); equally-typed "
                "in-scope fields left as menus"
                + (" — one batch check confirmed a witness applies here"
                   if verified else "")),
            "guarantee": (
                "a type-correct instantiation of this coupling type-checks "
                "as a call invariant here (one batch check confirmed it "
                "applies); the compiler did TYPE + SCOPE matching ONLY — not "
                "a claim it is the correct/complete coupling, and it does not "
                "choose among equally-typed fields (those stay menus, your "
                "pick is checked on commit)"
                if verified else
                "the fields are type-correct (source types) and in scope at "
                "this goal (goal head) — assembled STATICALLY, not "
                "daemon-checked: the manager asks EC to verify it when you commit. The "
                "compiler did TYPE + SCOPE matching ONLY — not a claim it is "
                "the correct/complete coupling, and it does not choose among "
                "equally-typed fields (those stay menus)"),
            "why": (
                f"`{name}`'s parameter types match the in-scope state fields."),
        })
    if not_typed:
        lines.append(
            f"  ({not_typed} other named predicate(s) examined are not in "
            "scope / type-match at this call.)")

    # Inductive side-conditions: a `call (_: <inv>)` over an adversary that
    # queries a random oracle with fresh keys is usually NOT inductive unless
    # <inv> also pins each queried oracle's DOMAIN to a tracked "used" set.
    # Surface the structural ingredients (in-scope RO maps + tracked sets) and
    # the `dom ⊆ used` idiom; the RO↔set pairing / key decomposition / side
    # are the agent's semantic pick (family-agnostic — see the miner docstring).
    try:
        from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
            ro_domain_side_conditions)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
                ro_domain_side_conditions)
        except Exception:
            ro_domain_side_conditions = None  # type: ignore
    sidecond = None
    if ro_domain_side_conditions is not None:
        try:
            sidecond = ro_domain_side_conditions(self.session.dir, raw_goal)
        except Exception:
            sidecond = None
    if sidecond:
        lines.append(
            "\n  [INDUCTIVE SIDE-CONDITIONS — candidates] A `call (_: <inv>)` "
            "over an adversary that queries a random oracle with fresh keys is "
            "usually NOT inductive unless `<inv>` also pins each queried "
            "oracle's DOMAIN to a tracked \"used\" set the game maintains. For "
            "each RO map the coupling above does NOT already pin (commonly an "
            "auxiliary / one-sided oracle), add a conjunct of the shape:")
        lines.append("      " + sidecond["shape"])
        lines.append(
            "    RO maps on the goal head: " + ", ".join(sidecond["ro_maps"]))
        lines.append(
            "    tracked \"used\" sets in scope: "
            + ", ".join(sidecond["used_lists"]))
        lines.append(
            "    These are CANDIDATES — pick the RO↔set pairing, the key "
            "decomposition (the key may be a tuple; a component is what's "
            "tracked), and the side (`{1}`/`{2}`) by SEMANTICS. The compiler "
            "points at the ingredients + the idiom; it asserts no specific "
            "conjunct.")
        recs.append({
            "id": "relational_invariant_skeleton.side_conditions",
            "kind": "call_invariant_skeleton",
            "producer": "ec_relational_invariant",
            "action": sidecond["shape"],
            "committable": False,
            "verified": "structural_candidate",
            "ro_maps": sidecond["ro_maps"],
            "used_sets": sidecond["used_lists"],
            "derivation": (
                "RO `.m` maps on the goal head x list/fset-typed tracked sets "
                "in scope; the domain-containment idiom a call invariant needs "
                "to be inductive when the adversary queries the oracle with "
                "fresh keys"),
            "guarantee": (
                "structural ingredients only — the in-scope RO maps + tracked "
                "sets plus the `dom ⊆ used` shape; NOT a checked conjunct. The "
                "RO↔set pairing, key decomposition, and side are the agent's "
                "semantic pick"),
            "why": (
                "a call invariant over an RO-querying adversary is rarely "
                "inductive unless it constrains the queried oracle's domain to "
                "a tracked set"),
        })

    # Shape vocabulary (lamp b) — surface the in-scope invariant forms. See
    # _shape_palette_block; it needs no resolved carrier.
    block = self._shape_palette_block(raw_goal)
    if block:
        lines.extend(block[0])
        recs.append(block[1])

    # Mechanism CORRECT — up-to-bad call coherence (flag-only). If the upstream
    # post admits a `\/ bad` disjunct but the committed call is lockstep, append
    # the up-to-bad `call (_: bad, inv)` candidate as an UNCERTIFIED suggestion.
    # (`coh` was computed at the top of this method, before any early return.)
    if coh is not None:
        coh_line, coh_rec = coh
        lines.append(coh_line)
        recs.append(coh_rec)

    return HookResult(
        text="\n".join(lines) + "\n", layer=2, kind="recommendation",
        recommendations=recs,
        # `evidence` buckets are list[dict] (see _record_pivot_tool_view);
        # carry the static-assembly diagnostic as a proper evidence item,
        # not as bare scalars (a bool/int here is non-iterable downstream).
        evidence={"static": [{
            "id": "relational_invariant_skeleton.static",
            "assembled": "statically",
            "predicates_examined": len(preds),
        }]})


def shape_palette_block(
    self, raw_goal: str
) -> "Optional[tuple[list[str], dict[str, Any]]]":
    """Lamp (b): the invariant-shape vocabulary block for the call-invariant
    skeleton inspection.

    Pure vocabulary from the in-scope named predicates — it needs NO resolved
    carrier, so it is surfaced both on the success path and when no relational
    carrier type-resolves at this goal (the common call-frontier case, which
    is exactly when the agent most needs to see the available forms). Shows,
    from THIS development's own predicates, that an invariant conjunct can be a
    guarded implication / size-or-count bound / domain fact — not only an
    equality. Possibility space, not a recommendation.
    """
    try:
        from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
            invariant_shape_palette)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
                invariant_shape_palette)
        except Exception:
            return None
    try:
        palette = invariant_shape_palette(self.session.dir, raw_goal)
    except Exception:
        palette = None
    if not (palette and palette.get("classes")):
        return None
    shape_label = {
        "guarded_implication": "guarded implication (guard => relation)",
        "size_or_count_bound": "size / count bound",
        "domain_membership": "domain membership",
        "relational_equality": "relational equality",
    }
    lines = [
        "\n  [INVARIANT SHAPE VOCABULARY] Invariant conjuncts in this "
        "development are written in these forms (examples are real in-scope "
        "predicates, NOT a recommendation — an invariant is not limited to "
        "equalities):"
    ]
    example_lines: list[str] = []
    for cls, items in palette["classes"].items():
        ex = "; ".join(
            str(it.get("name")) + ": " + str(it.get("shape"))
            for it in items[:2])
        example_lines.append(shape_label.get(cls, cls) + " — " + ex)
    for el in example_lines:
        lines.append("    - " + el)
    # The agent-facing view renders ONLY `why` for this item — the rich
    # `text`/`lines` above are dropped at the managed-protocol boundary. So
    # the concrete in-scope predicates (the actually-useful payload, e.g.
    # `inv_lbad1_i: uniq lenc /\ size lbad1 <= ...`) MUST be embedded in
    # `why`, else the agent sees only a generic meta-note and the real
    # named predicates never reach it. (Empirically: on step4_badi the agent
    # got the meta-note, did not see inv_lbad1_i, and spent ~3min
    # re-deriving the goal by hand.)
    _vocab = " | ".join(el[:240] for el in example_lines)
    # #11: lead with the named predicates that mention THIS goal's state, so
    # the relevant one (e.g. `inv_lbad1_i`) is not buried in the long vocab
    # prose (empirically the agent pulled this topic but missed it). Factual
    # ("these mention your state"), not a recommendation to use any one.
    relevant_names: list[str] = []
    seen_rel: set[str] = set()
    for _items in palette["classes"].values():
        for _it in _items:
            _n = str(_it.get("name") or "")
            if _it.get("relevant") and _n and _n not in seen_rel:
                seen_rel.add(_n)
                relevant_names.append(_n)
    relevant_lead = (
        "Named predicates that mention your goal's state (lookup_symbol for "
        "each definition): " + ", ".join(relevant_names[:6]) + ". "
    ) if relevant_names else ""
    why = (
        relevant_lead
        + "No mechanical `={glob}` frame applies at this call — build the call "
        "invariant from THIS development's own in-scope predicates (an "
        "invariant conjunct can be a guarded implication / size-or-count "
        "bound / domain fact, not only an equality). In-scope forms + named "
        "predicates (use lookup_symbol for the full definition of any): "
        + _vocab)
    if relevant_lead:
        lines.insert(1, "    [relevant to your goal] named predicates over "
                        "your state: " + ", ".join(relevant_names[:6]))
    rec = {
        "id": "invariant_shape_palette",
        "kind": "call_invariant_skeleton",
        "producer": "ec_relational_invariant",
        "committable": False,
        "verified": "vocabulary_examples",
        "shape_classes": sorted(palette["classes"].keys()),
        "relevant_named_predicates": relevant_names[:8],
        "named_predicates": _vocab,
        "guarantee": (
            "possibility space only — real in-scope predicates grouped by "
            "form so the shapes are visible; asserts no specific conjunct"),
        "why": why,
    }
    return lines, rec


def try_call_glob_invariant(self, raw_goal: str,
                             h: Optional[DaemonHandle]) -> Optional[HookResult]:
    """Mechanically synthesize the ``={glob <shared oracle modules>}`` frame
    of a ``call (_: <inv>)`` obligation invariant.

    Compiler/agent boundary: the compiler emits ONLY the mechanical glob
    frame (the in-scope ``declare module`` set, daemon-filtered so the
    called adversary drops out); the agent extends it with the semantic
    conjuncts the spawned obligations need (key/state correspondences,
    set-membership, win-implications).
    """
    if not raw_goal:
        return None
    is_prhl = (("&1" in raw_goal and "&2" in raw_goal)
               or (" ~ " in raw_goal and "==>" in raw_goal))
    if not is_prhl:
        return None
    try:
        from core.easycrypt.analysis.ec_call_glob_invariant import (
            declared_abstract_modules, glob_modules_from_goal,
            maximal_accepted_glob,
            render_call_glob_tactic, render_glob_invariant)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_call_glob_invariant import (  # type: ignore
                declared_abstract_modules, glob_modules_from_goal,
                maximal_accepted_glob,
                render_call_glob_tactic, render_glob_invariant)
        except Exception:
            return None
    try:
        mods = declared_abstract_modules(self.session.dir)
    except Exception:
        mods = []
    # `declare module` misses the CONCRETE shared oracle/state modules threaded
    # through the goal's call expressions (functor args like Log/LRO in `Log(LRO)`),
    # which are exactly what a `call (_: ={glob ...})` frame must keep synchronized.
    # Union them in (excluding the called adversary roots — the call rule forbids
    # `={glob A}`); every candidate is daemon-filtered below, so this cannot surface
    # a false frame (panel audit: call_invariant_skeleton emitted NO_GLOB on goals
    # whose real frame is over concrete functor modules).
    try:
        _seen_names = {str(m.get("name") or "") for m in mods}
        for gm in glob_modules_from_goal(
                raw_goal, exclude=self._called_adversary_roots(raw_goal)):
            if gm["name"] and gm["name"] not in _seen_names:
                _seen_names.add(gm["name"])
                mods.append(gm)
    except Exception:
        pass
    if not mods:
        return HookResult(
            text=("\n[CALL-INVARIANT-SKELETON/NO_MODULES] No abstract "
                  "`declare module` is in scope; no mechanical `={glob ...}` "
                  "frame applies. Synthesize the call invariant from the "
                  "program state directly.\n"),
            layer=3, kind="recommendation", recommendations=[])
    if h is None:
        cand = render_call_glob_tactic([m["name"] for m in mods])
        return HookResult(
            text=("\n[CALL-INVARIANT-SKELETON/DAEMON_UNAVAILABLE] candidate "
                  "glob frame (NOT daemon-filtered; the called adversary may "
                  f"need removing):\n  {cand}\n"),
            layer=3, kind="recommendation",
            evidence={"context": [{
                "id": "context.call_invariant_skeleton.no_daemon",
                "producer": "ec_call_glob_invariant",
                "candidate_modules": [m["name"] for m in mods]}]})

    probe_trace: list[dict[str, Any]] = []
    # Static cut (no probe): the called adversary's own `={glob A}` is always
    # rejected, so drop the callee module(s) read off the goal's call
    # statement instead of paying a guaranteed-reject singleton probe.
    _called = self._called_adversary_roots(raw_goal)
    if _called:
        mods = [m for m in mods
                if str(m.get("name") or "") not in _called] or mods
    # A probe is ~1.5 s of EC compute (no batch amortization) and this glob
    # producer co-runs with the relational one on `call_invariant_skeleton`,
    # so bound it both ways: cap the modules scanned (the singleton phase;
    # the union refinement still runs in full, so the returned glob stays
    # daemon-verified) and short-circuit probes past the wall-clock deadline.
    import time as _time
    _probe_deadline = self._resolve_probe_deadline()
    mods = mods[:self._INSPECT_PROBE_CAP]

    def _probe(tac: str) -> dict[str, Any]:
        if _time.monotonic() + self._PROBE_EST_S > _probe_deadline:
            return {"accepted": False, "error": "inspect preflight budget exhausted"}
        try:
            r = h.cli.try_tactic(h.dbe._session_id, tac)
        except Exception as exc:
            probe_trace.append({"tactic": tac, "accepted": False,
                                "error": f"{type(exc).__name__}: {exc}"})
            return {"accepted": False, "error": str(exc)}
        acc = bool(r.get("accepted"))
        probe_trace.append({"tactic": tac, "accepted": acc,
                            "error": (str(r.get("error"))[:120]
                                      if r.get("error") else "")})
        return {"accepted": acc, "error": r.get("error")}

    accepted = maximal_accepted_glob(mods, _probe)
    if not accepted:
        return HookResult(
            text=("\n[CALL-INVARIANT-SKELETON/NO_GLOB] No `={glob X}` over "
                  "the in-scope abstract modules is accepted at this call. "
                  "The invariant is purely semantic here — synthesize it "
                  "from the program/oracle state.\n"),
            layer=3, kind="recommendation", recommendations=[],
            evidence={"preflight": probe_trace})

    tactic = render_call_glob_tactic(accepted)
    inv = render_glob_invariant(accepted)
    return HookResult(
        text=(
            "\n[CALL-INVARIANT-SKELETON] Mechanical glob frame of the call "
            f"invariant (daemon-confirmed to apply):\n  {tactic}\n"
            f"  synchronized shared abstract modules: {', '.join(accepted)}\n"
            "  MECHANICAL frame only: it type-checks and spawns the oracle "
            "obligations, but is NOT a complete invariant. Extend it with "
            "the semantic conjuncts the obligations need, e.g. "
            f"`call (_: {inv} /\\ <your conjuncts>).`\n"),
        layer=2, kind="recommendation",
        recommendations=[{
            "id": "call_invariant_skeleton.mechanical.0",
            "kind": "call_invariant_skeleton",
            "producer": "ec_call_glob_invariant",
            "action": tactic,
            "why": (
                f"Shared abstract oracle modules {', '.join(accepted)} must "
                "stay synchronized across the adversary call; mechanical "
                "glob frame, daemon-confirmed to apply."),
            "action_type": "strategy_hint",
            "confidence": "mechanical_skeleton_applies",
            "derivation": (
                "mechanical glob frame: in-scope `declare module` set, "
                "daemon-filtered to the maximal `={glob ...}` the call rule "
                "accepts (the called adversary drops out automatically)"),
            "verified": "mechanical_skeleton_applies",
            "guarantee": (
                "type-checks and spawns the oracle obligations on the "
                "current goal; NOT a complete invariant and NOT a closer — "
                "extend with semantic conjuncts; reversible"),
            "evidence_refs": ["preflight.call_invariant_skeleton"],
            "metadata": {
                "extend_required": True,
                "submit": {"intent": "commit_tactic",
                           "payload": {"tactic": tactic}}},
        }],
        evidence={
            "deterministic": [{
                "id": "det.call_invariant_skeleton",
                "producer": "ec_call_glob_invariant",
                "declared_modules": [m["name"] for m in mods],
                "accepted_glob_modules": accepted}],
            "preflight": probe_trace},
        notes=[{
            "code": "call_invariant_skeleton.mechanical",
            "message": ("Compiler emits only the mechanical `={glob ...}` "
                        "frame; the semantic conjuncts are the agent's to "
                        "add.")}])
