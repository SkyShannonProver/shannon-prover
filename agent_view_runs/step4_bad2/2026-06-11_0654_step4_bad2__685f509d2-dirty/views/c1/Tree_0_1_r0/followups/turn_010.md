## Requested: `lookup_symbol` — sumr_ge0

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] sumr_ge0 (kind: lemma) * In [lemmas or axioms]: lemma sumr_ge0 ['a]: forall (P : 'a -> bool) (F : 'a -> int) (s : 'a list), (forall (a : 'a), P a => 0 <= F a) => 0 <= BIA.big P F s. (* StdBigop.Bigreal.sumr_ge0 *) lemma sumr_ge0 ['a]: forall (P : 'a -> bool) (F : 'a -> real) (s : 'a list), (forall (a : 'a), P a => 0%r <= F a) => 0%r <= BRA.big P F s.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 9)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &hr,
  ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
```
_…(+15 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `ns`
- `undup`
- `map`
- `ciphertext`
- `Mem.lc`
- `ns1`
- `filter`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **9** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `hoare.` → accepted
- commit `move=> &hr _; apply mulr_ge0; [apply sumr_ge0=> n0 _ /=; smt(size_ge0) | apply …` → REJECTED: [error] the given proof-term proves:
- commit `move=> &hr _; smt(sumr_ge0 size_ge0 ge0_pr_zeropol mulr_ge0).` → REJECTED: [error] cannot prove goal (strict)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

