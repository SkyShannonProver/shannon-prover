## Requested: `inspect_context` — call_site_options

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
```
_…(+52 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier — absorb with `sp`/`wp`: no left-side setup before this frontier
- frontier: left side only at `z <@ CCRO( SplitD.RO_DOM( SplitC1.RO_Pair( SplitC2. RO_Pair(`
- frontier: left side only at `no matching left-side sample at this frontier`

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
- commit `while (c{1} = c{2} /\ i{1} = i{2} /\ n{1} = n0 /\ size p{1} = size p{2} /\ 1 <=…` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

