## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b : bool}

pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}

CBC_Oracle(DoubleQuery(PRFi)).init()              (1)  CBC_Oracle(DoubleQuery(Sample)).init()            
b <@                                              (2)  b <@                                              
  A(CBC_Oracle(DoubleQuery(PRFi))).distinguish()  ( )    A(CBC_Oracle(DoubleQuery(Sample))).distinguish()

post =
  (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
  (!DoubleQuery.bad{2} => b{1} = b{2})
[118|check]>
```

## Call Frontier — set up the call invariant

**Situation:** no named-call candidate here — write a manual invariant or step in.

**Frontier:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: CBC_Oracle(DoubleQuery(PRFi)).init()
- frontier: both sides at `b <@ A(CBC_Oracle(DoubleQuery(PRFi))).distinguish()`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

## Status
remaining **1** · phase `relational_program` / `call_site`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":19,"handled_intent":{"intent":"inspect_context","payload":{"topic":"tactic_forms","name":"call"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect tactic forms","outcome":"The manager returned read-only context for the current goal.","timing":"91 ms","content":{"preview":"=== `call` tactic \u2014 argument forms === Current proof mode: ambient Form 1: call LEMMA. Use when: An equiv lemma already proves the procedure correspondence you need. This is the preferred form when available \u2014 EC closes the whole adversary/oracle call in one step. Example: call H_proc. (* uses a pre-declared equiv handle *) Note: EC unifies the pRHL call's LHS/RHS procedure targets against LEMMA's statement. If that succeeds, the call is fully handled. Form 2: call (_: INVARIANT). Use when: No pre-existing equiv lemma matches \u2014 you must provide the oracle invariant manually. EC generates oracle-equiv subgoals (one per oracle procedure the adversary may call). Example: call (_: ={Mem.k, Mem.log} /\\ StLSke.gs{1} = RO.m{2}). Note: Two pre-flight checks before writing the invariant: (a) Is there already a named equiv lemma that proves this correspondence? Run `-file-index` or check `strategic_helpers[equiv]` in your plan's context brief \u2014 if yes, prefer Form 1 (`call LEMMA.`) instead of re-deriving via invariant. (b) For an outer call to an abstract adversary's main (e.g. `A.main`, `BNR_Adv(A).main`), do NOT include `={glob A}` in the invariant. EC handles glob A implicitly via the..."}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
