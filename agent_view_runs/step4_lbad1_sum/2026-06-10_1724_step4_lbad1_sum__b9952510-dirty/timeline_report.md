# Agent-View Timeline — `step4_lbad1_sum`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1724_step4_lbad1_sum |
| lemma | `step4_lbad1_sum` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 10 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  apply (ler_trans Pr[UFCMA_l.f() @ &m : has (fun (i : int) => let tt = nth (w1, w2) UFCMA_l.lbad1 i in tt.`1 = tt.`2) (iota_ 0 qdec)]).
  rewrite Pr[mu_sub].
  move=> &hr [hsz [tt [htt htteq]]]; rewrite hasP; exists (index tt UFCMA_l.lbad1{hr}).
  rewrite mem_iota /=; smt(index_ge0 index_mem nth_index size_ge0).
  done.
  rewrite Pr[mu_has_le].
  done.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1724_step4_lbad1_sum

Run dir: `artifacts/eval_suite/rerun_struct_core/l1_goal_projection/step4_lbad1_sum/r01/2026-06-10_1724_step4_lbad1_sum/iteration_1`

t=0: `2026-06-11T00:30:26+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit apply (ler_trans Pr[UFCMA_l.f() @ &m : has (fun (i : int) => let tt =... | probability / pr / probability, 1 goal, goal 393 chars | accepted commit |  |
| T0.0-2 | +00:05 | [2.8 s](./views/Tree_0_0/thinking/turn_002.md) | 191 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit rewrite Pr[mu_sub] | probability / pr / probability, 2 goals, goal 401 chars | accepted commit |  |
| T0.0-3 | +00:11 | [5.6 s](./views/Tree_0_0/thinking/turn_003.md) | 1.4 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit move=> &hr [hsz [tt [htt htteq]]]; apply/hasP; exists (index tt UFCMA_l.lbad1{hr}) | ambient / ambient_logic, 3 goals, goal 384 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-4 | +00:21 | [8.8 s](./views/Tree_0_0/thinking/turn_004.md) | 231 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit move=> &hr [hsz [tt [htt htteq]]]; rewrite hasP; exists (index tt UFCMA_l.lbad1{hr}) | ambient / ambient_logic, 3 goals, goal 384 chars | accepted commit |  |
| T0.0-5 | +00:31 | [9.7 s](./views/Tree_0_0/thinking/turn_005.md) | 264 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit rewrite mem_iota /=; smt(index_ge0 index_mem nth_index size_ge0) | ambient / ambient_logic, 3 goals, goal 428 chars | accepted commit |  |
| T0.0-6 | +00:34 | [3.4 s](./views/Tree_0_0/thinking/turn_006.md) | 564 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit done | ambient / ambient_logic, 2 goals, goal 150 chars | accepted commit |  |
| T0.0-7 | +00:39 | [3.8 s](./views/Tree_0_0/thinking/turn_007.md) | 178 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit rewrite Pr[mu_has_le] | probability / pr / probability, 1 goal, goal 411 chars | accepted commit |  |
| T0.0-8 | +00:42 | [2.8 s](./views/Tree_0_0/thinking/turn_008.md) | 195 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit done | ambient / ambient_logic, 1 goal, goal 135 chars | accepted commit |  |
| T0.0-9 | +00:53 | [10.8 s](./views/Tree_0_0/thinking/turn_009.md) | 202 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-10 | +00:58 | 5 s |  | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
