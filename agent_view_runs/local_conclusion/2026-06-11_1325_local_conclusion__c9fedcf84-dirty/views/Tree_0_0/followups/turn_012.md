## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
`|Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PseudoRP)),
                      QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)))).main
     () @ &m : res] -
  Pr[CBCa.SKEa.RCPA.INDR_CPA(Random,
                      QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)))).main
     () @ &m : res]| <=
`|Pr[IND(PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main
     () @ &m : res] -
  Pr[IND(PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main
     () @ &m : res]| +
2%r * ((q * n) ^ 2)%r * mu1 d_block witness<:block>
[90|check]>
```

**Last action:** `apply/(Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))) &m).` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] the given proof-term proves:`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
