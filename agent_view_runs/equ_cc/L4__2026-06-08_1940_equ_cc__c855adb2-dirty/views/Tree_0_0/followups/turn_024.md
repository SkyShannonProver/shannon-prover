## Requested: `lookup_symbol` — Block.addmA

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-MISS] Block.addmA not found. tried: Block.addmA, MB.Block.addmA, NonceCount.Block.addmA, Poly_in.Block.addmA, Poly_out.Block.addmA, TPoly.Block.addmA, Extra_block.Block.addmA, Block.Block.addmA, FiniteRO.Block.addmA, Indist.Block.addmA, OpCCinit.Block.addmA, OpCCRO.Block.addmA, CCA_UFCMA.Block.addmA, Split0.Block.addmA, SplitD.Block.addmA, SplitC1.Block.addmA, Split1.Block.addmA, SplitC2.Block.addmA, Byte.Block.addmA, Key.Block.addmA, Nonce.Block.addmA, C.Block.addmA, MB.I1.Block.addmA, MB.I2.Block.addmA, MB.RO.Block.addmA, MB.RO_Pair.Block.addmA, MB.ROF.Block.addmA, MB.ROin.Block.addmA, MB.ROout.Block.addmA, NonceCount.I1.Block.addmA, NonceCount.I2.Block.addmA hint: no declaration resolved in the current EasyCrypt context or source-scan fallback. Use a more exact qualified name, or ask the manager for `goal_info` / `lemma_hints` before trying to apply it.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
&1: {i : int, c : byte list, k, k0 : key, n, n0 : nonce, c0 : C.counter,
```
_…(+65 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `size`
- `max_cipher_size`
- `block_size`
- `nonce`
- `C.counter`
- `SplitD.ROF.RO.m`
- `BNR.lenc`
- `C.toint`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **2** · phase `relational_program` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> &1 &2 />.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

