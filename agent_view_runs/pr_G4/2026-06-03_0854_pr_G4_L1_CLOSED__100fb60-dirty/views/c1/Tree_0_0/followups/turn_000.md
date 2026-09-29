Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal (remaining: 6)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b0 : bool, e, f, h : group, r, r' : ZModE.exp,
              m0, m1 : PKE_.plaintext}
Bound   : [<=] (PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)

pre = size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w

(1)  G1.u <$ dt               
(2)  G1.u' <$ dt \ pred1 G1.u 
(3)  r' <$ dt                 
(4)  r <$ dt                  

post =
  ((g ^ G1.u, G1.g_ ^ G1.u', g ^ r', g ^ r) \in G3.cilog) /\
  size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w
[153|check]>
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk1/2026-06-03_0924_pr_G4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk1/2026-06-03_0924_pr_G4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk1/2026-06-03_0924_pr_G4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk1/2026-06-03_0924_pr_G4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
