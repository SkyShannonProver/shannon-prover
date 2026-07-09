## Requested: `lookup_symbol` — test_poly

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT-SOURCE] test_poly (kind: op; source-scan fallback) op test_poly = (n:nonce) (lc:ciphertext list) r s = let pts = map (fun (c:ciphertext) => (topol c.`2 c.`3, c.`4)) (List.filter (fun (c:ciphertext) => c.`1 = n) lc) in List.has (fun (pt:polynomial*tag) => pt.`2 = poly1305 r s pt.`1) pts SOURCE: current context line 684. NOTE: This is source-scan context because EasyCrypt `print` did not resolve the exact name. Treat it as definition context, not as a daemon-verified lemma signature.

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

