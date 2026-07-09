## 🎯 Current Goal
```
Current goal

Type variables: <none>

P : PRF
P' : PRF
I: (glob P) -> (glob P') -> bool
P_init_eq: equiv[ P.init  ~ P'.init : true ==> I (glob P){1} (glob P'){2}]
P_f_eq: equiv[ P.f  ~ P'.f :
                arg{1} = arg{2} /\ I (glob P){1} (glob P'){2} ==>
                res{1} = res{2} /\ I (glob P){1} (glob P'){2}]
&m: {}
A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}
------------------------------------------------------------------------
Pr[INDR_CPA_direct(CBC_Oracle(P), A).main() @ &m : res] =
Pr[INDR_CPA_direct(CBC_Oracle(P'), A).main() @ &m : res]
[57|check]>
```

**Last action:** `move=> P_init_eq P_f_eq &m A.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_CPA_direct_eq/r01/2026-06-11_1532_CPA_direct_eq/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_CPA_direct_eq/r01/2026-06-11_1532_CPA_direct_eq/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_CPA_direct_eq/r01/2026-06-11_1532_CPA_direct_eq/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_CPA_direct_eq/r01/2026-06-11_1532_CPA_direct_eq/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
