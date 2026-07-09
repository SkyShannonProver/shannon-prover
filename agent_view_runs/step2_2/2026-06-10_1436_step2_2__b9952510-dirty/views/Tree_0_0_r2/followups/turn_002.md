## Requested: `inspect_context` — diagnose

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

No errors found in current session output.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
&1: {r : bool}
&2: {r, forged : bool, i : int, n : nonce, ns : nonce list, r0 : poly_in,
    s : poly_out, bl : block}
```
_…(+22 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `size`
- `ns`
- `Mem.lc`
- `StLSke.gs`
- `RO.m`
- `undup`
- `map`
- `ciphertext`

**Visible hypotheses:**
- `Hns: ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})`
- `Hf: forged{2} = false`
- `Hi: i{2} = 0`
- `Hlc: Mem.lc{1} = Mem.lc{2}`
- `Hgs: StLSke.gs{1} = RO.m{2}`

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
remaining **3** · phase `relational_program` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- probe `move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]]; apply (IH c); first…` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

