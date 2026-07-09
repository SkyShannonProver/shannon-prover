r"""Mechanism CORRECT — up-to-bad call-coherence flag.

Precision contract (from the step4_1 design audit):
  - FIRES on an up-to-bad postcondition (top-level ``\/ bad`` disjunct, relation may
    break) paired with a lockstep single-clause ``call (_: inv)``.
  - Does NOT fire on a pure-equivalence post (step3 shape: ``==> ={res}``).
  - Does NOT fire when ``bad`` appears only in IMPLICATION position inside an
    invariant/post (step4_bad1_lbad1 shape: ``(UFCMA.bad1{1} => exists ...)``).
  - Does NOT fire when the call is already the 2-clause up-to-bad form.
"""
from __future__ import annotations

from core.easycrypt.up_to_bad_coherence import (
    DECISION_CONTEXT_KEY,
    coherence_flag,
    is_lockstep_call,
    latest_relational_call,
    up_to_bad_names,
)

# ---- step4_1-shaped up-to-bad postconditions (relation may break on bad) --------
POST_NEG_GUARD = (
    "equiv[ G1.O ~ G2.O : ={glob A} ==> "
    "!(UFCMA.bad1 \\/ UFCMA.bad2){2} => ={res} ]"
)
POST_RHS_DISJUNCT = (
    "byequiv (_: ={arg} ==> res{1} => res{2} \\/ UFCMA.bad1{2} \\/ UFCMA.bad2{2})"
)
POST_BARE_DISJUNCT = "={res} \\/ bad1 \\/ bad2"

# ---- step3-shaped pure-equivalence postcondition (lockstep is correct) ----------
POST_PURE_EQUIV = "equiv[ M.f ~ M.g : ={glob A, x} ==> ={res, glob M} ]"

# ---- step4_bad1_lbad1-shaped: bad only in IMPLICATION position (legit lockstep) --
POST_BAD_IN_IMPL = (
    "equiv[ G.O ~ G.O : ={arg} ==> ={res} /\\ "
    "(UFCMA.bad1{1} => exists tt, mem tt UFCMA.log{2}) ]"
)

LOCKSTEP_CALL = "call (_: ={glob UFCMA} /\\ ={UFCMA.log})."
UPTOBAD_CALL = "call (_: UFCMA.bad1, ={glob UFCMA} /\\ ={UFCMA.log})."


def test_up_to_bad_names_neg_guard() -> None:
    names = up_to_bad_names(POST_NEG_GUARD)
    assert names == {"UFCMA.bad1", "UFCMA.bad2"}, names


def test_up_to_bad_names_rhs_disjunct() -> None:
    names = up_to_bad_names(POST_RHS_DISJUNCT)
    assert names == {"UFCMA.bad1", "UFCMA.bad2"}, names


def test_up_to_bad_names_bare_disjunct() -> None:
    names = up_to_bad_names(POST_BARE_DISJUNCT)
    assert names == {"bad1", "bad2"}, names


def test_pure_equiv_post_has_no_bad_names() -> None:
    assert up_to_bad_names(POST_PURE_EQUIV) == set()


def test_bad_in_implication_is_not_a_disjunct() -> None:
    # CRITICAL precision: `(bad1 => exists ...)` is implication-position bad-tracking,
    # NOT a relation-break disjunct. Must yield no active bad names.
    assert up_to_bad_names(POST_BAD_IN_IMPL) == set()


def test_is_lockstep_call_discriminator() -> None:
    assert is_lockstep_call(LOCKSTEP_CALL) is True
    assert is_lockstep_call(UPTOBAD_CALL) is False
    # comma INSIDE the invariant (e.g. a tuple/glob list) is top-level only when the
    # 2-clause separator; a parenthesised comma must not be mistaken for the clause sep.
    assert is_lockstep_call("call (_: ={glob (M,N)} /\\ ={x}).") is True


