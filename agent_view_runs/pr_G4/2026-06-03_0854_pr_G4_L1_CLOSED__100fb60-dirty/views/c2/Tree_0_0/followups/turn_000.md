Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal (remaining: 9)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b0 : bool, e, f, h : group, r, r' : ZModE.exp,
              m0, m1 : PKE_.plaintext}
Bound   : [<=] 0%r

pre =
  ! ((g ^ G1.u \in map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog) /\
     (G1.g_ ^ G1.u' \in map (fun (t : PKE_.ciphertext) => t.`2) G3.cilog) /\
     size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w)

(1)  r' <$ dt                 
(2)  r <$ dt                  

post =
  (g ^ G1.u \in map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog) /\
  (G1.g_ ^ G1.u' \in map (fun (t : PKE_.ciphertext) => t.`2) G3.cilog) /\
  (g ^ r' \in map (fun (t : PKE_.ciphertext) => t.`3) G3.cilog) /\
  (g ^ r \in map (fun (t : PKE_.ciphertext) => t.`4) G3.cilog) /\
  size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w
[196|check]>
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
