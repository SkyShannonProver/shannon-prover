## 🎯 Current Goal
```
Current goal (remaining: 7)

Type variables: <none>

&m: {}
dec: eK -> ctxt -> ptxt option
dec_sem: forall (ge : (glob E)) (_k : eK) (_c : ctxt),
           hoare[ E.dec :
                   (glob E) = ge /\ k = _k /\ c = _c ==>
                   (glob E) = ge /\ res = dec _k _c ]
E_corr: forall (_k : eK) (_p : ptxt),
          hoare[ E.enc : k = _k /\ p = _p ==> dec _k res = Some _p ]
------------------------------------------------------------------------
pre =
  !MACa.SUF_CMA.SUF_Wrap.win{2} /\
  arg{1} = arg{2} /\
  ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
  CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
  CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
  CTXT_Wrap.win{1} = MACa.SUF_CMA.SUF_Wrap.win{2} /\
  forall (ct : ctxt * tag),
    ct \in MACa.SUF_CMA.SUF_Wrap.s{2} => dec CMAa.ek{2} ct.`1 <> None<:ptxt>

    CTXT_Wrap(EtM(E, M)).enc ~ CMAa(E, A, MACa.SUF_CMA.SUF_Wrap(M)).Sim.enc 

post =
  !MACa.SUF_CMA.SUF_Wrap.win{2} =>
  res{1} = res{2} /\
  ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
  CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
  CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
  CTXT_Wrap.win{1} = MACa.SUF_CMA.SUF_Wrap.win{2} /\
  forall (ct : ctxt * tag),
    ct \in MACa.SUF_CMA.SUF_Wrap.s{2} => dec CMAa.ek{2} ct.`1 <> None<:ptxt>
[133|check]>
```

## Status
remaining **7** · phase `relational_program` / `prhl_module`

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

**Last action:** `exact A_forge_ll.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