def test_CORRECT_fires_on_step4_1_shape() -> None:
    flag = coherence_flag(POST_NEG_GUARD, LOCKSTEP_CALL)
    assert flag is not None
    assert flag["key"] == DECISION_CONTEXT_KEY == "up_to_bad_call"
    assert flag["certified"] is False
    assert "UFCMA.bad1" in flag["active_bad_events"]
    # The surfaced text carries the exact spec phrasing + the up-to-bad candidate.
    assert "your `call (_: inv)` is lockstep" in flag["text"]
    # E2 (audit 2026-06-09): POST_NEG_GUARD carries BOTH bad1 and bad2, so the
    # candidate must cover both via the disjunctive up-to-bad clause — the old
    # `call (_: UFCMA.bad1, <inv>)` silently dropped bad2.
    assert "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>)" in flag["text"]
    assert "UFCMA.bad1" in flag["candidate"]
    assert "UFCMA.bad2" in flag["candidate"]


def test_CORRECT_fires_on_rhs_disjunct_shape() -> None:
    flag = coherence_flag(POST_RHS_DISJUNCT, LOCKSTEP_CALL)
    assert flag is not None
    assert flag["key"] == "up_to_bad_call"


def test_CORRECT_does_not_fire_on_pure_equiv_post() -> None:
    # step3 shape: lockstep call is the CORRECT move here.
    assert coherence_flag(POST_PURE_EQUIV, LOCKSTEP_CALL) is None


def test_CORRECT_does_not_fire_on_bad_implication_post() -> None:
    # step4_bad1_lbad1 shape: legitimate lockstep bad-tracking.
    assert coherence_flag(POST_BAD_IN_IMPL, LOCKSTEP_CALL) is None


def test_CORRECT_does_not_fire_when_call_already_uptobad() -> None:
    # The agent already used the 2-clause form — nothing to flag.
    assert coherence_flag(POST_NEG_GUARD, UPTOBAD_CALL) is None


def test_CORRECT_does_not_fire_when_inv_already_tracks_bad() -> None:
    # Lockstep call but the invariant already mentions the bad name -> precision skip.
    inv_call = "call (_: !UFCMA.bad1{2} /\\ ={UFCMA.log})."
    assert coherence_flag(POST_NEG_GUARD, inv_call) is None


# ---- E2 (audit 2026-06-09): the candidate + obligations must cover EVERY active --
# relation-break bad, never the sorted-first one only. With >1 bad the up-to-bad
# clause is their disjunction `(bad1 \/ bad2)`; single-bad wording is unchanged. ---

# A single-bad relation-break post (only bad1 in the `\/`): the candidate must keep
# the bare single-bad form `call (_: UFCMA.bad1, inv).` — NO disjunction wrapping.
POST_SINGLE_BAD = (
    "byequiv (_: ={arg} ==> res{1} => res{2} \\/ UFCMA.bad1{2})"
)


def test_E2_two_bad_candidate_covers_both_bads() -> None:
    # POST_NEG_GUARD carries bad1 AND bad2. The candidate + every obligation line
    # must mention both via the disjunctive clause — nothing silently dropped.
    flag = coherence_flag(POST_NEG_GUARD, LOCKSTEP_CALL)
    assert flag is not None
    assert flag["active_bad_events"] == ["UFCMA.bad1", "UFCMA.bad2"]
    # Candidate is the disjunctive up-to-bad clause covering both bads.
    assert flag["candidate"] == (
        "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), ={glob UFCMA} /\\ ={UFCMA.log})."
    )
    assert "UFCMA.bad1" in flag["candidate"]
    assert "UFCMA.bad2" in flag["candidate"]
    # The obligation text must NOT mention only the sorted-first bad: the negated
    # guard and the bad-clause in obligations (2)/(3) are the full disjunction.
    assert "`!(UFCMA.bad1 \\/ UFCMA.bad2)`" in flag["text"]
    assert "(UFCMA.bad1 \\/ UFCMA.bad2)`-preservation" in flag["text"]


