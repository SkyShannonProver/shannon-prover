## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
pre =
  arg{1} = arg{2} /\
  Mem.lc{1} = Mem.lc{2} /\
  Mem.log{1} = Mem.log{2} /\
  BNR.lenc{1} = BNR.lenc{2} /\
  BNR.ndec{1} = BNR.ndec{2} /\
  UFCMA.log{1} = UFCMA.log{2} /\
  UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
  UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
  RO.m{1} = RO.m{2} /\
  SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
  SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\
  UFCMA_li.i{2} = nth0 /\
  UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
  UFCMA_li.badi{2} =
  (nth0 < size UFCMA_l.lbad1{2} /\
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)

    BNR(CPA_CCA_Orcls(UFCMA_l.O)).enc ~ BNR(CPA_CCA_Orcls(UFCMA_li.O)).enc 

post =
  res{1} = res{2} /\
  Mem.lc{1} = Mem.lc{2} /\
  Mem.log{1} = Mem.log{2} /\
  BNR.lenc{1} = BNR.lenc{2} /\
  BNR.ndec{1} = BNR.ndec{2} /\
  UFCMA.log{1} = UFCMA.log{2} /\
  UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
  UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
  RO.m{1} = RO.m{2} /\
  SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
  SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\
  UFCMA_li.i{2} = nth0 /\
  UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
  UFCMA_li.badi{2} =
  (nth0 < size UFCMA_l.lbad1{2} /\
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)
[427|check]>
```

## Status
remaining **5** · phase `relational_program` / `prhl_module`

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
- you submitted: `commit_tactic` `call (_: Mem.lc{1} = Mem.lc{2} /\ Mem.log{1} = Mem.log{2} /\ BNR.lenc{1} = BNR.lenc{2} /\…`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":25,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"call (_: Mem.lc{1} = Mem.lc{2} /\\ Mem.log{1} = Mem.log{2} /\\ BNR.lenc{1} = BNR.lenc{2} /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1} = UFCMA.log{2} /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\\ RO.m{1} = RO.m{2} /\\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\\ UFCMA_li.i{2} = nth0 /\\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2))."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"516 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
