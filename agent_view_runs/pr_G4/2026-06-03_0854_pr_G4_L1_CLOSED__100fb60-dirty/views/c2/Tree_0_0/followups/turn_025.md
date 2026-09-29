## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
ll_dec2: islossless G4.O.dec
Hg: islossless G4.A.guess
------------------------------------------------------------------------
Context : hr: {b0 : bool, e, f, h : group, r, r' : ZModE.exp,
              m0, m1 : PKE_.plaintext}
Bound   : [<=] 1%r

pre =
  G2.v = H G1.k (G3.a, G3.a_, G3.c) /\
  G2.alpha = (r - G1.u * (G1.x + G2.v * G1.y)) / (G1.w * (G1.u' - G1.u)) /\
  G1.cstar = Some (G3.a, G3.a_, G3.c, G3.d) /\
  ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog)

(1)  b0 <@ G4.A.guess(G3.a, G3.a_, G3.c, G3.d)

post = true
[214|check]>
```

**Last action:** `call Hg.` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/l1/artifacts/resume_loop/PRG4b-L1/chunk2/2026-06-03_0954_pr_G4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