def test_E2_single_bad_candidate_wording_unchanged() -> None:
    # Regression red line: a single active bad keeps the bare single-bad form — NO
    # `(...)` disjunction wrapping, identical to the pre-E2 text.
    flag = coherence_flag(POST_SINGLE_BAD, LOCKSTEP_CALL)
    assert flag is not None
    assert flag["active_bad_events"] == ["UFCMA.bad1"]
    assert flag["candidate"] == (
        "call (_: UFCMA.bad1, ={glob UFCMA} /\\ ={UFCMA.log})."
    )
    assert "call (_: UFCMA.bad1, <inv>)" in flag["text"]
    assert "`!UFCMA.bad1`" in flag["text"]
    # No spurious disjunction wrapping leaked into the single-bad path.
    assert "\\/" not in flag["candidate"]


# ============================================================================== #
# REAL-DATA precision (step4_1 turn_008 / step4_badi). The recognizer must harvest #
# the GENUINE up-to-bad shape and ONLY it: a name counts iff it is a `\/` disjunct  #
# whose disjunction has a relation-break partner (res/forged/={...}/inv ...).       #
# ============================================================================== #

# step4_1 turn_008 REAL post: `forged{1} => forged{2} \/ bad2 \/ bad1`. The `=>`
# CONSEQUENT is the disjunction `forged \/ bad2 \/ bad1`; `forged` is the relation-
# break partner, so {bad1, bad2} are the active bad events (`forged` is NOT a bad).
_STEP4_1_REAL_POST = "forged{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2}"

# step4_1 turn_008 REAL parenthesized pre-conjunct: `(bad1 \/ inv RO.m{1} RO.m{2} ...)`.
# The `inv ...` application is the relation-break partner, so {bad1} is harvested —
# this requires DESCENDING one paren level (the whole segment is a wrapped group).
_STEP4_1_REAL_PRE_CONJUNCT = (
    "(UFCMA.bad1{2} \\/ inv SplitC2.I1.RO.m{1} RO.m{2} SplitC2.I2.RO.m{1} "
    "SplitC2.I2.RO.m{2} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} "
    "BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} UFCMA.log{2})"
)

# step4_badi REAL byequiv post: bare consequent `... => badi{2}` (NO `\/`). This is
# lockstep bad-TRACKING, not an up-to-bad relation break -> harvest nothing.
_STEP4_BADI_REAL_POST = (
    "(let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) "
    "=> UFCMA_li.badi{2}"
)

# step4_badi REAL multi-glob lockstep call. The commas are INSIDE the `={...}` brace
# group (one clause), so this is single-clause lockstep, not the 2-clause up-to-bad.
_STEP4_BADI_REAL_CALL = (
    "call (_: ={glob BNR, glob ROIN.RO, glob SplitC2.I2.RO, glob SplitD.ROF.RO, "
    "UFCMA.cbad1, UFCMA.log, UFCMA_l.lbad1, Mem.log, Mem.lc} /\\ "
    "UFCMA_li.i{2} = nth0 /\\ "
    "UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2})).")


def test_up_to_bad_names_harvests_step4_1_post() -> None:
    # The `forged => forged \/ bad2 \/ bad1` shape -> {bad1, bad2}. (Before the fix
    # this ALSO captured `forged`, the relation term, on a false basis.)
    assert up_to_bad_names(_STEP4_1_REAL_POST) == {"UFCMA.bad1", "UFCMA.bad2"}


def test_up_to_bad_names_harvests_parenthesized_pre_conjunct() -> None:
    # `(bad1 \/ inv ...)` -> {bad1}. Requires descending one paren level AND
    # recognizing the `inv ...` application as the relation-break partner. (Before the
    # fix `_top_level_split` could not look inside the wrapping group -> ∅, a miss.)
    assert up_to_bad_names(_STEP4_1_REAL_PRE_CONJUNCT) == {"UFCMA.bad1"}


