## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b, b' : bool, m0, m1, h : ptxt, c : rand * ptxt, pk : pkey,
             sk : skey}
&2 (right) : {b, b' : bool, m0, m1, h : ptxt, c : rand * ptxt, pk : pkey,
```
_…(+19 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: Log(LRO).init()
- frontier: both sides at `(m0, m1) <@ A(Log(LRO)).a1(pk)`
- frontier: both sides at `b' <@ A(Log(LRO)).a2(c)`
- frontier: both sides at `(pk, sk) <$ dkeys`
- frontier: both sides at `b <$ {0,1}`
- frontier: both sides at `Game1.r <$ drand`
- frontier: both sides at `h <$ dptxt`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **1** · phase `relational_program` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d1_eq_game12/r01/2026-06-06_1331_eq_Game1_Game2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d1_eq_game12/r01/2026-06-06_1331_eq_Game1_Game2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d1_eq_game12/r01/2026-06-06_1331_eq_Game1_Game2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d1_eq_game12/r01/2026-06-06_1331_eq_Game1_Game2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
