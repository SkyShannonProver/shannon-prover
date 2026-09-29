## Requested: `inspect_context` — tactic_forms `while`

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== `while` tactic — argument forms === Current proof mode: probability Form 1: while (INVARIANT) (VARIANT). Use when: One-sided phoare/probabilistic loop: the proof is already inside a `phoare` obligation and the loop needs both an invariant and a decreasing integer measure. Example: while (0 <= j <= N /\ oflist s = restr x j) (N - j). Note: Do not append `: p`, `(p)`, or any probability argument. The second parenthesized argument is the termination measure; EC generates the probability/body side obligations after this step. Form 2: while (INVARIANT). Use when: Symmetric while: both sides have while loops that advance together. Invariant holds between iterations. Example: while (={p, c, i, n} /\ OCC.gs{1} = RO.m{2}); auto. Form 3: while{1} (INVARIANT) (TERMINATION). Use when: One-sided while on LHS: LHS has a while, RHS doesn't (or has already been processed). Provide INVARIANT (holds each iteration) AND a TERMINATION measure (strictly decreasing integer that reaches 0 to end the loop). Example: while{1} (0 <= i <= n) (n - i). Note: Termination measure REQUIRED for one-sided while. EC won't accept without it. Form 4: while{2} (INVARIANT) (TERMINATION). Use when: One-sided while...

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[UFCMA3(LRO).distinguish() @ &m : res] <=
qdec%r * maxr pr_zeropol pr1_poly_out
[388|check]>
```

## Opener — reduce the probability goal

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound

**Unfoldable heads:**
- `rewrite /pr1_poly_out.` (unfolds `pr1_poly_out`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `byequiv (ROIN.FullEager.RO_LRO_D UFCMA3 _) => //; move=> _; apply dpoly_in_ll.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

