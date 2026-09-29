## Requested: `inspect_context` — call_invariant_skeleton

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {r : bool}
&2 (right) : {r : bool}

```
_…(+11 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- frontier: both sides at `r <@ A(GenChaChaPoly(OCC(I))).main()`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **1** · phase `failure_diagnostic` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc*.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

