## 🎯 Current Goal
```
Current goal

Type variables: <none>

&hr: {g_, g, g_0, e, f, h, a, a_, c0, d, g0, g_1, a0, a_0, c1, d0 : group,
     x1, x2, y1, y2, z1, z2, w, u, v, x10, x20, y10, y20, z10, z20, v0 :
     ZModE.exp, k, k0, k1 : K,
     pk0 : K * group * group * group * group * group,
     sk0 : K * group * group * ZModE.exp * ZModE.exp * ZModE.exp *
     ZModE.exp * ZModE.exp * ZModE.exp, pk, pk1 : PKE_.pkey,
     sk, sk1 : PKE_.skey, m, m0 : PKE_.plaintext, c, ci : PKE_.ciphertext,
     m' : PKE_.plaintext option}
x1: ZModE.exp
x2: ZModE.exp
y1: ZModE.exp
y2: ZModE.exp
z1: ZModE.exp
z2: ZModE.exp
w: ZModE.exp
k: K
u: ZModE.exp
------------------------------------------------------------------------
(if (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u *
    (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^
    (u *
     H k
       (DH.G.g ^ u, DH.G.g ^ w ^ u,
        (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr})) =
    DH.G.g ^ u ^
    (x1 +
     H k
       (DH.G.g ^ u, DH.G.g ^ w ^ u,
        (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}) *
     y1) *
    DH.G.g ^ w ^ u ^
    (x2 +
     H k
       (DH.G.g ^ u, DH.G.g ^ w ^ u,
        (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}) *
     y2) then
   Some
     ((DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} /
      (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2))
 else None) =
Some m{hr}
[52|check]>
```

**Last action:** `move=> &hr _ x1 _ x2 _ y1 _ y2 _ z1 _ z2 _ w _ k _ /= u _ /=.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_rerun_l1/l1_goal_projection/d1_cramershoup/r01/2026-06-06_1550_CramerShoup_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_rerun_l1/l1_goal_projection/d1_cramershoup/r01/2026-06-06_1550_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_rerun_l1/l1_goal_projection/d1_cramershoup/r01/2026-06-06_1550_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_rerun_l1/l1_goal_projection/d1_cramershoup/r01/2026-06-06_1550_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
