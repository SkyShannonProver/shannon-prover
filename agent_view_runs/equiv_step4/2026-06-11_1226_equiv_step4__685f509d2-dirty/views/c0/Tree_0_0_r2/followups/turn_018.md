## Requested: `inspect_context` — call_site_options

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, ns, ns1, ns2, l1, l2, l, l0 : nonce list}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}
```
_…(+49 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–3) — absorb with `sp`/`wp`: 3 setup statement(s): l1 <- ns1; l2 <- ns2; l <- l1
- frontier: right side only at `r <@ RO.get(n, C.ofintd 0)`
- frontier: right side only at `t <@ UFCMA(RO).set_bad2(map (fun (c : ciphertext) => c.`4 - `
- frontier: both sides at `while (l <> []) {`
- frontier: both sides at `while (l0 <> []) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **2** · phase `relational_program` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `inline{1} Iter(Orcl).iters Iter(Orcl).iter.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

