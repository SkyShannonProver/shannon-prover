## Requested: `inspect_context` — call_invariant_skeleton

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, v, v0 : bool, i : int,
```
_…(+54 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- setup before the frontier (positions 3–6) — absorb with `sp`/`wp`: 4 setup statement(s): h <- g ^ w0; (x, w) <- (h, w0); h0 <- x; ... (1 more)
- frontier: both sides at `b <@ D.distinguish(x, t)`
- frontier: both sides at `w0 <$ dt`
- frontier: both sides at `r <$ dt`
- frontier: both sides at `if (w0 = zero) {`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **1** · phase `failure_diagnostic` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1).` → accepted
- probe `call (_: ={glob D}).` → REJECTED: The module D can write D (add restriction D to D, or D to D)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

