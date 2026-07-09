## Requested: `inspect_context` — call_subgoals

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== Call subgoal preview === `call (_: ={glob Mem, glob BNR} /\ StLSke.gs{1} = RO.m{2}...)` was rejected by the daemon BEFORE we could preview subgoals: unknown module: BNR Common causes: • invariant has a typo / unresolved name → check with `-where <ident>` • invariant uses a side annotation incorrectly ({1} vs {2}) → re-read the goal's pre to see which side each var lives on • the trailing call doesn't take this invariant — if it's a non-adversary call (named `call LEMMA`), use `call <lemma_name>` not `call (_: I)`

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b : bool}
```
_…(+11 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: RealOrcls(StLSke(St)).init()
- frontier: both sides at `b <@ CCA_CPA_Adv(A, RealOrcls(StLSke(St))).main()`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **4** · phase `failure_diagnostic` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

