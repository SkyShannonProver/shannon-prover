# Agent-View Timeline — `eq_Game1_Game2`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1331_eq_Game1_Game2 |
| lemma | `eq_Game1_Game2` |
| source file | `eval/examples/br93.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 22 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  call (_: ={glob Log, glob LRO}).
  sim.
  wp.
  rnd (fun (x : ptxt) => x +^ (if b{1} then m0{1} else m1{1})).
  conseq (_ : _ ==> ={glob A, Log.qs, LRO.m, pk, b} /\ Game1.r{1} = Game2.r{2}).
  smt(addpK dptxt_funi dptxt_fu).
  sim.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1331_eq_Game1_Game2

Run dir: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d1_eq_game12/r01/2026-06-06_1331_eq_Game1_Game2/iteration_1`

t=0: `2026-06-06T20:31:48.400000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe proc | equiv / prhl_module / relational_program, 1 goal, goal 250 chars | accepted probe |  |
| T0.0-2 | +00:07 | [5.8 s](./views/Tree_0_0/thinking/turn_002.md) | 179 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 250 chars | accepted commit |  |
| T0.0-3 | +00:27 | [19.2 s](./views/Tree_0_0/thinking/turn_003.md) | 786 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 1 goal, goal 1130 chars | read-only inspect |  |
| T0.0-4 | +00:42 | [14.8 s](./views/Tree_0_0/thinking/turn_004.md) | 164 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | probe call (_: ={glob Log}) | pRHL / call_site / relational_program, 1 goal, goal 1130 chars | accepted probe |  |
| T0.0-5 | +01:09 | [26.9 s](./views/Tree_0_0/thinking/turn_005.md) | 150 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | probe call (_: ={glob Log, glob LRO}) | pRHL / call_site / relational_program, 1 goal, goal 1130 chars | accepted probe |  |
| T0.0-6 | +01:19 | [9.9 s](./views/Tree_0_0/thinking/turn_006.md) | 137 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit call (_: ={glob Log, glob LRO}) | pRHL / call_site / relational_program, 1 goal, goal 1130 chars | accepted commit |  |
| T0.0-7 | +01:27 | [7.2 s](./views/Tree_0_0/thinking/turn_007.md) | 829 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | probe sim | equiv / prhl_module / relational_program, 2 goals, goal 309 chars | accepted probe |  |
| T0.0-8 | +01:35 | [7.8 s](./views/Tree_0_0/thinking/turn_008.md) | 202 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit sim | equiv / prhl_module / relational_program, 2 goals, goal 309 chars | accepted commit |  |
| T0.0-9 | +01:51 | [15.1 s](./views/Tree_0_0/thinking/turn_009.md) | 856 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | probe wp | pRHL / call_site / relational_program, 1 goal, goal 1398 chars | accepted probe |  |
| T0.0-10 | +02:05 | [13.8 s](./views/Tree_0_0/thinking/turn_010.md) | 195 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit wp | pRHL / call_site / relational_program, 1 goal, goal 1398 chars | accepted commit |  |
| T0.0-11 | +02:19 | [13.1 s](./views/Tree_0_0/thinking/turn_011.md) | 873 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | probe rnd (fun (x : ptxt) => x +^ (if b{1} then m0{1} else m1{1})) | pRHL / call_site / relational_program, 1 goal, goal 1274 chars | accepted probe |  |
| T0.0-12 | +02:43 | [23.8 s](./views/Tree_0_0/thinking/turn_012.md) | 198 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit rnd (fun (x : ptxt) => x +^ (if b{1} then m0{1} else m1{1})) | pRHL / call_site / relational_program, 1 goal, goal 1274 chars | accepted commit |  |
| T0.0-13 | +03:20 | [36.1 s](./views/Tree_0_0/thinking/turn_013.md) | 861 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | probe sim | pRHL / call_site / relational_program, 1 goal, goal 1697 chars | rejected probe: cannot infer the set of equalities |  |
| T0.0-14 | +03:26 | 5 s |  | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | unknown | pRHL / call_site / relational_program, 1 goal, goal 1697 chars | repair / unhealthy |  |
| T0.0-15 | +03:57 | 31 s |  | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | unknown | pRHL / call_site / relational_program, 1 goal, goal 1697 chars | repair / unhealthy |  |
| T0.0-16 | +04:00 | [3.8 s](./views/Tree_0_0/thinking/turn_016.md) | 175 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | probe conseq (_ : _ ==> ={glob A, Log.qs, LRO.m, pk, b} /\ Game1.r{1} = Gam... | pRHL / call_site / relational_program, 1 goal, goal 1697 chars | accepted probe |  |
| T0.0-17 | +04:16 | [15.8 s](./views/Tree_0_0/thinking/turn_017.md) | 193 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit conseq (_ : _ ==> ={glob A, Log.qs, LRO.m, pk, b} /\ Game1.r{1} = Gam... | pRHL / call_site / seq_cut, 1 goal, goal 1697 chars | accepted commit |  |
| T0.0-18 | +04:26 | [9 s](./views/Tree_0_0/thinking/turn_018.md) | 1 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | probe smt(addpK dptxt_funi dptxt_fu) | ambient / ambient_logic / relational_program, 2 goals, goal 1453 chars | accepted probe |  |
| T0.0-19 | +04:31 | [4.7 s](./views/Tree_0_0/thinking/turn_019.md) | 326 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit smt(addpK dptxt_funi dptxt_fu) | ambient / ambient_logic / relational_program, 2 goals, goal 1453 chars | accepted commit |  |
| T0.0-20 | +04:36 | [4.9 s](./views/Tree_0_0/thinking/turn_020.md) | 1.1 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | probe sim | pRHL / call_site / relational_program, 1 goal, goal 845 chars | accepted probe |  |
| T0.0-21 | +04:45 | [7.8 s](./views/Tree_0_0/thinking/turn_021.md) | 161 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit sim | pRHL / call_site / relational_program, 1 goal, goal 845 chars | accepted commit |  |
| T0.0-22 | +04:50 | [4.8 s](./views/Tree_0_0/thinking/turn_022.md) | 159 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