def test_up_to_bad_names_silent_on_bare_implication_consequent() -> None:
    # step4_badi `... => badi{2}`: a BARE consequent (single term, no `\/`) is NOT a
    # relation-break disjunction -> ∅. (Before the fix the lone term was harvested.)
    assert up_to_bad_names(_STEP4_BADI_REAL_POST) == set()


def test_is_lockstep_call_brace_aware() -> None:
    # Commas inside `={glob A, glob B}` are NOT clause separators -> lockstep=True.
    assert is_lockstep_call("call (_: ={glob A, glob B}).") is True
    # A REAL top-level comma (`bad, inv`) is the 2-clause up-to-bad form -> False.
    assert is_lockstep_call("call (_: bad1 \\/ bad2, inv).") is False
    # The real step4_badi multi-glob frame is single-clause lockstep.
    assert is_lockstep_call(_STEP4_BADI_REAL_CALL) is True


def test_up_to_bad_names_step4_1_pre_conjunct_does_not_overcapture_inv() -> None:
    # Precision: the `inv ...` relational predicate (an APPLICATION) is the relation
    # partner, never itself a bad event; only `bad1` is harvested.
    names = up_to_bad_names(_STEP4_1_REAL_PRE_CONJUNCT)
    assert "inv" not in names and names == {"UFCMA.bad1"}


def test_CORRECT_silent_on_step4_badi_bare_consequent_with_multiglob_call() -> None:
    # End-to-end #2 acceptance: step4_badi is silent for the RIGHT reason —
    # up_to_bad_names returns ∅ (bare consequent, no `\/`) AND is_lockstep_call
    # correctly returns True for the multi-glob call (so the silence is NOT a
    # mis-classified call). The flag is None because the post has no relation break.
    assert up_to_bad_names(_STEP4_BADI_REAL_POST) == set()
    assert is_lockstep_call(_STEP4_BADI_REAL_CALL) is True
    assert coherence_flag(_STEP4_BADI_REAL_POST, _STEP4_BADI_REAL_CALL) is None


# ============================================================================== #
# PRECISION HARDENING (2026-06-09). Two independent audits found `up_to_bad_names` #
# LOOSER than its docstring claimed — it over-harvested in three confirmed ways    #
# (one leaked on REAL step4_1 turn_005). Each over-harvest case below FAILS on the  #
# pre-hardening code and must now be ∅; the genuine fires must NOT regress.         #
# ============================================================================== #

# step4_1 turn_005 REAL post (flattened): a `forall (... bad1_R : bool ...)` binder
# introduces the local bool `bad1_R`, which then appears as `bad1_R \/ inv ...`. That
# disjunct is NOT a fireable bad event — it is a quantifier-bound local. The GENUINE
# bad here is the module-qualified `UFCMA.bad1` in the parenthesized `&&` conjunct
# `(!UFCMA.bad1{2} => ... inv ...)`. So the harvest must be {UFCMA.bad1}, NOT bad1_R.
_STEP4_1_TURN005_POST = (
    "(!UFCMA.bad1{2} => true /\\ (glob A){1} = (glob A){2} /\\ "
    "inv RO.m{1} RO.m{2} Mem.log{1} Mem.log{2} UFCMA.log{2}) && "
    "forall (result_L result_R : bool) (A_L : (glob A)) (ndec_R : int) "
    "(bad1_R : bool) (log_R : (nonce, tag) fmap) (m_R : (a, b) fmap), "
    "(!bad1_R => result_L = result_R /\\ A_L = A_L /\\ "
    "inv m_R m_R log_R log_R) => bad1_R \\/ inv m_R m_R log_R log_R"
)


def test_up_to_bad_names_excludes_forall_bound() -> None:
    # A `forall (... bad1_R : bool ...)` binder local that later appears as a
    # `bad1_R \/ inv ...` disjunct is a QUANTIFIED VARIABLE, not a bad event. It must
    # be stripped — only the genuine module-qualified `UFCMA.bad1` survives.
    # (Pre-hardening this harvested {UFCMA.bad1, bad1_R} — the real turn_005 leak.)
    names = up_to_bad_names(_STEP4_1_TURN005_POST)
    assert "bad1_R" not in names
    assert names == {"UFCMA.bad1"}, names


