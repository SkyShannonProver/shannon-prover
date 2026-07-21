"""Static reference: valid argument forms for EC tactics that have
multiple forms.

Purpose: when the classifier fires a SYNTAX-class label (arg count,
argument form, memory annotation, unknown identifier), agent needs to
know the VALID alternative forms without re-deriving from EC error
messages. This reference lists them.

Observed failure modes:
- used `.main(tt)` when the procedure expected unit via empty parentheses
- used `call (_: Inv)` when a named equiv handle already matched
- used `apply pr_RO_FinRO_D` when the section-exported lemma needed explicit arguments
- used `conseq (_: X{hr})` instead of side-indexed memories such as `{1}`/`{2}`

All four are "agent knows tactic, doesn't know the specific form". This
module encodes the forms returned by the typed `tactic_forms` context intent.

Public API:
    get_forms(name: str) -> Optional[TacticForms]
    format_forms(forms: TacticForms, mode: str = "") -> str
    normalize_proof_mode(mode: str = "", goal_text: str = "") -> str
    list_all() -> list[str]                      # all covered tactic names
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from core.easycrypt.analysis.ec_goal_parser import classify_goal


@dataclass
class TacticForm:
    syntax: str          # e.g. "call LEMMA."
    use_when: str        # 1-line guidance
    example: str         # concrete example
    note: str = ""       # optional caveat
    modes: tuple = ()    # proof modes this form is FOR ("pRHL"/"phoare"/"hoare");
                         # empty = applies to all. When the goal mode is known,
                         # forms for other modes are not applicable and are omitted.


@dataclass
class TacticForms:
    name: str
    forms: list[TacticForm]
    common_mistake: str = ""    # the #1 trap we've seen
    see_also: list[str] = None  # related tactic names


_FORMS: dict[str, TacticForms] = {
    # -----------------------------------------------------------------
    "call": TacticForms(
        name="call",
        forms=[
            TacticForm(
                syntax="call LEMMA.",
                use_when="An equiv lemma already proves the procedure correspondence "
                         "you need. This is the preferred form when available — EC "
                         "closes the whole adversary/oracle call in one step.",
                example="call H_proc.    (* uses a pre-declared equiv handle *)",
                note="EC unifies the pRHL call's LHS/RHS procedure targets against "
                     "LEMMA's statement. If that succeeds, the call is fully handled.",
            ),
            TacticForm(
                syntax="call (_: INVARIANT).",
                use_when="No pre-existing equiv lemma matches — you must provide the "
                         "oracle invariant manually. EC generates oracle-equiv subgoals "
                         "(one per oracle procedure the adversary may call).",
                example="call (_: ={Mem.k, Mem.log} /\\ StLSke.gs{1} = RO.m{2}).",
                note="Two pre-flight checks before writing the invariant: "
                     "(a) If a surfaced named equiv lemma already proves this "
                     "correspondence, prefer "
                     "Form 1 (`call LEMMA.`) instead of re-deriving via invariant. "
                     "(b) For an outer call to an abstract adversary's main (e.g. "
                     "`A.main`, `BNR_Adv(A).main`), do NOT include `={glob A}` in the "
                     "invariant. EC handles glob A implicitly via the abstract module's "
                     "frame condition; including it explicitly causes the unifier to fail "
                     "and `call` reports 'no effect'. Use `byequiv (_: ={glob A} ==> ={res})` "
                     "to thread it via the precondition instead, then write the invariant "
                     "WITHOUT `={glob A}`.",
            ),
            TacticForm(
                syntax="call (_: BAD_EVENT, INVARIANT).",
                use_when="Up-to-bad reasoning: the adversary MAY trigger a bad event, "
                         "and you want to bound the probability of disagreement by "
                         "`Pr[bad]`. Generates both the oracle-equiv subgoals under "
                         "`!BAD_EVENT` AND the losslessness subgoals when BAD_EVENT "
                         "holds.",
                example="call (_: UFCMA.bad1, ={Mem.k, glob A} /\\ ...).",
            ),
            TacticForm(
                syntax="call{1} (_: PRE ==> POST). / call{2} (_: PRE ==> POST).",
                use_when="One-sided call: the LHS (or RHS) has a procedure call that "
                         "the other side doesn't. Typically used inside a `seq K L : inv` "
                         "suffix where programs have diverged. PRE/POST are hoare-style "
                         "on the one side only.",
                example="call{1} (_: true ==> true).    (* discharge LHS-only call *)",
                note="Commonly paired with `islossless` to prove the PRE ==> true branch.",
            ),
            TacticForm(
                syntax="call (_: PRE ==> POST).",
                use_when="One-sided `phoare` call under a `[<=]` bound, especially a "
                         "`Bound : [<=] 1%r` residual after a probability split. "
                         "Use the hoare-style pre/post form when there is no RHS/LHS "
                         "side annotation.",
                example="call (_: true ==> true).",
                note="Do not read `call (_: true).` and `call (_: true ==> true).` "
                     "as equivalent here. Under one-sided bounds, the shorter form "
                     "can fail because the bound direction and hoare postcondition "
                     "are not made explicit.",
            ),
            TacticForm(
                syntax=(
                    "exlim e1{side}, e2{side} => x1 x2; "
                    "call (LEMMA x1 x2 ...)."
                ),
                use_when="The named equiv lemma has UNIVERSAL PARAMETERS that can't be "
                         "inferred from the call-site alone. Common for local equivs that "
                         "parameterize over nonces / fmaps / memory snapshots (e.g. "
                         "`local equiv foo n0 mr0 ms0 : ...` has 3 params). EC will error "
                         "with `cannot infer all placeholders` if you use Form 1 here. "
                         "When the parameter values are side-qualified program "
                         "expressions, first lift them into logical names with `exlim`, "
                         "then call the fully applied lemma.",
                example="exlim n{2}, RO.m{1}, ST.m{1} => n0 ro0 st0; "
                        "call (bridge_equiv n0 ro0 st0).",
                note="Check the exact declaration first to see how many universal "
                     "parameters the equiv carries — count tokens between `equiv LEMMA` and the first "
                     "`:`. Direct `ecall (LEMMA _ arg2 ...)` is an alternate EC form, "
                     "but it is syntax-sensitive for side-qualified program expressions; "
                     "prefer exlim/call when the arguments come from the current program "
                     "state.",
            ),
        ],
        common_mistake="Three traps cluster on `call`. "
                      "(1) Using Form 2 (`call (_: Inv)`) when a named equiv already "
                      "proves the correspondence — re-proves everything from scratch "
                      "and fans out subgoals per oracle. Prefer a surfaced named equiv "
                      "that matches the current procedures before writing an invariant. "
                      "(2) Using Form 1 (`call LEMMA.`) on an equiv with universal "
                      "parameters — EC errors `cannot infer all placeholders`. Fix is "
                      "Form 5 above: lift program expressions with `exlim`, then call "
                      "the fully applied lemma. Check the exact declaration before the "
                      "first call on a new lemma name. "
                      "(3) `call` reports 'no effect' (tactic accepted, state unchanged). "
                      "The most common cause is NOT a wrong invariant — it's that LHS/RHS "
                      "bottoms aren't both a single trailing `<@` call. EC's `call` "
                      "requires both sides to end with exactly one procedure call. If "
                      "either side has trailing assignments, samples, or other statements, "
                      "consume them FIRST: use `wp` to absorb assignments below the call; "
                      "use `sp` to absorb assignments above the call; use `seq K 0 : (Inv)` "
                      "/ `seq 0 K : (Inv)` to align asymmetric prefixes. Re-try `call` only "
                      "after both sides are at single-call form. (If `call` still says "
                      "'no effect' after alignment, also recheck Form 2's note above: did "
                      "you accidentally include `={glob A}` for an abstract adversary?) "
                      "(4) In one-sided `phoare [<=] 1%r` residuals, `call (_: true).` "
                      "can be the wrong form; use the hoare-style `call (_: true ==> true).` "
                      "when the current goal is a single-program call obligation.",
        see_also=["apply", "byequiv"],
    ),

    # -----------------------------------------------------------------
    "ecall": TacticForms(
        name="ecall",
        forms=[
            TacticForm(
                syntax="ecall (LEMMA arg1 arg2 ...).",
                use_when="A named hoare/equiv lemma proves the trailing procedure "
                         "call, and its explicit arguments should be supplied from "
                         "the current program state. EC uses the current call-site "
                         "to instantiate the procedure argument relation.",
                example="ecall (f_ok1 x).    (* EasyCrypt tests/call_with_op.ec *)",
                note="Use this for a named lemma/spec. It is not the same as "
                     "`call (_: INVARIANT)`, which asks you to provide an oracle "
                     "invariant and generates preservation subgoals.",
            ),
            TacticForm(
                syntax="ecall{1} (LEMMA arg1 arg2 ...). / ecall{2} (LEMMA arg1 arg2 ...).",
                use_when="One-sided pRHL call elimination: only the LHS or RHS has the "
                         "call to be discharged by a named lemma/spec.",
                example="ecall{1} (H_left x{1}).",
                note="Use only when the selected side is at the call frontier. If "
                     "setup statements remain before the call, expose the frontier "
                     "first with `sp`, `wp`, or an indexed `seq` split.",
            ),
            TacticForm(
                syntax="exlim e1{side}, e2{side} => x1 x2; call (LEMMA x1 x2 ...).",
                use_when="The lemma arguments are side-qualified program expressions "
                         "or memory snapshots that are hard to pass directly to "
                         "`ecall`. Lift them into logical names, then use ordinary "
                         "`call` with the fully applied lemma.",
                example="exlim n{1}, RO.m{1} => n0 ro0; call (H n0 ro0).",
                note="This is the more stable repair when `ecall (LEMMA ...)` fails "
                     "with placeholder, side-expression, or split-position errors.",
            ),
        ],
        common_mistake="Using `ecall` before the program frontier is actually at a "
                       "call. EC can then report split-position/frontier errors. "
                       "First inspect `align` or use `sp`, `wp`, or "
                       "`seq K L : (...)` to expose the call. Also avoid using "
                       "`ecall` as a replacement for `call (_: INVARIANT)` when no "
                       "named lemma/spec is available.",
        see_also=["call", "seq", "sp", "wp"],
    ),

    # -----------------------------------------------------------------
    "inline": TacticForms(
        name="inline",
        forms=[
            TacticForm(
                syntax="inline PROC.",
                use_when="Expand a named procedure call that is visibly blocking the "
                         "current program frontier.",
                example="inline G9(BNR_Adv(A), RO).distinguish.",
                note="This is targeted lowering: use it when the current frontier is "
                     "a wrapper/procedure call whose body must become visible before "
                     "a structural tactic such as `seq`, `rcondt`, `rcondf`, `call`, "
                     "or `wp` can apply.",
            ),
            TacticForm(
                syntax="inline{1} N. / inline{2} N.",
                use_when="Side-specific pRHL lowering: expand the N-th visible "
                         "procedure statement on the selected side.",
                example="inline{1} 2.",
                note="N is an EasyCrypt program position, not a source line number. "
                     "Use this when only one side has the wrapper/procedure call to "
                     "open.",
            ),
            TacticForm(
                syntax="inline *.",
                use_when="Bulk lowering when every visible procedure wrapper should "
                         "be expanded before local program work.",
                example="inline *; wp.",
                note="Bulk inline can make the goal very large and can erase useful "
                     "call-site structure. Prefer targeted inline when the surface "
                     "names a specific load-bearing call.",
            ),
        ],
        common_mistake="Using `sp`/`wp` on a visible procedure wrapper that must be "
                       "opened first, or using `inline *` when a targeted side-specific "
                       "`inline{1} N` / `inline{2} N` would expose only the load-bearing "
                       "call.",
        see_also=["call", "seq", "wp", "sp"],
    ),

    # -----------------------------------------------------------------
    "apply": TacticForms(
        name="apply",
        forms=[
            TacticForm(
                syntax="apply LEMMA.",
                use_when="EC can unify LEMMA against the current goal with no manual "
                         "argument hints. Works for simple cases.",
                example="apply eq_sym.",
            ),
            TacticForm(
                syntax="apply (LEMMA arg1 arg2 ... &m).",
                use_when="LEMMA has explicit arguments (modules, proof-terms, memory "
                         "references, formulas) that EC can't infer. REQUIRED for "
                         "section-exported lemmas outside their section — module-typed "
                         "parameters bound inside the section must be passed explicitly.",
                example="apply (pr_RO_FinRO_D D &m () (fun x => x)).",
                note="Check LEMMA's exact declaration first to see the expected signature: "
                     "what's a module, what's a &m, what's a formula. Mismatches "
                     "produce 'cannot infer module arguments' or 'expecting proof-term "
                     "not formula'.",
            ),
            TacticForm(
                syntax="apply (LEMMA _ _ &m).",
                use_when="You want EC to INFER some args (the `_`s) while providing "
                         "others (often `&m` for Pr-level lemmas).",
                example="apply (REDUCTION_LEMMA St _ _ A _ &m).",
            ),
            TacticForm(
                syntax="apply LEMMA; [by auto | smt() | done].",
                use_when="LEMMA produces subgoals; close them with branch-specific "
                         "tactics right after.",
                example="apply ler_add; [byequiv H_proc => // | smt()].",
            ),
        ],
        common_mistake="Guessing argument patterns by trial and error. Standard trap: "
                      "apply LEMMA without realizing it's section-exported. Check its "
                      "exact declaration before the first `apply` to see if args are needed.",
        see_also=["rewrite", "have"],
    ),

    # -----------------------------------------------------------------
    "rewrite": TacticForms(
        name="rewrite",
        forms=[
            TacticForm(
                syntax="rewrite LEMMA.",
                use_when="Forward rewrite: replaces instances of LEMMA's LHS in the "
                         "goal with LEMMA's RHS.",
                example="rewrite map2_zip.",
            ),
            TacticForm(
                syntax="rewrite -LEMMA.",
                use_when="Backward rewrite: replaces LEMMA's RHS with LHS. Useful when "
                         "the RHS matches a term you want to transform back to the LHS.",
                example="rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).",
            ),
            TacticForm(
                syntax="rewrite (LEMMA arg1 arg2).",
                use_when="Apply LEMMA with explicit arguments (modules, &m, etc.).",
                example="rewrite (pr_RO_FinRO_D _ G2 &m () (fun (b:bool) => b)).",
            ),
            TacticForm(
                syntax="rewrite /op.",
                use_when="Unfold (delta-reduce) the definition of `op`.",
                example="rewrite /dec /get /genpoly1305 /=.",
                note="Multiple unfolds can be chained. `/=` at the end triggers "
                     "beta/iota reduction after the delta.",
            ),
            TacticForm(
                syntax="rewrite !LEMMA.",
                use_when="Repeat: rewrite as many times as possible (at least once).",
                example="rewrite !mulrC.",
            ),
            TacticForm(
                syntax="rewrite ?LEMMA.",
                use_when="Zero or more: rewrite any number of times, succeed if none.",
                example="rewrite ?addr0.",
            ),
            TacticForm(
                syntax="rewrite {K}LEMMA.",
                use_when="Rewrite only the K-th occurrence in the goal.",
                example="rewrite {2}(addK b).",
            ),
        ],
        common_mistake="Using forward `rewrite LEMMA` when you need backward `-LEMMA`. "
                      "The direction matters: check which side matches the term you "
                      "want to change.",
        see_also=["apply", "have"],
    ),

    # -----------------------------------------------------------------
    "case": TacticForms(
        name="case",
        forms=[
            TacticForm(
                syntax="case (COND) => H.",
                use_when="Split a pure residual into the `COND` and `!COND` branches.",
                example="case (n <= size xs) => h.",
                note="Use when a visible lemma family has a boundary condition, such as "
                     "list/drop length, integer division/modulo smallness, or membership "
                     "case analysis. The condition itself must come from the current goal.",
            ),
            TacticForm(
                syntax="case: H => H1 H2.",
                use_when="Destruct an existing conjunctive, disjunctive, or boolean "
                         "hypothesis already present in the proof context.",
                example="case: hp => h_nonempty h_bound.",
                note="This form consumes a visible hypothesis; it does not invent a new "
                     "split condition.",
            ),
            TacticForm(
                syntax="case (x = y) => [-> | Hneq].",
                use_when="Split an equality test and immediately substitute on the "
                         "equal branch.",
                example="case (i = j) => [-> | hij].",
                note="Common in map/get-set and list-index residuals where the equal "
                     "branch rewrites by reflexive substitution.",
            ),
        ],
        common_mistake="Splitting on a condition that is not the boundary used by the "
                       "visible lemma family. Read the current goal first: the useful "
                       "condition should mention terms already present in the residual.",
        see_also=["rewrite", "apply"],
    ),

    # -----------------------------------------------------------------
    "byequiv": TacticForms(
        name="byequiv",
        forms=[
            TacticForm(
                syntax="byequiv => //.",
                use_when="Convert a `Pr[G1.main() @ &m : res] = Pr[G2.main() @ &m : res]` "
                         "or `Pr[...] <= Pr[...]` goal into an equiv goal that EC can "
                         "check with `proc; inline *; sim/;auto`. The `=> //` closes "
                         "any trivial side-conditions (like initial glob equalities) "
                         "by `trivial`.",
                example="byequiv => //.    (* opens equiv goal *)",
            ),
            TacticForm(
                syntax="byequiv LEMMA.",
                use_when="Use a pre-declared equiv lemma to close the Pr equality in "
                         "one step. The lemma's statement must match the two Pr terms.",
                example="byequiv H_main.",
            ),
            TacticForm(
                syntax="byequiv LEMMA => //.",
                use_when="Combine: apply lemma + close trivial side-conditions.",
                example="byequiv H_main => //.",
            ),
            TacticForm(
                syntax="byequiv (_: PRE ==> POST).",
                use_when="Specify custom PRE/POST for the equiv goal (different from "
                         "defaults `={glob A}` / `={res}`).",
                example="byequiv (_: ={glob A} ==> res{1} => res{2} \\/ bad{2}).",
            ),
        ],
        common_mistake="Using `byequiv => //.` on a goal that's NOT a Pr-equality "
                      "(e.g., `Pr + Pr <= Pr + Pr`). EC reports `invalid goal shape`. "
                      "Apply `apply ler_add` / `apply ler_add2l` to split the sum "
                      "first, then `byequiv` on each Pr.",
        see_also=["byphoare", "bypr", "apply"],
    ),

    # -----------------------------------------------------------------
    "conseq": TacticForms(
        name="conseq",
        forms=[
            TacticForm(
                syntax="conseq (_: NEW_PRE ==> NEW_POST).",
                use_when="Strengthen precondition and/or weaken postcondition of the "
                         "current pRHL/hoare/phoare goal. Creates subgoals to show "
                         "the new pre implies the old, and the old post implies the new.",
                example="conseq (_: ={glob A} /\\ Mem.k{1} = IndBlock.k{2} ==> ={res}).",
            ),
            TacticForm(
                syntax="conseq LEMMA.",
                use_when="Apply a conseq-style lemma (one proving `PRE2 ==> PRE1` and "
                         "`POST1 ==> POST2`) to reshape the goal.",
                example="conseq CONSEQ_LEMMA.",
            ),
            TacticForm(
                syntax="conseq <= (_: NEW_PRE ==> NEW_POST).",
                use_when="One-way weakening: only weaken post (don't strengthen pre).",
                example="conseq <= (_: true ==> res{1} = res{2}).",
            ),
            TacticForm(
                syntax="conseq (: _ ==> NEW_POST); [2: sim => /> /#].",
                use_when="Mid-proof pRHL surgery: after `rcond`, indexed `wp`, or "
                         "`swap`, weaken the remaining suffix to a smaller relation "
                         "and discharge the unchanged suffix by `sim`.",
                example="conseq(:_==> ={c1, t0, RO.m}); [2: sim=> /> /#].",
                note="This is a proof-shaping step, not a close tactic. Use it when "
                     "the current postcondition is too detailed for the aligned suffix "
                     "but a smaller relation is enough for the branch you are proving.",
            ),
        ],
        common_mistake="Using `{hr}` memory annotation (phoare memory) inside a pRHL "
                      "conseq postcondition. pRHL uses `{1}` / `{2}` only. EC errors "
                      "`unknown memory: &hr`. Fix: replace `{hr}` with `{1}` or `{2}` "
                      "matching the side of the conseq target.",
        see_also=["byequiv", "byphoare", "wp", "swap", "rcondt", "rcondf"],
    ),

    # -----------------------------------------------------------------
    "islossless": TacticForms(
        name="islossless",
        forms=[
            TacticForm(
                syntax="islossless.",
                use_when=(
                    "The current single-program goal is a `phoare [=] 1%r` "
                    "obligation with literal `true` pre/postconditions."
                ),
                example="islossless.",
                note=(
                    "This decomposes the visible procedure body into mechanical "
                    "losslessness obligations for calls, samples, branches, and "
                    "loops. It does not choose a call certificate, loop invariant, "
                    "termination measure, or inlining strategy."
                ),
                modes=("phoare",),
            ),
        ],
        common_mistake=(
            "Treating `islossless` as a generic program tactic. It is surfaced only "
            "for the canonical probability-1 true/true procedure obligation."
        ),
        see_also=["call", "rnd", "while"],
    ),

    # -----------------------------------------------------------------
    "while": TacticForms(
        name="while",
        forms=[
            TacticForm(
                syntax="while (INVARIANT).",
                use_when="Single-program Hoare partial correctness: the current "
                         "program frontier is a while loop and INVARIANT is preserved.",
                example="while (0 <= i <= size xs).",
                modes=("hoare",),
            ),
            TacticForm(
                syntax="while (INVARIANT).",
                use_when="Symmetric while: both sides have while loops that advance "
                         "together. Invariant holds between iterations.",
                example="while (={p, c, i, n} /\\ OCC.gs{1} = RO.m{2}); auto.",
                modes=("pRHL",),
            ),
            TacticForm(
                syntax="while{1} (INVARIANT). / while{2} (INVARIANT).",
                use_when="One-sided pRHL loop: only the selected side is at a while "
                         "frontier. This form opens the loop relation and a separate "
                         "losslessness obligation without supplying an integer variant "
                         "in the pRHL tactic itself.",
                example="while{1} (ret{1} = ret{2}).",
                note="This is a valid EasyCrypt form. Use the two-argument indexed "
                     "form only when you want to supply an explicit integer variant.",
                modes=("pRHL",),
            ),
            TacticForm(
                syntax="while{1} (INVARIANT) (VARIANT). / while{2} (INVARIANT) (VARIANT).",
                use_when="One-sided pRHL loop with an explicit integer variant on the "
                         "selected side.",
                example="while{2} (0 <= i <= size ns) (size ns - i).",
                modes=("pRHL",),
            ),
            TacticForm(
                syntax="while (INVARIANT).",
                use_when="Single-program Phoare loop using EasyCrypt's reverse "
                         "bounded-Hoare while rule without an explicit variant.",
                example="while (0 <= i <= size xs).",
                modes=("phoare",),
            ),
            TacticForm(
                syntax="while (INVARIANT) (VARIANT).",
                use_when="Single-program Phoare loop with an integer variant.",
                example="while (0 <= j <= N /\\ oflist s = restr x j) (N - j).",
                modes=("phoare",),
            ),
            TacticForm(
                syntax="while (INVARIANT) (VARIANT) UPPER_BOUND DECREASE_PROBABILITY.",
                use_when="Lower- or equal-bounded Phoare termination: VARIANT is an "
                         "integer expression, UPPER_BOUND bounds it, and "
                         "DECREASE_PROBABILITY is a lower bound on the probability of "
                         "strict decrease in one iteration.",
                example="while (true) (if test r then 1 else 0) 1 "
                        "(mu sample (predC test)).",
                note="EasyCrypt accepts this four-argument form for `[=]`/`[>=]` "
                     "bounded-Hoare loops and generates the invariant, bound, body, "
                     "and positive-progress obligations.",
                modes=("phoare",),
            ),
        ],
        common_mistake="Mixing proof modes: indexed `while{1}`/`while{2}` forms are "
                      "pRHL forms, while the four-argument probabilistic-termination "
                      "form belongs to a single-program Phoare goal.",
        see_also=["seq", "sim"],
    ),

    # -----------------------------------------------------------------
    "sim": TacticForms(
        name="sim",
        forms=[
            TacticForm(
                syntax="sim.",
                use_when=(
                    "The two pRHL programs are already synchronized and "
                    "EasyCrypt can infer the equality relation for the suffix."
                ),
                example="sim.",
                note=(
                    "If EC reports that it cannot infer equalities, the current "
                    "frontier still needs an explicit relation, call/seq boundary, "
                    "or local alignment step before this form carries enough "
                    "information."
                ),
            ),
            TacticForm(
                syntax="sim => />.",
                use_when=(
                    "The synchronized suffix leaves small pure side conditions "
                    "after simulation."
                ),
                example="sim => />.",
            ),
            TacticForm(
                syntax="conseq (: _ ==> POST); [2: sim => /> /#].",
                use_when=(
                    "A synchronized suffix is available, but the current "
                    "postcondition is larger than the relation needed for that suffix."
                ),
                example="conseq (: _ ==> ={c, t}); [2: sim => /> /#].",
                note=(
                    "This is a relation-shaping use of `sim`; the first subgoal "
                    "still proves that the smaller post is sufficient."
                ),
            ),
        ],
        common_mistake=(
            "Retrying plain `sim.` after EC says it cannot infer equalities. "
            "That error is evidence about the current pRHL frontier, not a "
            "syntax issue; inspect alignment or make the relation "
            "explicit before trying simulation again."
        ),
        see_also=["conseq", "wp", "sp", "seq", "call"],
    ),

    # -----------------------------------------------------------------
    "sp": TacticForms(
        name="sp",
        forms=[
            TacticForm(
                syntax="sp.",
                use_when="Consume matching straight-line prefixes in a pRHL/program "
                         "frontier before a structural tactic such as `if`, `call`, "
                         "`wp`, or local automation.",
                example="sp.",
                note="Use this when the current first instructions are symmetric "
                     "assignments/setup. If the setup is asymmetric, prefer the "
                     "indexed form below.",
            ),
            TacticForm(
                syntax="sp I J.",
                use_when="Consume I left-side and J right-side straight-line setup "
                         "statements to expose the next shared frontier. This is the "
                         "expert opener when one side has a small setup prefix before "
                         "an aligned branch.",
                example="sp 0 1; inline *; if => //; auto.",
                note="Read I and J from the current alignment/setup counts. If EC "
                     "rejects a larger block because its first instruction is "
                     "invalid, revise to the matching prefix such as `sp 0 1.`.",
            ),
            TacticForm(
                syntax="sp; wp; skip => />.",
                use_when="After prefix exposure, absorb assignments and close a small "
                         "pure residual obligation.",
                example="sp; wp; skip => />.",
                note="This is a short repair block, not a branch opener. Do not use it "
                     "before checking whether the branch/call frontier should be "
                     "handled structurally.",
            ),
        ],
        common_mistake="Using `if` while one side still has setup before the branch, "
                       "or using plain `sp.` when the setup is asymmetric. Inspect "
                       "`align`; if the table says one right-side setup "
                       "statement precedes an aligned branch, try `sp 0 1` before "
                       "`inline *; if`.",
        see_also=["if", "wp", "seq", "call"],
    ),

    # -----------------------------------------------------------------
    "wp": TacticForms(
        name="wp",
        forms=[
            TacticForm(
                syntax="wp.",
                use_when="Absorb trailing assignments and deterministic statements "
                         "after the structural frontier is exposed.",
                example="wp.",
                note="In pRHL, do not use plain `wp.` as a blind opener when a branch, "
                     "call, sample, or asymmetric suffix is still the important frontier.",
            ),
            TacticForm(
                syntax="wp I J.",
                use_when="Indexed pRHL weakest-precondition step: consume a concrete "
                         "number of trailing statements on the left and right sides.",
                example="wp 5 6=> />.",
                note="The counts are statement counts in the current expanded goal. "
                     "Use `align` to read the suffix shape; try the "
                     "indexed form before committing a larger block.",
            ),
            TacticForm(
                syntax="wp -I -J.",
                use_when="Tail-surgery form seen in larger pRHL proofs: work from the "
                         "end while leaving a guarded prefix/frontier in place.",
                example="wp -11 -11=> /> /=.",
                note="Negative counts are syntax-sensitive and depend on the current "
                     "expanded statement list. Inspect `align` first; if it "
                     "fails, try a smaller indexed prefix rather than switching route.",
            ),
            TacticForm(
                syntax="wp; skip => />.",
                use_when="After suffix statements are absorbed, close the remaining "
                         "skip/pure relation.",
                example="wp; skip => />.",
            ),
        ],
        common_mistake="Using plain `wp.` to push through a suffix that still contains "
                       "one-sided sampling, guarded code, or instrumentation. First "
                       "use `rcondt`/`rcondf`, `swap`, `seq`, or one-sided `rnd{1}`/"
                       "`rnd{2}` to make the suffix shape match.",
        see_also=["sp", "seq", "swap", "rcondt", "rcondf", "conseq", "rnd"],
    ),

    # -----------------------------------------------------------------
    "swap": TacticForms(
        name="swap",
        forms=[
            TacticForm(
                syntax="swap K OFFSET.",
                use_when="Move statement K by OFFSET positions in the current "
                         "two-sided program order when both sides need the same "
                         "reordering.",
                example="swap 3 -2; sp.",
                note="Use only for independent statements. If dependencies are "
                     "unclear, inspect `align` before trying several offsets.",
            ),
            TacticForm(
                syntax="swap [I..J] OFFSET.",
                use_when="Move a contiguous statement range by OFFSET positions.",
                example="swap [5..6] 7.",
                note="Useful after inlining when a small block must move past local "
                     "setup before `sp`, `wp`, or `sim` can see the aligned suffix.",
            ),
            TacticForm(
                syntax="swap{1} K OFFSET. / swap{2} K OFFSET.",
                use_when="One-sided pRHL reorder: only the selected side needs the "
                         "statement moved before suffix alignment.",
                example="swap{2} 10 -6; wp 5 6=> />.",
                note="This is common in branch-local proofs where one side has extra "
                     "bad-event instrumentation or table updates.",
            ),
        ],
        common_mistake="Treating `swap` as random search over statement numbers. It is "
                       "a local surgery tactic: read the current statement order from "
                       "`align`, move the smallest independent statement or "
                       "range, then try the next structural step.",
        see_also=["sp", "wp", "seq", "rcondt", "rcondf", "conseq"],
    ),

    # -----------------------------------------------------------------
    "rcondt": TacticForms(
        name="rcondt",
        forms=[
            TacticForm(
                syntax="rcondt K; 1: PROVE_CONDITION.",
                use_when="Tell EC that the K-th conditional in the current program "
                         "state is always true, then continue with the true branch.",
                example="rcondt 9; 1: by auto=> />; while(true); auto.",
            ),
            TacticForm(
                syntax="rcondt{1} K; 1: PROVE_CONDITION. / rcondt{2} K; 1: PROVE_CONDITION.",
                use_when="One-sided conditional pruning in pRHL: only the selected "
                         "side's K-th conditional is forced true.",
                example="rcondt{2} 11; 1: by auto=> />; while(true); auto; smt().",
                note="The proof after `1:` must establish the guard in the current "
                     "precondition. If it needs loop facts, preserve them in the "
                     "invariant before doing local surgery.",
            ),
        ],
        common_mistake="Using `rcondt` at the wrong statement position. The index is "
                       "from the current expanded program state, not the source line. "
                       "Inspect `align` after inlining/swap before "
                       "choosing K.",
        see_also=["rcondf", "wp", "swap", "conseq"],
    ),

    # -----------------------------------------------------------------
    "rcondf": TacticForms(
        name="rcondf",
        forms=[
            TacticForm(
                syntax="rcondf K; 1: PROVE_NEGATED_CONDITION.",
                use_when="Tell EC that the K-th conditional is always false, then "
                         "continue with the false branch.",
                example="rcondf 9; 1: by auto=> />; while(true); auto.",
            ),
            TacticForm(
                syntax="rcondf{1} K; 1: PROVE_NEGATED_CONDITION. / rcondf{2} K; 1: PROVE_NEGATED_CONDITION.",
                use_when="One-sided conditional pruning in pRHL when only one side "
                         "has the conditional or only one side's branch is known.",
                example="rcondf{2} 9; 1: by auto=> />; while(true); auto; smt().",
                note="Use this after a case split or invariant fact makes the guard "
                     "decidable. If EC cannot prove the condition, the route may need "
                     "a stronger call/loop invariant rather than more local tactics.",
            ),
        ],
        common_mistake="Using `rcondf` before the guard fact is present in the current "
                       "precondition. If the guard fact should have come from an "
                       "earlier call invariant, rewind to that checkpoint and add it.",
        see_also=["rcondt", "wp", "swap", "conseq"],
    ),

    # -----------------------------------------------------------------
    "seq": TacticForms(
        name="seq",
        forms=[
            TacticForm(
                syntax="seq K L : (INVARIANT).",
                use_when="Split pRHL goal at K stmts on LHS and L stmts on RHS. "
                         "INVARIANT is the mid-point predicate. K != L is allowed "
                         "(asymmetric splits). Generates 2 subgoals: first (prefix) "
                         "with INV as post, second (suffix) with INV as pre.",
                example="seq 1 1 : (={Mem.lc} /\\ StLSke.gs{1} = RO.m{2}).",
                note="K and L are statement counts, not character positions. `inline *` "
                     "increases the statement count as bodies are expanded.",
                modes=("pRHL",),
            ),
            TacticForm(
                syntax="seq K L : (INVARIANT) : PROB_BOUND.",
                use_when="Probabilistic seq: the mid-point invariant holds with "
                         "probability bounded by PROB_BOUND.",
                example="seq 1 1 : (={glob A}) : (1%r - eps).",
                modes=("pRHL",),
            ),
            TacticForm(
                syntax="seq N : (R) P1 P2 P3 P4.",
                use_when="bd-hoare/phoare split of ONE program at N statements (NOT a "
                         "relational `~` goal). R is the mid-point assertion; the four "
                         "bounds are the probabilities EC makes you discharge — P1 = "
                         "`phoare[prefix : pre ==> R]`, P2 = `phoare[suffix : R ==> "
                         "post]`, P3 = `phoare[prefix : pre ==> !R]`, P4 = "
                         "`phoare[suffix : !R ==> post]` — and EC checks the goal bound "
                         "against `P1*P2 + P3*P4` (`<=` for a `[<=]` goal, `=` for `[=]`).",
                example="seq 1 : (good) (1%r) (1%r / 2%r) (0%r) (1%r).",
                note="This is the bd-hoare 4-bound layout for a `phoare[ M : pre ==> "
                     "post ] (= | <=) p` goal — use it instead of the pRHL `seq K L : "
                     "(INV)` form when the goal is one program with a probability bound.",
                modes=("phoare",),
            ),
            TacticForm(
                syntax="seq K : Q B.",
                use_when="One-sided `phoare [<=]` split with an explicit budget "
                         "ledger. Q is the cut assertion; B is the budget assigned "
                         "to the budget-carrying residual branch.",
                example="seq 13 : (size G3.cilog <= PKE_.qD) (((PKE_.qD%r / order%r) ^ 2) * (PKE_.qD%r / order%r)).",
                note="This is the form to check when a product probability budget "
                     "must survive a cut. Think of B as the remaining balance in "
                     "the budget ledger, not as an arbitrary decoration.",
                modes=("phoare",),
            ),
            TacticForm(
                syntax="seq K : Q.",
                use_when="One-sided cut with no explicit budget. Use only when the "
                         "default bound allocation is actually what you want.",
                example="seq 13 : (size G3.cilog <= PKE_.qD).",
                note="Under a product bound, this shape can be accepted while "
                     "placing the small product budget on a high-probability prefix "
                     "or deterministic side condition.",
                modes=("phoare",),
            ),
            TacticForm(
                syntax="seq K : Q (1%r).",
                use_when="One-sided cut where the branch being charged should cost "
                         "at most one. This is not the same as preserving the product "
                         "budget for the event branch.",
                example="seq 13 : (size G3.cilog <= PKE_.qD) (1%r).",
                note="In product-budget proofs this old-order-looking shape can be "
                     "accepted but misleading: it may leave the product budget on "
                     "the wrong side of the cut.",
                modes=("phoare",),
            ),
        ],
        common_mistake="Counting statements wrongly. After `inline *`, many small "
                      "statements may exist that aren't visible in the original code. "
                      "Use the current expanded goal and `align` to count the statements EC currently sees. "
                      "For one-sided product-budget `phoare`, the second trap is "
                      "forgetting the budget ledger: `seq K : Q.` and "
                      "`seq K : Q (1%r).` may typecheck while preserving the wrong "
                      "branch budget; inspect the generated residual before commit.",
        see_also=["while", "call", "phoare_split"],
    ),

    # -----------------------------------------------------------------
    "rnd": TacticForms(
        name="rnd",
        forms=[
            TacticForm(
                syntax="rnd.",
                use_when="Symmetric random sampling: both sides sample from the same "
                         "distribution and EC can infer the coupling automatically "
                         "(usually just identity).",
                example="rnd.",
            ),
            TacticForm(
                syntax="rnd (fun s => FWD(s)) (fun s => BWD(s)).",
                use_when="Bijection coupling: the two samples are related by a "
                         "bijection. Provide forward map and backward map. EC "
                         "generates a subgoal to show FWD and BWD are mutual inverses.",
                example="rnd (fun s => s + mask) (fun s => s - mask).",
                note="THE key technique for game hops that shift/mask random samples. "
                     "Look for it whenever a sampled value on one side equals the other "
                     "side's sample plus a deterministic offset.",
            ),
            TacticForm(
                syntax="rnd{1}. / rnd{2}.",
                use_when="Drop a one-sided sampling that's not present on the other "
                         "side (dead-code elimination for randoms). Typical: LHS "
                         "samples something the proof doesn't use, RHS doesn't sample.",
                example="rnd{1}.    (* drop useless LHS sample *)",
                note="In branch-local pRHL surgery, it is also common to combine a "
                     "one-sided drop with an aligned sample step, e.g. `rnd{2}; rnd.` "
                     "when the RHS has an extra instrumentation sample before the "
                     "shared sample.",
            ),
            TacticForm(
                syntax="rnd predT.    (* phoare/pHL single program *)",
                use_when="SINGLE-program phoare/bd_hoare goal (`phoare[...] = p` / "
                         "`[<=] p` / `[>=] p`, or `bd_hoare`) whose program ends in a "
                         "sample `x <$ d`, where the postcondition does NOT constrain "
                         "the sampled value — the probability-1 / losslessness case. "
                         "`predT` is the always-true event, so EC reduces the sample "
                         "step to `mu d predT = 1%r` (i.e. `is_lossless d`); discharge "
                         "it with the distribution's `*_ll` lemma.",
                example="proc; rnd predT; skip => />; smt(dbool_ll).",
                note="The argument is a PREDICATE / event (`'a -> bool`), NOT a "
                     "probability-mass function — EC computes the sample's "
                     "contribution as `mu d <event>`. `rnd.` (no argument) also works "
                     "when the post is independent of the sampled variable (EC infers "
                     "the event as `predT`); pass `predT` explicitly when that "
                     "inference fails. Do NOT use the two-function `rnd (fwd) (bwd)` "
                     "bijection form here — that is pRHL-only and EC rejects it in a "
                     "single-program goal.",
            ),
            TacticForm(
                syntax="rnd (fun x => P x).    (* phoare/pHL single program *)",
                use_when="SINGLE-program phoare/bd_hoare goal where the bound is the "
                         "probability that the freshly sampled value satisfies a "
                         "specific predicate `P`. EC reduces the sample step to "
                         "`mu d (fun x => P x) <cmp> bound` (the `<cmp>` matches the "
                         "goal's `=` / `<=` / `>=`).",
                example="rnd (fun b => !b); skip; smt(dbool_funi dbool_fu).    "
                        "(* EasyCrypt examples/PIR.ec *)",
                note="`P` ranges over the sampled value's type only (no `{1}`/`{2}` "
                     "side annotation — this is one program). Discharge the residual "
                     "mass obligation with the distribution's mass lemmas "
                     "(`mu1_*`, `dboolE`, `*_funi`, `*_fu`, `*_ll`).",
            ),
        ],
        common_mistake="Mode confusion is the #1 trap. In pRHL (two programs, `equiv "
                      "[_ ~ _]`), `rnd.` with a non-trivial coupling fails — use "
                      "`rnd (fwd) (bwd)` with explicit mutually-inverse maps. In a "
                      "SINGLE-program phoare/bd_hoare goal (`phoare[...] = p`), the "
                      "two-function bijection form is INVALID; `rnd` there takes one "
                      "predicate/event argument — `rnd predT.` for a probability-1 "
                      "sample (residual is the distribution's losslessness), or "
                      "`rnd (fun x => P x).` to reduce to `mu d P`. Read the goal head "
                      "(`equiv [...]` vs `phoare[...]`/`bd_hoare`) before choosing the "
                      "form.",
        see_also=["while", "wp", "phoare", "conseq"],
    ),

    # -----------------------------------------------------------------
    "eager": TacticForms(
        name="eager",
        forms=[
            TacticForm(
                syntax="eager while (h: S1 ~ S2 : pre ==> post).",
                use_when="Commute a statement across a `while` loop. Goal shape: "
                         "`while c; S2 ~ S1; while c` (reach it with `symmetry` / "
                         "`conseq` first). `h` names the one-iteration equivalence; "
                         "`S1 ~ S2` are the moved statement on each side; `pre ==> post` "
                         "is its coupling. Often chased with `=> //; first sim.`",
                example="eager while (h: c <@ O.f(x); ~ c <@ O.f(x); "
                        ": ={glob O} ==> ={glob O, c}) => //; first sim.",
                note="The argument is a ONE-ITERATION relation `(h: S1 ~ S2 : pre ==> "
                     "post)`, NOT a loop invariant and NOT bare `eager while.` — both "
                     "parse-error. `eager while h.` also works if `h` is an already-"
                     "established eager hypothesis.",
            ),
            TacticForm(
                syntax="eager proc.",
                use_when="Enter the eager proof for a pair of CONCRETE procedures "
                         "(no abstract adversary). Usually followed by `inline`, "
                         "`swap`, `sim`.",
                example="eager proc; inline *; sim.",
            ),
            TacticForm(
                syntax="eager proc (h: S1 ~ S2 : pre ==> post) F.",
                use_when="Eager equivalence over an ABSTRACT adversary/oracle `F`: give "
                         "the one-iteration oracle relation `h` and the module name.",
                example="eager proc (h: O.f() ~ O.f() : ={glob O} ==> ={glob O}) A "
                        "=> //.",
            ),
            TacticForm(
                syntax="eager call LEMMA.",
                use_when="Discharge an eager call obligation with an already-proved "
                         "eager equivalence lemma.",
                example="eager call eager_D.",
            ),
            TacticForm(
                syntax="eager [ S_L, c1 ~ c2, S_R : pre ==> post ].",
                use_when="Introduce an explicit eager judgment that moves `S_L`/`S_R` "
                         "across the procedure call `c1 ~ c2` under a stated relation.",
                example="eager [ r <$ dout : ={RO.m} ==> ={RO.m, r} ].",
                note="Use after inspecting the frontier. If the relation needs facts "
                     "missing from the precondition, strengthen the earlier invariant "
                     "rather than enlarging the eager block.",
            ),
        ],
        common_mistake="Writing `eager while.` (bare) or `eager while (<invariant>)`. "
                       "The `while`/`seq`/`proc` eager forms take an eager-info "
                       "`(h: S1 ~ S2 : pre ==> post)` (a one-iteration relation) or a "
                       "bare established-hypothesis name `h`, NEVER a loop invariant. "
                       "Get the goal into `while c; S ~ S; while c` shape (via "
                       "`symmetry`/`conseq`) before `eager while`.",
        see_also=["swap", "transitivity", "sim", "conseq"],
    ),

    # -----------------------------------------------------------------
    "transitivity": TacticForms(
        name="transitivity",
        forms=[
            TacticForm(
                syntax="transitivity M.proc (PRE_LM ==> POST_LM) (PRE_MR ==> POST_MR).",
                use_when="Route a pRHL equivalence through an intermediate procedure "
                         "M.proc. Generates 3 subgoals: (1) glob existence — there is a "
                         "memory state for M making PRE_LM hold from the original LHS "
                         "and PRE_MR hold for the new RHS; (2) original LHS ~ M.proc "
                         "with (PRE_LM ==> POST_LM); (3) M.proc ~ original RHS with "
                         "(PRE_MR ==> POST_MR). Reach for it in game-hop proofs when "
                         "no single equiv lemma bridges LHS to RHS but two chained ones do.",
                example="transitivity M.main1 \n"
                        "  (={glob D, arg} /\\ FRO.m{2} = map (fun _ c => (c, Known)) RO.m{1} ==> ={res, glob D})\n"
                        "  (={glob D, arg} /\\ FRO.m{1} = map (fun _ c => (c, Known)) RO.m{2} ==> ={res, glob D}) => //.",
                note="The two PRE/POST pairs are NOT identical — first pair links "
                     "original LHS state to M's state; second links M's state to "
                     "original RHS state. EC's `=> //` after closes the trivial "
                     "glob-existence subgoal when straightforward.",
            ),
            TacticForm(
                syntax="transitivity{1} { CODE_BLOCK; } (PRE1 ==> POST1) (PRE2 ==> POST2).",
                use_when="Replace the LHS program with an equivalent CODE_BLOCK and "
                         "prove the substitution preserves the equiv. Useful when LHS "
                         "needs program-level rewriting that no pre-existing equiv "
                         "lemma covers — e.g. unfolding a wrapper inline. `{2}` form "
                         "for RHS substitution.",
                example="transitivity{1} \n"
                        "    { Iter(RRO.I).iter_1s(x, elems ((fdom (restr Unknown FRO.m)) `\\` fset1 x)); }\n"
                        "    (={x, FRO.m} /\\ x{1} \\in FRO.m{1} ==> ={x, FRO.m})\n"
                        "    (PRE2 ==> POST2).",
                note="Generates 4 subgoals: glob-existence + two equivs (original LHS ~ "
                     "CODE_BLOCK; CODE_BLOCK ~ original RHS) + a `glob` reflexivity.",
            ),
            TacticForm(
                syntax="transitivity*{1} { r <@ M.proc(args); }.",
                use_when="The `*` (starred) variant inlines the call to M.proc into the "
                         "code block, expanding it during the transitivity step. Useful "
                         "when you want EC to handle the proc-inlining as part of the "
                         "rewrite. Found in PROM.ec for FinRO/RO transitions.",
                example="transitivity*{1} { r <@ MainD(D, GenFinRO(LRO)).distinguish(x); }.",
                note="Less common than the standard form; reach for it when the "
                     "intermediate program is naturally expressed as a single proc call.",
            ),
        ],
        common_mistake="Using `transitivity M.proc (PRE ==> POST).` with a SINGLE "
                       "pre/post pair (Coq-style). pRHL transitivity requires TWO "
                       "pairs — one for each leg of the chain. EC errors with a parse "
                       "issue or 'expected two specifications'. Use one of the "
                       "two-specification forms above.",
        see_also=["byequiv", "conseq", "call"],
    ),

    # -----------------------------------------------------------------
    "congr": TacticForms(
        name="congr",
        forms=[
            TacticForm(
                syntax="congr.",
                use_when="Apply congruence: split a goal `f a1 ... an = f b1 ... bn` "
                         "(equality of two applications of the SAME function) into "
                         "n subgoals `a1 = b1`, ..., `an = bn`. Most common use: "
                         "splitting `Pr[A] +/- Pr[B] = Pr[C] +/- Pr[D]` into "
                         "`Pr[A] = Pr[C]` and `Pr[B] = Pr[D]` (each closeable by "
                         "byequiv).",
                example="congr.    (* splits Pr[X] - Pr[Y] = Pr[Z] - Pr[W] into "
                        "two Pr equalities *)",
                note="EC's `congr` is single-step (one layer of the function "
                     "application). Typical recipe for a chained Pr-equality: "
                     "`congr; have -> : Pr[A] = Pr[C] by byequiv ...; ...; congr; ...` "
                     "— peel the outer layer, close each Pr-equality, then `congr` "
                     "again on the next layer.",
            ),
            TacticForm(
                syntax="congr; congr.    (* or `do ! congr.` for repetition *)",
                use_when="Nested function applications: `f1(f2(a)) = f1(f2(b))` needs "
                         "TWO layers of congruence. Common when peeling wrappers like "
                         "`map_set (Mem.lc{1} ++ ...) = map_set (Mem.lc{2} ++ ...)` "
                         "where you want to reduce to the inner argument equality.",
                example="congr; congr; apply: fsetP=> x'; ...    (* PROM.ec line 459 *)",
                note="`congr; congr.` is preferred over a `do` loop when you know "
                     "the exact depth — keeps the proof script readable and the "
                     "subgoal structure explicit.",
            ),
            TacticForm(
                syntax="rewrite Pr[mu_not]; congr.",
                use_when="Probability-of-negation pattern: `Pr[E : !P] = 1 - Pr[E : P]`. "
                         "After rewriting via `Pr[mu_not]`, the goal becomes a "
                         "subtraction equality that `congr` splits into a `Pr[E : P] = "
                         "Pr[E' : P']` subgoal (the constant `1` parts cancel by "
                         "reflexivity, which `congr` handles).",
                example="rewrite Pr[mu_not]; congr.    (* PKE_hybrid.ec line 213 *)",
            ),
        ],
        common_mistake="Using `congr` on `f(a) = g(b)` where the outer function symbols "
                       "DIFFER (`f` vs `g`). `congr` requires the outer symbol to be the "
                       "SAME on both sides — otherwise no congruence applies and EC "
                       "errors. The fix: rewrite one side to expose the matching outer "
                       "symbol first (e.g. `rewrite -funE` to fold both into the same "
                       "form), then `congr`. Also: `congr` on a Pr-equality where one "
                       "side is `Pr[A] + Pr[B]` and the other is `Pr[C]` (no sum) won't "
                       "split — you need an `apply ler_add` or arithmetic reformulation "
                       "first.",
        see_also=["rewrite", "apply", "byequiv"],
    ),
}


_FORMS["fel"] = TacticForms(
    name="fel",
    forms=[
        TacticForm(
            syntax="fel <at_pos> <counter> <delta> <q> <bad> [ Oracle.proc : <cond> ; ... ].",
            use_when=(
                "The goal is a single-program probability budget "
                "`Pr[ G() @ &m : E ] (<=) bound` where the event `E` is a flag raised "
                "inside a loop and the loop runs at most `q` adversary/oracle steps. "
                "This is the full argument-carrying form EasyCrypt requires for "
                "adversary-driven bad events."
            ),
            example=(
                "fel 1 Count.c (fun x => p%r / n%r) q SampleB.bad "
                "[CountI(R(SampleB)).sample : (size X <= p /\\ Count.c < q)]."
            ),
            note=(
                "Positional arguments (EcPhlFel `fel cntr delta q event pred_specs`): "
                "(1) `at_pos` — number of leading statements before the covered loop "
                "(an int code-gap, e.g. 1 or 2); "
                "(2) `counter` — an int expression counting steps so far "
                "(e.g. `size log`, `Count.c`, `size mf1 + size mf2`); "
                "(3) `delta` — a function `int -> real` bounding the per-step increase "
                "in `Pr[bad]` (e.g. `fun x => x%r * eps`); a CONSTANT here is the usual "
                "mistake; "
                "(4) `q` — the upper bound on `counter`; "
                "(5) `bad` — the event predicate (e.g. `OX2.bad2`, `!uniq l`); "
                "(6) the bracket list pairs EACH adversary oracle with the condition "
                "under which that call may set `bad` — use `[]` only when the adversary "
                "calls no oracles. `fel` then emits one lossless/branch obligation per "
                "oracle plus the accumulated-bound obligation, so expect several "
                "subgoals."
            ),
        ),
        TacticForm(
            syntax="fel.   /   fel N.",
            use_when=(
                "Degenerate forms: EasyCrypt can infer the decomposition only when the "
                "shape is simple (no adversary oracles / trivial counter). Most "
                "adversary-driven probability budgets need the full argument form above."
            ),
            example="fel 1 (size l) (fun x => x%r * mu1 d w) q (!uniq l) [].",
            note=(
                "If `fel.`/`fel N.` fails by applicability, the goal needs the explicit "
                "`counter`/`delta`/`q`/`bad`/oracle-list arguments; read the current "
                "goal and probability-budget surface for the loop counter and bad-event names."
            ),
        ),
    ],
    common_mistake=(
        "On a `Pr[...]` probability budget: omitting the per-oracle bracket list (or "
        "passing `[]` when the adversary DOES call oracles), or giving `delta` as a "
        "constant instead of a function of the `counter`. The `counter`/`delta`/`q` "
        "describe the loop that raises `bad` at the top-level probability goal, not a "
        "local procedure body."
    ),
    see_also=["lemma_hints", "phoare_split"],
)

_PHOARE_SPLIT_FORMS = TacticForms(
    name="phoare_split",
    forms=[
        TacticForm(
            syntax="phoare split ! P Q.",
            use_when=(
                "Split a one-sided probabilistic Hoare obligation into a bound "
                "for `P` and a residual bound for `Q`; useful only when both "
                "bounds match the probability budget you intend to prove."
            ),
            example="phoare split ! 1%r (1%r - bound).",
            note=(
                "`phoare split ! 1%r (1%r - bound)` is an old-order style split. "
                "It can be accepted while leaving a residual `[<=] 1%r` branch "
                "that is easy locally but poor for the full product budget."
            ),
        ),
        TacticForm(
            syntax="phoare split ! (1%r - bound) bound.",
            use_when=(
                "Use when the budget-carrying branch is the second residual and "
                "the first branch is the complementary easy bound."
            ),
            example="phoare split ! (1%r - (PKE_.qD%r / order%r)) (PKE_.qD%r / order%r).",
            note=(
                "Check the generated subgoals before committing. Accepted split "
                "syntax is not enough evidence that the route matches the intended "
                "probability decomposition."
            ),
        ),
    ],
    common_mistake=(
        "Treating an accepted `phoare split !` as route quality. In one-sided "
        "`[<=]` goals, a direct `call (_: true).` residual can fail because the "
        "bound direction is wrong, and a `[<=] 1%r` residual may still be the "
        "wrong proof route for a product budget."
    ),
    see_also=["fel", "call", "lemma_hints"],
)

_FORMS["phoare_split"] = _PHOARE_SPLIT_FORMS
_FORMS["phoare"] = _PHOARE_SPLIT_FORMS


def get_forms(name: str) -> Optional[TacticForms]:
    return _FORMS.get(name.strip())


def list_all() -> list[str]:
    return sorted(_FORMS.keys())


def format_forms(
    forms: TacticForms,
    *,
    mode: str = "",
    goal_text: str = "",
) -> str:
    """Pretty-print a TacticForms entry for stdout."""
    normalized_mode = normalize_proof_mode(mode, goal_text)
    lines = [
        f"=== `{forms.name}` tactic — argument forms ===",
        "",
    ]
    if normalized_mode:
        lines.append(f"Current proof mode: {normalized_mode}")
        lines.append("")
    # `TacticForm.modes` is applicability metadata, not a ranking hint. A bd-hoare
    # goal must never receive pRHL-only syntax (and vice versa). Untagged forms are
    # universal until their entry is split into mode-specific variants.
    rendered_forms = list(forms.forms)
    if normalized_mode:
        rendered_forms = [
            form for form in rendered_forms
            if not tuple(getattr(form, "modes", ()) or ())
            or normalized_mode in tuple(getattr(form, "modes", ()) or ())
        ]
    if not rendered_forms:
        lines.append(
            f"No `{forms.name}` argument form applies to the current "
            f"{normalized_mode or 'unknown'} proof mode."
        )
        lines.append("")
    for i, f in enumerate(rendered_forms, 1):
        lines.append(f"Form {i}:  {f.syntax}")
        lines.append(f"  Use when: {f.use_when}")
        lines.append(f"  Example:  {f.example}")
        if f.note:
            lines.append(f"  Note:     {f.note}")
        lines.append("")
    contextual = _contextual_mode_notes(forms.name, normalized_mode)
    if contextual:
        lines.extend(contextual)
        lines.append("")
    if forms.common_mistake:
        lines.append(f"⚠️  Common mistake: {forms.common_mistake}")
        lines.append("")
    if forms.see_also:
        lines.append(f"See also: {', '.join(forms.see_also)}")
        lines.append("")
    return "\n".join(lines)


def normalize_proof_mode(mode: str = "", goal_text: str = "") -> str:
    """Return the canonical presentation mode for tactic-form filtering."""
    explicit = (mode or "").strip().lower()
    if explicit in {"prhl", "equiv", "relational", "relational_program"}:
        return "pRHL"
    if explicit in {"phoare", "hoare", "probability", "ambient"}:
        return explicit
    classified = classify_goal(goal_text or "") if goal_text else ""
    if classified in {"pRHL", "equiv", "eager"}:
        return "pRHL"
    if classified in {"phoare", "hoare", "probability", "ambient"}:
        return classified
    return ""


def _contextual_mode_notes(name: str, mode: str) -> list[str]:
    if not mode:
        return []
    if name == "rnd":
        return _rnd_mode_notes(mode)
    if name != "while":
        return []
    if mode == "phoare":
        return [
            "Mode-specific note:",
            "  Phoare supports invariant-only, invariant+variant, and a four-argument",
            "  positive-progress form. The current goal and desired bound determine which",
            "  rule applies; the four-argument form is not pRHL syntax.",
        ]
    if mode == "hoare":
        return [
            "Mode-specific note:",
            "  In a hoare goal, start with `while (INVARIANT).` for partial-correctness",
            "  loop proofs. Add a variant only when the surrounding proof obligation",
            "  explicitly asks for termination.",
            "  Example: `while (0 <= i <= size xs).`",
        ]
    if mode == "pRHL":
        return [
            "Mode-specific note:",
            "  In pRHL, `while (INVARIANT).` is the symmetric two-program form.",
            "  For a one-sided loop, `while{1}`/`while{2}` accepts either just the",
            "  relation invariant or the invariant plus an explicit integer variant.",
        ]
    return []


def _rnd_mode_notes(mode: str) -> list[str]:
    if mode in {"phoare", "hoare", "probability"}:
        return [
            "Mode-specific note:",
            "  This is a SINGLE-program goal, so `rnd` takes ONE predicate/event",
            "  argument — NOT the two-function `rnd (fwd) (bwd)` bijection (that form",
            "  is pRHL-only and EC rejects it here).",
            "  Probability-1 sample (`= 1%r`, post free of the sample): `rnd predT.`",
            "    → residual is `mu d predT = 1%r`, the distribution's losslessness;",
            "      close with its `*_ll` lemma. `rnd.` alone also works when EC can",
            "      infer the event as `predT`.",
            "  Explicit bound on the sampled value: `rnd (fun x => P x).`",
            "    → residual is `mu d (fun x => P x) <cmp> bound`; close with the",
            "      distribution's mass lemmas (`mu1_*`, `dboolE`, `*_funi`, `*_fu`).",
        ]
    if mode == "pRHL":
        return [
            "Mode-specific note:",
            "  In pRHL (two programs), use `rnd.` for an inferable symmetric coupling,",
            "  `rnd (fun s => FWD(s)) (fun s => BWD(s)).` for a bijection coupling, or",
            "  `rnd{1}`/`rnd{2}` to drop a one-sided sample. The single-predicate",
            "  `rnd predT.` form belongs to single-program phoare/bd_hoare goals.",
        ]
    return []
