# Agent-View Timeline — `eq_Game1_Game2`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1325_eq_Game1_Game2 |
| lemma | `eq_Game1_Game2` |
| source file | `eval/examples/br93.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 12 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  seq 4 4 : (={glob A, glob Log, glob LRO, pk, m0, m1, b}).
  sim.
  call (_: ={glob Log, glob LRO}).
  sim.
  wp.
  rnd (fun (z:ptxt) => z +^ (if b{2} then m0{2} else m1{2})) (fun (z:ptxt) => z +^ (if b{2} then m0{2} else m1{2})).
  rnd.
  skip.
  smt(addpK dptxt_funi dptxt_fu).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1325_eq_Game1_Game2

Run dir: `artifacts/eval_suite/wave1_recover_both/l1_goal_projection/d1_eq_game12/r01/2026-06-06_1325_eq_Game1_Game2/iteration_1`

t=0: `2026-06-06T20:29:48.017000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 983 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 250 chars | accepted commit |  |
| T0.0-2 | +00:10 | [8.8 s](./views/Tree_0_0/thinking/turn_002.md) | 167 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit seq 4 4 : (={glob A, glob Log, glob LRO, pk, m0, m1, b}) | pRHL / call_site / relational_program, 1 goal, goal 1130 chars | accepted commit |  |
| T0.0-3 | +00:15 | [4.8 s](./views/Tree_0_0/thinking/turn_003.md) | 168 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit sim | pRHL / verification_residue / relational_program, 2 goals, goal 690 chars | accepted commit |  |
| T0.0-4 | +00:19 | [3.9 s](./views/Tree_0_0/thinking/turn_004.md) | 135 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit call (_: ={glob Log, glob LRO}) | pRHL / call_site / relational_program, 1 goal, goal 944 chars | accepted commit |  |
| T0.0-5 | +00:23 | [3.8 s](./views/Tree_0_0/thinking/turn_005.md) | 172 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit sim | equiv / prhl_module / relational_program, 2 goals, goal 309 chars | accepted commit |  |
| T0.0-6 | +00:28 | [4.8 s](./views/Tree_0_0/thinking/turn_006.md) | 186 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit wp | pRHL / procedure_body / relational_program, 1 goal, goal 1218 chars | accepted commit |  |
| T0.0-7 | +00:35 | [6.8 s](./views/Tree_0_0/thinking/turn_007.md) | 194 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit rnd (fun (z:ptxt) => z +^ (if b{2} then m0{2} else m1{2})) (fun (z:pt... | pRHL / procedure_body / relational_program, 1 goal, goal 1104 chars | accepted commit |  |
| T0.0-8 | +00:43 | [7.8 s](./views/Tree_0_0/thinking/turn_008.md) | 233 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit rnd | pRHL / procedure_body / relational_program, 1 goal, goal 1537 chars | accepted commit |  |
| T0.0-9 | +00:59 | [15.8 s](./views/Tree_0_0/thinking/turn_009.md) | 187 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit skip | pRHL / verification_residue / relational_program, 1 goal, goal 1707 chars | accepted commit |  |
| T0.0-10 | +01:08 | [8.7 s](./views/Tree_0_0/thinking/turn_010.md) | 289 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit smt(addpK dptxt_funi dptxt_fu) | ambient / ambient_logic / relational_program, 1 goal, goal 1489 chars | accepted commit |  |
| T0.0-11 | +01:10 | [1.8 s](./views/Tree_0_0/thinking/turn_011.md) | 154 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-12 | +01:15 | 5 s |  | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