def test_up_to_bad_names_excludes_forall_bound_minimal() -> None:
    # Minimal binder-strip: a `forall`-bound `bad1_R` opposite an `inv ...` partner is
    # the ONLY flag in the disjunction -> after stripping the binder local, ∅.
    post = (
        "forall (result_L result_R : bool) (bad1_R : bool), "
        "(!bad1_R => result_L = result_R) => bad1_R \\/ inv m_R m_R"
    )
    assert up_to_bad_names(post) == set()


def test_up_to_bad_names_excludes_false_literal() -> None:
    # A boolean literal is a value, never a fireable event. (Pre-hardening this
    # harvested {'false'} because `_looks_like_event_name` accepted the bare token.)
    assert up_to_bad_names("inv x y \\/ false") == set()
    assert up_to_bad_names("={res} \\/ true") == set()


def test_up_to_bad_names_excludes_operator_head_in_negated_guard() -> None:
    # `! size A <= i ==> ! size A <= i`: the negated guard is an APPLIED operator +
    # comparison (`size A <= i`), NOT a bare boolean flag. A negated-guard bad must be
    # a bare flag identifier (`Mod.flag{2}`). (Pre-hardening the `!<name>` regex
    # captured only the head `size` and dropped ` A <= i`, mis-harvesting {'size'} —
    # the REAL step4_badi r2 turns ~011/013/014 carrier.)
    assert up_to_bad_names("! size A <= i ==> ! size A <= i") == set()
    # A genuine bare negated flag guard still fires (the relation RHS is the partner).
    assert up_to_bad_names("!UFCMA.bad1{2} => ={res}") == {"UFCMA.bad1"}


# ============================================================================== #
# NESTED / PROJECTION-ANNOTATED HARVEST (audit 2026-06-09, SPEC-C #1).            #
# The step4_1 Tree_0_1 lineage writes the SAME up-to-bad post with extra parens    #
# and a projection annotation; both renderings must harvest {bad1, bad2}. Before   #
# the fix BOTH were ∅ — the flagship false negative (scratch t18-41 silent for 24  #
# turns; resume hook sticky-fact never formed over the 104-turn lineage).          #
# ============================================================================== #

# The REAL committed byequiv of step4_1 Tree_0_1 (resume prefix L2, verbatim).
_STEP4_1_TREE01_BYEQUIV = (
    "byequiv (_: ={glob A} ==> (res{1} => ((res \\/ UFCMA.bad2) \\/ UFCMA.bad1){2}))."
)

# The rendered-goal form of the same post (step4_1 scratch Tree_0_1 t18-41).
_STEP4_1_TREE01_RENDERED = (
    "forged{1} => (forged{2} \\/ UFCMA.bad2{2}) \\/ UFCMA.bad1{2}"
)


def test_up_to_bad_names_harvests_projection_annotated_nested_byequiv() -> None:
    # `((res \/ bad2) \/ bad1){2}` — a projection-ANNOTATED nested disjunction
    # inside an implication consequent inside the byequiv parens. Must peel the
    # `(...){2}` group, descend the inner implication, and flatten the nested
    # disjunction. (Pre-fix: ∅ — the resume Tree_0_1 FN's proximate cause.)
    assert up_to_bad_names(_STEP4_1_TREE01_BYEQUIV) == {"UFCMA.bad1", "UFCMA.bad2"}


def test_up_to_bad_names_harvests_nested_paren_rendered_form() -> None:
    # `(forged{2} \/ bad2{2}) \/ bad1{2}` — the renderer's left-nested grouping of
    # the same disjunction. The relation partner (`forged`) sits INSIDE the inner
    # group; flattening must still see it. (Pre-fix: ∅ — scratch Tree_0_1 t18-41.)
    assert up_to_bad_names(_STEP4_1_TREE01_RENDERED) == {"UFCMA.bad1", "UFCMA.bad2"}


