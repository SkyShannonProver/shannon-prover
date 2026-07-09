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
enc_corr_eq: forall (_k : eK) (_p : ptxt),
               equiv[ E.enc  ~ E.enc :
                       ((glob E){1} = (glob E){2} /\
                        k{1} = k{2} /\ p{1} = p{2}) /\
                       k{1} = _k /\ p{1} = _p ==>
                       ((glob E){1} = (glob E){2} /\ res{1} = res{2}) /\
                       dec _k res{1} = Some _p]
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
[135|check]>
```

## Status
remaining **7** · phase `relational_program` / `prhl_module`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `by move=> _k _p; conseq (_: ={glob E, k, p} ==> ={glob E, res}) (E_corr _k _p) …` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
