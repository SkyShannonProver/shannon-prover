## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
pre =
  arg{1} = arg{2} /\
  RCPA_Wrap.k{1} = RCPA_Wrap.k{2} /\
  RCPA_QueryBounder.qC{1} = RCPA_QueryBounder.qC{2}

    RCPA_QueryBounder(A, RCPA_Wrap(MEE(PseudoRP, MAC))).O'.enc ~ RCPA_QueryBounder(
                                                                   A,
                                                                   RCPA_Wrap(
                                                                    MacThenEncrypt(
                                                                    PadThenEncrypt(
                                                                    IV_Wrap(
                                                                    CBC(
                                                                    PseudoRP))),
                                                                    MAC))).O'.enc 

post =
  res{1} = res{2} /\
  RCPA_Wrap.k{1} = RCPA_Wrap.k{2} /\
  RCPA_QueryBounder.qC{1} = RCPA_QueryBounder.qC{2}
[66|check]>
```

**Last action:** `wp; call (_: ={RCPA_Wrap.k, RCPA_QueryBounder.qC}); last by auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
