## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `ZModE.exp`
- `dt`
- `pred1`
- `zero`
- `dk`
- `g_2`
- `DH.G.g`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
forall &hr,
  true =>
  forall (x1_0 : ZModE.exp),
    x1_0 \in dt =>
    forall (x2_0 : ZModE.exp),
      x2_0 \in dt =>
      forall (y1_0 : ZModE.exp),
        y1_0 \in dt =>
        forall (y2_0 : ZModE.exp),
          y2_0 \in dt =>
          forall (z1_0 : ZModE.exp),
            z1_0 \in dt =>
            forall (z2_0 : ZModE.exp),
              z2_0 \in dt =>
              forall (w0 : ZModE.exp),
                w0 \in dt \ pred1 zero =>
                forall (k2 : K),
                  k2 \in dk =>
                  let g_2 = DH.G.g ^ w0 in
                  let sk2 =
                    (k2, DH.G.g, g_2, x1_0, x2_0, y1_0, y2_0, z1_0, z2_0) in
                  forall (u0 : ZModE.exp),
                    u0 \in dt =>
                    let a1 = DH.G.g ^ u0 in
                    let a_1 = g_2 ^ u0 in
                    let c0_0 = (DH.G.g ^ z1_0 * g_2 ^ z2_0) ^ u0 * m{hr} in
                    let v0_0 = H sk2.`1 (a1, a_1, c0_0) in
                    (if (DH.G.g ^ x1_0 * g_2 ^ x2_0) ^ u0 *
                        (DH.G.g ^ y1_0 * g_2 ^ y2_0) ^
                        (u0 * H k2 (a1, a_1, c0_0)) =
                        a1 ^ (sk2.`4 + v0_0 * sk2.`6) *
                        a_1 ^ (sk2.`5 + v0_0 * sk2.`7) then
                       Some (c0_0 / (a1 ^ sk2.`8 * a_1 ^ sk2.`9))
                     else None) =
                    Some m{hr}
[52|check]>
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

**Last action:** `inline *; auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
