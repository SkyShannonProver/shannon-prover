## Requested: `lookup_symbol` — dec

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-MISS] dec not found. tried: dec, MB.dec, NonceCount.dec, Poly_in.dec, Poly_out.dec, TPoly.dec, Extra_block.dec, Block.dec, FiniteRO.dec, Indist.dec, OpCCinit.dec, OpCCRO.dec, CCA_UFCMA.dec, Split0.dec, SplitD.dec, SplitC1.dec, Split1.dec, SplitC2.dec, Byte.dec, Key.dec, Nonce.dec, C.dec, MB.I1.dec, MB.I2.dec, MB.RO.dec, MB.RO_Pair.dec, MB.ROF.dec, MB.ROin.dec, MB.ROout.dec, NonceCount.I1.dec, NonceCount.I2.dec hint: no declaration resolved in the current EasyCrypt context or source-scan fallback. Use a more exact qualified name, or ask the manager for `goal_info` / `lemma_hints` before trying to apply it.

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
- `ciphertext`
- `Mem.lc`
- `hr`
- `dec`
- `StLSke.gs`
- `m0`
- `Mem.k`
- `None`

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
- commit `do 4! (split; first by smt()).` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

