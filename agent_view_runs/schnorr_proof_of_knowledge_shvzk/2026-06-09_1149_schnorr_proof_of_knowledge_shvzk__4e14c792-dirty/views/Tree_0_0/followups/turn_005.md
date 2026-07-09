## 🎯 Current Goal
```
Current goal

Type variables: <none>

D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool, i : int, x : statement, w : witness, m : message,
             s : secret, e : challenge, t : message * challenge * response,
             to : (message * challenge * response) option}
&2 (right) : {b : bool, x : statement, m : message, e : challenge,
             z : response, t : message * challenge * response}

pre = (glob D){2} = (glob D){m} /\ (glob D){1} = (glob D){m}

(x, w) <@ SchnorrPK.gen()                (1--)  (x, m, e, z) <@ Run(SchnorrPK).main()
(m, s) <@ SchnorrPK.commit(x, w)         (2--)  t <- (m, e, z)                       
e <$ de                                  (3--)  b <@ D.distinguish(x, t)             
to <@                                    (4--)                                       
  SpecialHVZKExperiment(SchnorrPK,       (  -)                                       
    SchnorrPKAlgorithms).main(x, e)      (  -)                                       
i <- 0                                   (5--)                                       
while (to = None<:message * challenge *  (6--)                                       
       response>) {                      (  -)                                       
  to <@                                  (6.1)                                       
    SpecialHVZKExperiment(SchnorrPK,     (   )                                       
      SchnorrPKAlgorithms).main(x, e)    (   )                                       
  i <- i + 1                             (6.2)                                       
}                                        (6--)                                       
t <- oget to                             (7--)                                       
b <@ D.distinguish(x, t)                 (8--)                                       

post = b{1} = b{2}
[42|check]>
```

## Surgery — align or decompose the two sides

**Where:**
- frontier: both sides at `b <@ D.distinguish(x, t)`
- frontier: left side only at `(x, w) <@ SchnorrPK.gen()`
- frontier: right side only at `(x, m, e, z) <@ Run(SchnorrPK).main()`
- frontier: left side only at `(m, s) <@ SchnorrPK.commit(x, w)`
- frontier: left side only at `to <@ SpecialHVZKExperiment(SchnorrPK, SchnorrPKAlgorithms).`
- frontier: left side only at `while (to = None<:message * challenge * response>) {`
- frontier: left side only at `e <$ de`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **1** · phase `seq_cut` / `call_site`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The current cut or frontier context may expose a call route.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- The visible cut may depend on LHS/RHS statement alignment or missing live facts.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`
- Need the valid form for call, seq, while, rnd, or rewrite.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The visible cut/frontier may need indexed `sp i j` before branch tactics.
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

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `proc.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
