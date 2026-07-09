# Lemma Authoring Rules For Compiler-Friendly Proofs

The compiler should not depend on lemma names.  It should understand project
resources from declaration shape, canonical `Pr[...]` endpoints, events, and
typed signatures.  This document describes the lemma shapes that the current
compiler promises to recognize well.

These are authoring rules, not naming rules.  Names like `step2_1`,
`Bound_by_Birthday`, `Theorem42`, and `pr_Game0_Game1` are all acceptable when
the declaration exposes the right structure.

## General Rules

Prefer declarations whose conclusion exposes the proof resource directly:

- Put the relevant `Pr[...]` terms in the theorem statement, not only in the
  proof body.
- Keep the main equality or inequality at top level after premises and `forall`
  binders.
- Keep bad events, union events, and result predicates visible in the `Pr[...]`
  event position.
- Use explicit module/procedure endpoints such as `Game(A).main()` or
  `M.proc(args)` rather than hiding them behind an opaque predicate.
- Let section parameters, module parameters, and memory arguments appear in the
  signature so name resolution and instantiation binding can see them.

The compiler tolerates:

- local lemmas and section-exported lemmas
- clone prefixes and qualified names
- numbered step names
- names unrelated to the semantic role
- premises before the main conclusion

The compiler does not promise to recover resources hidden only inside an
`smt` proof, a proof-local `have`, or an opaque predicate whose definition is
not present in the visible declaration.

## Pr Equality Rewrite Lemmas

Preferred shape:

```easycrypt
local lemma AnyName &m:
  Pr[G0(A).main() @ &m : res] =
  Pr[G1(A).main() @ &m : res].
```

What the compiler reads:

- two `Pr[...]` terms
- canonical game keys `G0(A)` and `G1(A)`
- matching memories and events when present
- declaration tag `pr_rewrite`

Good uses:

- endpoint normalization
- game-hop equality
- wrapper equivalence lifted to probability

Avoid:

```easycrypt
lemma AnyName &m:
  equiv [G0(A).main ~ G1(A).main : true ==> ={res}].
```

This is a useful pRHL lemma, but it is not a Pr rewrite until another pass or
lemma exposes the corresponding probability equality.

## Pr Inequality And Bound Lemmas

Preferred shape:

```easycrypt
lemma AnyName &m:
  Pr[Game(A).main() @ &m : BadEvent] <= eps.
```

or:

```easycrypt
lemma AnyName &m:
  Pr[G0(A).main() @ &m : res] <=
  Pr[G1(A).main() @ &m : res] +
  Pr[G1(A).main() @ &m : BadEvent].
```

What the compiler reads:

- top-level `<=`
- visible Pr term on the bounded side
- visible bad/result event
- optional additive Pr terms on the other side
- semantic tags such as `pr_bound`, `pr_inequality`, `bad_event`, and
  `pr_additive_bound`

Good examples in the current matrix:

- `Plog_Psample`
- `pr_Game0_Game1`
- `step2_1`
- `Bound_by_Birthday`
- synthetic `Theorem42`

Avoid:

```easycrypt
lemma AnyName &m:
  loss <= eps.
```

when the statement does not reveal which probability/game/event `loss`
represents.

## Additive And Union Bounds

Preferred additive shape:

```easycrypt
lemma AnyName &m:
  Pr[G0.main() @ &m : res] <=
  Pr[G1.main() @ &m : res] +
  Pr[G1.main() @ &m : bad].
```

Preferred event-union shape:

```easycrypt
lemma AnyName &m:
  Pr[G.main() @ &m : E1 \/ E2] <=
  Pr[G.main() @ &m : E1] +
  Pr[G.main() @ &m : E2].
```

What the compiler reads:

- additive top-level real expression
- union or bad-event structure in event positions
- Pr terms that can seed bound/union obligations

Avoid burying the union-bound fact only inside the proof:

```easycrypt
lemma AnyName &m:
  Pr[G.main() @ &m : E1 \/ E2] <= eps.
proof.
  have h: Pr[G.main() @ &m : E1 \/ E2] <= ...
```

The theorem may be true, but the reusable additive resource is not visible as
a declaration shape.

## Advantage And Arithmetic Chain Lemmas

Preferred shape:

```easycrypt
lemma reduction (A <: Adv) &m:
  `|Pr[G0(A).main() @ &m : res] -
    Pr[G1(A).main() @ &m : res]| <=
  Pr[Bad(A).main() @ &m : bad] + eps.
```

What the compiler reads:

- absolute Pr difference
- source and target endpoints
- candidate chain lemmas for arithmetic composition
- native search needs for real-order or `mu` facts

Avoid:

- hiding the whole advantage under a custom operator without exposing the
  underlying `Pr[...]` terms
- replacing the conclusion with only a named `adv A <= eps` form unless the
  operator definition is also explicitly indexed by another pass

## Procedure Equivalence Lemmas

Preferred shape:

```easycrypt
local equiv call_bridge:
  M.proc ~ N.proc :
  ={arg} /\ I (glob P){1} (glob P'){2}
  ==> ={res} /\ I (glob P){1} (glob P'){2}.
```

What the compiler reads:

- procedure endpoints
- pre/post relation
- module parameters and global-state relation
- whether the lemma can match a live call frontier

Good uses:

- `call <lemma>` candidates
- procedure-frontier plans
- wrapper bridge facts when lifted to Pr equality

Avoid:

- proving only a wrapper theorem whose statement hides the actual procedure
  pair
- relying on naming alone to identify which call the lemma handles

## Module Parameters And Instantiation

Preferred shape:

```easycrypt
lemma AnyName (A <: Adv) (O <: Oracle) &m:
  Pr[G(A,O).main() @ &m : res] =
  Pr[H(A,O).main() @ &m : res].
```

What the compiler reads:

- typed module slots
- memory slots
- value/type slots when present
- whether exact instantiation is needed before probing

Avoid:

- omitting module bounds when the lemma is exported from a section
- relying on implicit argument order that is not recoverable from `-where`
- using placeholder-style names in proof actions without a signature lookup

## Native Search-Friendly Library Lemmas

For library lemmas intended to be found by EasyCrypt native search, expose the
operators in the statement:

```easycrypt
lemma mem_take x n xs:
  x \in take n xs => x \in xs.
```

Good native-search surfaces include:

- `take mem`
- `take size`
- `( <= ) mu`
- `mu predU`

The compiler treats native-search hits as inspection candidates. A search hit
should still be followed by `-where <lemma>` before applying or rewriting.

## Unsupported Or Weakly Supported Shapes

The compiler may miss or downgrade lemmas shaped like this:

- theorem conclusion is a custom operator with no visible `Pr[...]`
- proof body contains the useful bound, but the statement does not
- event/bad condition is hidden behind an opaque predicate not visible in the
  declaration
- important endpoint is created only by a local `have` inside the proof
- statement mixes many unrelated Pr terms without a clear top-level relation
- lemma requires non-obvious value arguments and no signature artifact exists

When in doubt, add a small compiler smoke matrix row before relying on a new
style.

## Adding A New Style

1. Add a real-source row to `tests/test_compiler_smoke_matrix.py`.
2. Add a synthetic row with an intentionally uninformative name.
3. Assert semantic recall, obligation planning, and action rendering.
4. If the compiler needs a new typed fact, add it to `SCHEMAS.md` and the
   producing module test.
5. If the style hides essential structure, document it as unsupported here
   rather than adding project-specific fallback logic.