def test_nested_flag_only_disjunction_still_harvests_nothing() -> None:
    # Flattening must not weaken the relation-partner requirement: a nested
    # disjunction of ONLY flags has no relation-break partner -> ∅.
    assert up_to_bad_names("(bad1 \\/ bad2) \\/ bad3") == set()


# ---- HARD REGRESSION RED LINES (must stay ∅ after the nested-harvest fix) -------

# Implication-position bad-tracking, `bad1 => size-bound /\ exists ...` shape
# (synthetic: identifiers renamed from a held-out MAC corpus goal post; the
# goal shape — flag in implication position, no relation-break partner — is
# preserved verbatim).
_MAC_IMPL_POSITION_POST = (
    "UF.bad1{1} => size UF_l.lbad1{2} <= qmax /\\ "
    "exists (tt : tag * tag), (tt \\in UF_l.lbad1{2}) /\\ tt.`1 = tt.`2"
)

# step4_badi REAL equality-form bad line — coupled counters, not a relation break.
_BADI_EQUALITY = "UFCMA.cbad1{1} = UFCMA.cbad1{2}"

# step4_badi REAL quantifier-body disjunction — `=`-relation partner inside a
# quantified body over BOUND locals; must not be harvested.
_BADI_QUANT_BODY = (
    "forall (n1 : nonce), (n1 = p{2}.`1 \\/ (n1 \\in BNR.lenc{2})) => "
    "UFCMA_li.cbadi{2} = b2i (n1 < size UFCMA_l.lbad1{2})"
)


def test_red_line_implication_position_still_empty() -> None:
    assert up_to_bad_names(_MAC_IMPL_POSITION_POST) == set()


def test_red_line_badi_bare_implication_tail_still_empty() -> None:
    assert up_to_bad_names(_STEP4_BADI_REAL_POST) == set()


def test_red_line_badi_equality_form_still_empty() -> None:
    assert up_to_bad_names(_BADI_EQUALITY) == set()


def test_red_line_badi_quantifier_body_still_empty() -> None:
    assert up_to_bad_names(_BADI_QUANT_BODY) == set()


# ============================================================================== #
# is_lockstep_call: phoare bare-flag clause (audit 2026-06-09, SPEC-C #3).         #
# ============================================================================== #


def test_is_lockstep_call_rejects_bare_flag_phoare_clause() -> None:
    # `call (_: UFCMA.bad1).` is the ONE-SIDED phoare bad-preservation form (the
    # six step4_1 resume prefix calls at L63+), NOT a lockstep relational call.
    # Pre-fix this was True and coherence_flag assembled the absurd candidate
    # `call (_: UFCMA.bad2, UFCMA.bad1).` — a phoare argument as invariant.
    assert is_lockstep_call("call (_: UFCMA.bad1).") is False
    assert is_lockstep_call("call (_: UFCMA.bad1{2}).") is False
    # `call (_: true).` is a REAL lockstep form (boolean literal, not a flag).
    assert is_lockstep_call("call (_: true).") is True


def test_coherence_flag_never_promotes_phoare_arg_to_invariant() -> None:
    # Post admits `\/ bad2`, latest call is the phoare `call (_: UFCMA.bad1).` —
    # the flag must be silent, never `call (_: UFCMA.bad2, UFCMA.bad1).`.
    flag = coherence_flag("==> ={res} \\/ UFCMA.bad2", "call (_: UFCMA.bad1).")
    assert flag is None


# ============================================================================== #
# latest_relational_call (audit 2026-06-09, SPEC-C #2): the coherence check keys   #
# on the most recent RELATIONAL `call (_: ...)`, not the temporally last call.     #
# ============================================================================== #

_LOCKSTEP_INV_CALL = "call (_: inv RO.m{1} RO.m{2} UFCMA.log{2})."


