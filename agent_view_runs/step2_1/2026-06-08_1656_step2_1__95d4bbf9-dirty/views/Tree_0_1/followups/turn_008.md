## Requested: `inspect_context` — call_subgoals

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== Call subgoal preview === Speculative `call (_: ...).` accepted by daemon. 4 subgoal(s) will be queued post-commit. Active call (pre-tactic): `... <@ A(RealOrcls(StLSke(St))).main(...)` Active subgoal verifies: `RealOrcls(OChaChaPoly(IFinRO)).enc ~ RealOrcls(StLSke(St)).enc` (this is subgoal 1 of 4) Outermost module's type: `Adv` (declared procs: main) Note: the 4 subgoals queued aren't necessarily one per proc above — EC's `call` produces one subgoal per oracle the adversary INVOKES, plus residual. The active subgoal's proc (shown above) tells you which oracle this subgoal verifies. Recommended next step: • Examine the active subgoal preview below — it tells you what proc this subgoal verifies and the post you must prove. • For the remaining subgoals, commit the call and navigate with `-status` between each. Each subgoal is one oracle equiv with the SAME invariant `I` you supplied. Active subgoal preview (first 20 lines): Current goal (remaining: 4) Type variables: <none> &m: {} ------------------------------------------------------------------------ pre = arg{1} = arg{2} /\ (Mem.k{1}, Mem.lc{1}, Mem.log{1}) = (Mem.k{2}, Mem.lc{2}, Mem.log{2}) /\ OCC.gs{1} = StLSke.gs{2} Rea...

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b : bool}
```
_…(+9 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: RealOrcls(OChaChaPoly(IFinRO)).init()
- frontier: both sides at `b <@ A(RealOrcls(OChaChaPoly(IFinRO))).main()`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **2** · phase `failure_diagnostic` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

