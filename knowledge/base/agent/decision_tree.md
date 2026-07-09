# Proof Planning Guide

Read this before starting a proof. This file is intentionally generic: it
does not store concrete lemma proof scripts, worked examples, or replayable
tactic sequences.

## First Question: What Kind Of Goal Is This?

Use the live EasyCrypt goal, not the KB, as the source of truth.

| Goal shape | First approach | Manager context |
|---|---|---|
| `Pr[...] = Pr[...]` | verified Pr bridge route, else pRHL equivalence | `goal_info`, `pr_bridge_routes`, `equiv_bridge_lemmas` |
| `Pr[...] <= ...` | `byphoare` / bad-event reasoning | `goal_info`, `subgoal_gap` |
| `equiv [...]` | `proc`, then preserve the highest useful abstraction layer | `proof_frontier`, `align` |
| `hoare [...]` / `phoare [...]` | program proof with invariant or deterministic decomposition | `goal_info` |
| pure ambient logic | rewrite, case split, algebra, or SMT | `lemma_hints`, `goal_info` |
| `islossless` | losslessness tactic or explicit calls for abstract procedures | `goal_info` |

## Abstraction Discipline

Stay as high-level as the goal allows.

1. Try a named local lemma if the current goal matches its statement.
2. Try `sim` when the programs are structurally identical.
3. Try `call (_: <invariant>)` while call sites are still visible.
4. Use targeted `inline <proc>` when one procedure body must be exposed.
5. Use `inline *` only after the call structure is no longer useful.

Once `inline *` removes call sites, `call`, `sim`, and call-level `conseq`
opportunities may be gone until you undo.

## Sampling Couplings

For pRHL goals with sampling, decide the coupling from the relationship
between sampled variables:

| Relationship | Coupling family |
|---|---|
| same distribution, same role | identity coupling |
| one side is a shifted or masked version of the other | explicit bijection |
| one side has an extra independent sample | one-sided `rnd` plus losslessness |
| dependent samplings are out of order | `swap` / `seq` before `rnd` |
| a later variable is needed by the bijection | reorder so the dependency is still in scope |

Ask the manager for `align` when statement positions are unclear. Count
positions from the current goal after every `wp`, `swap`, or `inline`, because
the program shape changes.

## Oracle Calls

When a proof reaches an oracle or adversary call:

1. Check whether a local equiv or losslessness lemma already matches.
2. If using `call`, derive the invariant from the current goal or with
   `inspect_context` topic `inv_from_lemma`.
3. Prefer the simpler call form that leaves module aliases inferable.
4. Inline the oracle body only when the invariant cannot be expressed at the
   call boundary.

If an oracle subgoal explodes into many obligations, pause and confirm the
call form is the intended one before proving every branch manually.

## Loops

Before writing a loop invariant, identify:

- the loop counter and its bounds,
- the state relation that must be preserved,
- the variable that decreases for probabilistic termination goals,
- the postcondition needed when the loop guard is false.

Hoare `while` uses an invariant. Phoare `while` uses an invariant and a
variant. If the tactic opens many subgoals, classify them before continuing:
body preservation, initialization, termination, and final postcondition are
different obligations.

## Probability Goals

For probability equalities, first decide whether the proof should compare
programs or rewrite to a closed form. For probability inequalities, avoid
trying to solve the `Pr` term directly with ambient SMT; move to a program
judgment or a known probability lemma first.

For final theorem assembly, gather the available local lemmas and compare
their left and right sides with the target expression. Use direction and
sign carefully; do not assume a rewrite direction from the lemma name.

## Ambient Goals

After program tactics discharge the executable part, remaining goals are
usually one of:

- algebraic equalities,
- set or map membership facts,
- boolean/propositional conversion,
- losslessness side conditions,
- range or non-zero side conditions.

Use `lemma_hints`, `goal_info`, and `lookup_symbol` for named facts. Prefer
small rewrites and explicit hypotheses when SMT lacks the right context.

## When Stuck

If the same tactic shape fails more than twice:

1. Read the latest `ProverWorkspaceView`.
2. Ask for `diagnose` for execution errors.
3. Ask for `goal_info` or `proof_frontier` for the current goal.
4. Check tactic forms with `tactic_forms`.
5. Undo to the previous abstraction level if the current proof shape is too
   low-level.

Do not search the KB for a stored proof script. The KB is only for generic
structure and tactic-form guidance.
