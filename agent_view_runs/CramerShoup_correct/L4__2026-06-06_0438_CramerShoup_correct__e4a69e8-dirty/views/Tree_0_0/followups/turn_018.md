## Requested: `lookup_symbol` — expN

[WHERE-HIT] expN (kind: lemma) * In [lemmas or axioms]: lemma expN: forall (x : group) (k : ZModE.exp), x ^ -k = inv (x ^ k). (* DH.G.expN *) lemma expN: forall (x : group) (k : int), x ^ -k = inv (x ^ k). (* Distr.expN *) lemma expN ['a]: forall (d : 'a Distr.distr) (f : 'a -> real), E d (fun (x : 'a) => - f x) = - E d f.

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&hr: {g_, g, g_0, e, f, h, a, a_, c0, d, g0, g_1, a0, a_0, c1, d0 : group,
     x1, x2, y1, y2, z1, z2, w, u, v, x10, x20, y10, y20, z10, z20, v0 :
     ZModE.exp, k, k0, k1 : K,
     pk0 : K * group * group * group * group * group,
```
_…(+39 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

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

## Status
remaining **1** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `pose V := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u …` → accepted
- probe `rewrite hc /=` → probed (read-only; state unchanged)
- probe `rewrite hc /=; rewrite log_bij !(logg1, logrzM, logDr); ring.` → probed (read-only; state unchanged)
- probe `rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 *…` → probed (read-only; state unchanged)
- probe `rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 *…` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `lookup_symbol`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
