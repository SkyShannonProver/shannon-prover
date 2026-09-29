## Requested: `lookup_symbol` — UFCMA.set_bad2

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-MISS] UFCMA.set_bad2 not found. tried: UFCMA.set_bad2, MB.UFCMA.set_bad2, NonceCount.UFCMA.set_bad2, Poly_in.UFCMA.set_bad2, Poly_out.UFCMA.set_bad2, TPoly.UFCMA.set_bad2, Extra_block.UFCMA.set_bad2, Block.UFCMA.set_bad2, FiniteRO.UFCMA.set_bad2, Indist.UFCMA.set_bad2, OpCCinit.UFCMA.set_bad2, OpCCRO.UFCMA.set_bad2, CCA_UFCMA.UFCMA.set_bad2, Split0.UFCMA.set_bad2, SplitD.UFCMA.set_bad2, SplitC1.UFCMA.set_bad2, Split1.UFCMA.set_bad2, SplitC2.UFCMA.set_bad2, IPNonce.UFCMA.set_bad2, Byte.UFCMA.set_bad2, Key.UFCMA.set_bad2, Nonce.UFCMA.set_bad2, C.UFCMA.set_bad2, MB.I1.UFCMA.set_bad2, MB.I2.UFCMA.set_bad2, MB.RO.UFCMA.set_bad2, MB.RO_Pair.UFCMA.set_bad2, MB.ROF.UFCMA.set_bad2, MB.ROin.UFCMA.set_bad2, MB.ROout.UFCMA.set_bad2, NonceCount.I1.UFCMA.set_bad2 hint: no declaration resolved in the current EasyCrypt context or source-scan fallback. Use a more exact qualified name, or ask the manager for `goal_info` / `lemma_hints` before trying to apply it.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 3)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
```
_…(+42 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: n <- head witness<:nonce> l0
- frontier: both sides at `r <@ RO.get(n, C.ofintd 0)`
- frontier: both sides at `t <@ UFCMA(RO).set_bad2(map (fun (c : ciphertext) => c.`4 - `

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **3** · phase `seq_cut` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `rcondf{1} 2; first by auto => />; smt(head_behead).` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