def test_latest_relational_call_skips_lemma_application_call() -> None:
    # step4_1 resume Tree_0_1 prefix shape: three lockstep calls then a lemma-
    # application `call (equ_cc ...)`. The lemma call must not mask the lockstep.
    hist = [
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad1{2}).",
        _LOCKSTEP_INV_CALL,
        _LOCKSTEP_INV_CALL,
        _LOCKSTEP_INV_CALL,
        "exlim n{2} => n0.",
        "call (equ_cc n0 mr0 ms0).",
    ]
    assert latest_relational_call(hist) == _LOCKSTEP_INV_CALL


def test_latest_relational_call_skips_phoare_bad_preservation_calls() -> None:
    # step4_1 resume Tree_0_0 prefix shape: the 2-clause up-to-bad call followed by
    # six one-sided `call (_: UFCMA.bad1).` phoare preservation calls.
    two_clause = "call (_: UFCMA.bad1, inv RO.m{1} RO.m{2})."
    hist = [two_clause] + ["call (_: UFCMA.bad1)."] * 6
    assert latest_relational_call(hist) == two_clause


def test_latest_relational_call_empty_when_no_relational_call() -> None:
    assert latest_relational_call(["proc.", "call (equ_cc n0).",
                                   "call (_: UFCMA.bad1)."]) == ""


def test_up_to_bad_names_post_path_after_prompt_strip() -> None:
    # The rendered goal appends a REPL prompt line `[NNN|check]>` after `post`. Without
    # stripping it, the prompt glues onto the post's last disjunct
    # (`... \/ UFCMA.bad1{2}[472|check]>`), making it multi-token so its bad name is
    # dropped — the POST block alone then yielded only {bad2}. After the strip in
    # `_pre_post_relation_blocks`, the POST block alone yields {bad1, bad2}.
    from core.easycrypt.session_prover_workspace_view import (
        _pre_post_relation_blocks,
    )

    post_lines = [
        "post = forged{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2}",
        "[472|check]>",
    ]
    blocks = _pre_post_relation_blocks(post_lines)
    assert len(blocks) == 1
    assert "check]>" not in blocks[0]  # prompt stripped
    assert up_to_bad_names(blocks[0]) == {"UFCMA.bad1", "UFCMA.bad2"}


# ---- E1 (audit 2026-06-09): multi-conjunct outer block whose up-to-bad disjunct ---
#      is a SINGLE conjunct of an outer block (step4_1 resume Tree_0_0 t34) ----------

# The REAL step4_1 resume Tree_0_0 t34 `pre =` block, flattened. The whole big
# conjunction `(b0=b1 /\ ... /\ (UFCMA.bad1{2} \/ inv ...))` arrives as ONE conjunct
# of the outer block `(...) /\ UFCMA.bad1{2}`; the parenthesized up-to-bad disjunct
# `(UFCMA.bad1{2} \/ inv ...)` lives two conjunction levels deep.
_STEP4_1_T34_PRE_BLOCK = (
    "(b0{2} = b1{2} /\\ b{2} = b0{2} /\\ forged{2} = false /\\ b2{1} = b3{1} /\\ "
    "b1{1} = b2{1} /\\ (UFCMA.bad1{2} \\/ inv SplitC2.I1.RO.m{1} RO.m{2} "
    "SplitC2.I2.RO.m{1} SplitC2.I2.RO.m{2} Mem.log{1} Mem.log{2} Mem.lc{1} "
    "Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} UFCMA.log{2})) /\\ "
    "UFCMA.bad1{2}"
)


def test_up_to_bad_names_harvests_deeply_nested_pre_conjunct_t34() -> None:
    # E1 regression: `_harvest_from_segment`'s `else` branch must RE-SPLIT a
    # non-implication segment into its top-level conjuncts and recurse, or the
    # parenthesized `(UFCMA.bad1{2} \/ inv ...)` group — buried inside a big `/\`
    # conjunction that is itself one conjunct of `(...) /\ bad1` — is never
    # re-examined and the harvest stays ∅. (Pre-fix this returned set().)
    assert up_to_bad_names(_STEP4_1_T34_PRE_BLOCK) == {"UFCMA.bad1"}
