## Requested: `inspect_context` — tactic_forms `seq`

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== `seq` tactic — argument forms === Current proof mode: ambient Form 1: seq K L : (INVARIANT). Use when: Split pRHL goal at K stmts on LHS and L stmts on RHS. INVARIANT is the mid-point predicate. K != L is allowed (asymmetric splits). Generates 2 subgoals: first (prefix) with INV as post, second (suffix) with INV as pre. Example: seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}). Note: K and L are statement counts, not character positions. `inline *` increases the statement count as bodies are expanded. Form 2: seq K L : (INVARIANT) : PROB_BOUND. Use when: Probabilistic seq: the mid-point invariant holds with probability bounded by PROB_BOUND. Example: seq 1 1 : (={glob A}) : (1%r - eps). Form 3: seq N : (R) P1 P2 P3 P4. Use when: bd-hoare/phoare split of ONE program at N statements (NOT a relational `~` goal). R is the mid-point assertion; the four bounds are the probabilities EC makes you discharge — P1 = `phoare[prefix : pre ==> R]`, P2 = `phoare[suffix : R ==> post]`, P3 = `phoare[prefix : pre ==> !R]`, P4 = `phoare[suffix : !R ==> post]` — and EC checks the goal bound against `P1*P2 + P3*P4` (`<=` for a `[<=]` goal, `=` for `[=]`). Example: seq 1 : (good) (1%r) (1%r / 2%r)...

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
              r : poly_in, t : poly_out}
```
_…(+36 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Status
remaining **1** · phase `procedure_frontier` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

