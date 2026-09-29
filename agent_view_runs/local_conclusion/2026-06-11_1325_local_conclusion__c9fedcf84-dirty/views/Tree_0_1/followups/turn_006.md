## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {m : msg * tag, c : block list}
&2 (right) : {m : msg * tag, c : block list}

pre =
  m{1} = m{2} /\
  RCPA_WUF_RCPA.RCPAa.mk{1} = RCPA_WUF_RCPA.RCPAa.mk{2} /\
  OracleBounder.qC{1} = OracleBounder.qC{2}

c <@                                           (1)  c <@                                               
  QueryBounder(                                ( )    QueryBounder(                                    
    RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)),        ( )      RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)),            
    CBCa.SKEa.RCPA.RCPA_Wrap(Random)).O'.enc(  ( )      CBCa.SKEa.RCPA.RCPA_Wrap(                      
    pad m)                                     ( )                       CBCa.SKEa.RCPA.Ideal)).O'.enc(
                                               ( )      pad m)                                         

post =
  c{1} = c{2} /\
  RCPA_WUF_RCPA.RCPAa.mk{1} = RCPA_WUF_RCPA.RCPAa.mk{2} /\
  OracleBounder.qC{1} = OracleBounder.qC{2}
[83|check]>
```

**Last action:** `proc; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
