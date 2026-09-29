## Requested: `inspect_context` — goal_info

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
- probe `rewrite BBS.big_cons /=.` → probed (read-only; state unchanged)
- probe `rewrite BBS.big_cons.` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

