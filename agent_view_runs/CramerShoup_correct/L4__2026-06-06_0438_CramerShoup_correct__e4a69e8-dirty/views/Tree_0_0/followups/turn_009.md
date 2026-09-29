## Pure Logic — close with smt / rewrite

**Goal operators:**
- `DH.G.g`
- `Some`
- `hr`
- `None`

**Visible hypotheses:**
- `hx1: x1 \in dt`
- `hx2: x2 \in dt`
- `hy1: y1 \in dt`
- `hy2: y2 \in dt`
- `hz1: z1 \in dt`
- `hz2: z2 \in dt`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

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
hx1: x1 \in dt
x2: ZModE.exp
hx2: x2 \in dt
y1: ZModE.exp
hy1: y1 \in dt
y2: ZModE.exp
hy2: y2 \in dt
z1: ZModE.exp
hz1: z1 \in dt
z2: ZModE.exp
hz2: z2 \in dt
w: ZModE.exp
hw: w \in dt \ pred1 zero
k: K
hk: k \in dk
u: ZModE.exp
hu: u \in dt
V: ZModE.exp
     := H k
          (DH.G.g ^ u, DH.G.g ^ w ^ u,
           (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr})
hc: (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u *
    (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * V) =
    DH.G.g ^ u ^ (x1 + V * y1) * DH.G.g ^ w ^ u ^ (x2 + V * y2)
------------------------------------------------------------------------
(if (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u *
    (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * V) =
    DH.G.g ^ u ^ (x1 + V * y1) * DH.G.g ^ w ^ u ^ (x2 + V * y2) then
   Some
     ((DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} /
      (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2))
 else None) =
Some m{hr}
[54|check]>
```

## Status
remaining **1** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `pose V := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u …` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
