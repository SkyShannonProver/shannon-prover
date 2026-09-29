# Agent-View Timeline — `schnorr_proof_of_knowledge_shvzk`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_0539_schnorr_proof_of_knowledge_shvzk |
| lemma | `schnorr_proof_of_knowledge_shvzk` |
| source file | `eval/examples/SchnorrPK.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 23 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  byequiv (_: ={glob D} ==> ={res}) => //.
  proc.
  inline *.
  rcondf{1} 28.
  move=> &m0; auto => />.
  move=> w00 _; split=> _ r1 _ e6 _ z10 _; rewrite log_bij !(loggK, logDr, logrzM); ring.
  swap{2} 12 -5.
  call (_: true).
  rcondt{1} 25.
  move=> &m0; auto => />; move=> w00 _; split=> _ r1 _ e6 _ z10 _; rewrite log_bij !(loggK, logDr, logrzM); ring.
  wp.
  rnd (fun (z:exp) => z - e1{2}*w{2}) (fun (r:exp) => r + e1{2}*w{2}).
  wp; rnd.
  wp.
  rnd{1}.
  wp.
  rnd; skip => />.
  move=> w0L _; split=> _ r1 _ eL _; (split; first by move=> rR _; ring); move=> _ z1L _; split; first by ring; move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring.
  move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring.
  ring.
  move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_0539_schnorr_proof_of_knowledge_shvzk

Run dir: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d2_schnorr_shvzk/r01/2026-06-06_0539_schnorr_proof_of_knowledge_shvzk/iteration_1`

t=0: `2026-06-06T12:46:44.047000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 953 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv (_: ={glob D} ==> ={res}) => // | probability / pr / probability, 1 goal, goal 324 chars | accepted commit |  |
| T0.0-2 | +00:03 | 2.2 s | 834 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 357 chars | accepted commit |  |
| T0.0-3 | +00:07 | 2.8 s | 2.2 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit inline * | pRHL / call_site / seq_cut, 1 goal, goal 1810 chars | accepted commit |  |
| T0.0-4 | +00:28 | [18.9 s](./views/Tree_0_0/thinking/turn_004.md) | 125 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit rcondf{1} 28 | pRHL / call_site / seq_cut, 1 goal, goal 5402 chars | accepted commit |  |
| T0.0-5 | +00:42 | [13.9 s](./views/Tree_0_0/thinking/turn_005.md) | 141 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit move=> &m0; auto => /> | hoare / procedure_body / procedure_frontier, 2 goals, goal 260 chars | accepted commit |  |
| T0.0-6 | +01:45 | [62.8 s](./views/Tree_0_0/thinking/turn_006.md) | 2.2 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit move=> w00 _; split=> _ r1 _ e6 _ z10 _; rewrite log_bij !(loggK, logDr, logrzM); ring | ambient / ambient_logic, 2 goals, goal 946 chars | accepted commit |  |
| T0.0-7 | +04:15 | [147.8 s](./views/Tree_0_0/thinking/turn_007.md) | 2.2 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit swap{2} 12 -5 | pRHL / call_site / seq_cut, 1 goal, goal 3444 chars | accepted commit |  |
| T0.0-8 | +04:27 | [9.8 s](./views/Tree_0_0/thinking/turn_008.md) | 2.2 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit call true | pRHL / call_site / seq_cut, 1 goal, goal 3444 chars | accepted commit |  |
| T0.0-9 | +04:43 | [13.9 s](./views/Tree_0_0/thinking/turn_009.md) | 141 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit rcondt{1} 25 | pRHL / procedure_body / seq_cut, 1 goal, goal 3608 chars | accepted commit |  |
| T0.0-10 | +04:49 | [5.7 s](./views/Tree_0_0/thinking/turn_010.md) | 2.3 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit move=> &m0; auto => />; move=> w00 _; split=> _ r1 _ e6 _ z10 _; rewrite log_bij !(loggK, log... | hoare / procedure_body / procedure_frontier, 2 goals, goal 257 chars | accepted commit |  |
| T0.0-11 | +05:16 | [24.7 s](./views/Tree_0_0/thinking/turn_011.md) | 2.3 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 3328 chars | accepted commit |  |
| T0.0-12 | +06:44 | [86.1 s](./views/Tree_0_0/thinking/turn_012.md) | 876 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit rnd (fun (z:exp) => z - e1{2}*w{2}) (fun (r:exp) => r + e1{2}*w{2}) | pRHL / procedure_body / seq_cut, 1 goal, goal 2452 chars | accepted commit |  |
| T0.0-13 | +07:15 | [30.2 s](./views/Tree_0_0/thinking/turn_013.md) | 844 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit wp; rnd | pRHL / procedure_body / seq_cut, 1 goal, goal 2618 chars | accepted commit |  |
| T0.0-14 | +07:51 | [35.1 s](./views/Tree_0_0/thinking/turn_014.md) | 853 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 2411 chars | accepted commit |  |
| T0.0-15 | +08:12 | [20.1 s](./views/Tree_0_0/thinking/turn_015.md) | 865 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit rnd{1} | pRHL / procedure_body / seq_cut, 1 goal, goal 3222 chars | accepted commit |  |
| T0.0-16 | +08:36 | [22.8 s](./views/Tree_0_0/thinking/turn_016.md) | 183 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 3319 chars | accepted commit |  |
| T0.0-17 | +08:56 | [19.9 s](./views/Tree_0_0/thinking/turn_017.md) | 147 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit rnd; skip => /> | pRHL / procedure_body / relational_program, 1 goal, goal 5001 chars | accepted commit |  |
| T0.0-18 | +09:41 | [44.9 s](./views/Tree_0_0/thinking/turn_018.md) | 122 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit move=> w0L _; split=> _ r1 _ eL _; (split; first by move=> rR _; ring); move=> _ z1L _; split... | ambient / ambient_logic, 1 goal, goal 1192 chars | accepted commit |  |
| T0.0-19 | +10:14 | [32.8 s](./views/Tree_0_0/thinking/turn_019.md) | 155 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring | ambient / ambient_logic, 3 goals, goal 316 chars | accepted commit |  |
| T0.0-20 | +10:18 | 3.9 s | 148 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit ring | ambient / ambient_logic, 2 goals, goal 262 chars | accepted commit |  |
| T0.0-21 | +10:22 | [3.9 s](./views/Tree_0_0/thinking/turn_021.md) | 140 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring | ambient / ambient_logic, 1 goal, goal 297 chars | accepted commit |  |
| T0.0-22 | +10:25 | [2.9 s](./views/Tree_0_0/thinking/turn_022.md) | 130 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-23 | +10:40 | 15 s |  | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
