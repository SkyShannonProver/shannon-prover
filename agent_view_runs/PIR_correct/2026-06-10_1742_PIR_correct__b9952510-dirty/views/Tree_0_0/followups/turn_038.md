## Requested: `lookup_symbol` — BBS.big_cons

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] BBS.big_cons (kind: lemma) * In [lemmas or axioms]: lemma big_cons ['a]: forall (P : 'a -> bool) (F : 'a -> word) (x : 'a) (s : 'a list), big P F (x :: s) = if P x then F x +^ big P F s else big P F s.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
i0: int
hi0: 0 <= i0 < N
z: int
```
_…(+20 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `big`
- `int`
- `PIR.s`
- `zerow`

**Visible hypotheses:**
- `hi0: 0 <= i0 < N`
- `H: (((0 <= j{hr} <= N /\`
- `hv: v \in {0,1}`
- `hji: j{hr} = i{hr}`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `case v => hv2.` → accepted
- probe `rewrite big_cons /=; rewrite /predT in H; smt(xorwA xorwC xorw0 xorwK).` → probed (read-only; state unchanged)
- commit `rewrite big_cons /=; rewrite /predT in H; smt(xorwA xorwC xorw0 xorwK).` → REJECTED: structural-fingerprint-equal
- probe `rewrite BBS.big_cons /=.` → probed (read-only; state unchanged) (×2)
- probe `rewrite BBS.big_cons.` → probed (read-only; state unchanged)
- probe `rewrite /predT in H; smt(big_cons xorwA xorwC xorw0 xorwK).` → probed (read-only; state unchanged)
- probe `rewrite -/predT.` → probed (read-only; state unchanged)
- probe `smt(BBS.big_cons xorwA xorwC xorw0).` → REJECTED: cannot prove goal (strict)
- probe `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

