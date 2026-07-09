## Requested: `inspect_context` — tactic_forms `while`

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== `while` tactic — argument forms === Current proof mode: pRHL Form 1: while (INVARIANT) (VARIANT). Use when: One-sided phoare/probabilistic loop: the proof is already inside a `phoare` obligation and the loop needs both an invariant and a decreasing integer measure. Example: while (0 <= j <= N /\ oflist s = restr x j) (N - j). Note: Do not append `: p`, `(p)`, or any probability argument. The second parenthesized argument is the termination measure; EC generates the probability/body side obligations after this step. Form 2: while (INVARIANT). Use when: Symmetric while: both sides have while loops that advance together. Invariant holds between iterations. Example: while (={p, c, i, n} /\ OCC.gs{1} = RO.m{2}); auto. Form 3: while{1} (INVARIANT) (TERMINATION). Use when: One-sided while on LHS: LHS has a while, RHS doesn't (or has already been processed). Provide INVARIANT (holds each iteration) AND a TERMINATION measure (strictly decreasing integer that reaches 0 to end the loop). Example: while{1} (0 <= i <= n) (n - i). Note: Termination measure REQUIRED for one-sided while. EC won't accept without it. Form 4: while{2} (INVARIANT) (TERMINATION). Use when: One-sided while on RHS...

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
eqLRO: equiv[ UFCMA3(RO).distinguish  ~ UFCMA3(LRO).distinguish :
               ((glob A){1}, BNR.lenc{1}, BNR.ndec{1}, UF.forged{1},
                UFCMA.bad1{1}, UFCMA.bad2{1}, UFCMA.cbad1{1}, UFCMA.cbad2{1},
```
_…(+51 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Status
remaining **3** · phase `relational_program` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `trivial.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

