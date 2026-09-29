## Requested: `lookup_symbol` — hasP

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] hasP (kind: lemma) * In [lemmas or axioms]: lemma hasP ['b, 'a]: forall (P : 'a -> 'b -> bool) (m : ('a, 'b) fmap), has P m <=> exists (x : 'a) (y : 'b), m.[x] = Some y /\ P x y. (* List.hasP *) lemma hasP ['a]: forall (p : 'a -> bool) (s : 'a list), has p s <=> exists (x : 'a), (x \in s) /\ p x.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
&m0: {r : bool}
z: int
&hr: {r, forged : bool, i : int, n : nonce, ns : nonce list,
```
_…(+21 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `forged`
- `hr`
- `test_poly`
- `nth`
- `witness`
- `nonce`
- `ns`
- `Mem.lc`

**Visible hypotheses:**
- `Hlt: i{hr} < size ns{hr}`
- `Hz: size ns{hr} - i{hr} = z`
- `i_rng: 0 <= i{hr} <= size ns{hr}`
- `Hlc: Mem.lc{m0} = Mem.lc{hr}`
- `Hgs: StLSke.gs{m0} = RO.m{hr}`
- `Hns: ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> [Hn0 | Hold]; last by have := IH c Hc Hdec Hold; smt().` → accepted
- probe `right; rewrite /test_poly hasP; exists (topol c.`2 c.`3, c.`4); split; first by…` → REJECTED: nothing to rewrite
- probe `right; rewrite /test_poly /=.` → probed (read-only; state unchanged)
- probe `right; rewrite /test_poly /=; move=> _; apply/hasP; exists (topol c.`2 c.`3, c.…` → REJECTED: the given proof-term proves:
- probe `right; rewrite /test_poly /=; move=> _; apply/hasP.` → REJECTED: the given proof-term proves:

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

