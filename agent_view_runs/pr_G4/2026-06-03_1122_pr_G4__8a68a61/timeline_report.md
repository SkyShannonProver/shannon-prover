# Agent-View Timeline — `pr_G4`

| field | value |
|---|---|
| commit | `8a68a61` |
| branch | `HEAD` |
| run time | 2026-06-03_1122_pr_G4 |
| lemma | `pr_G4` |
| source file | `eval/examples/cramer-shoup/cramer_shoup.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | incomplete (timeout/open) |
| turns | 29 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 13 tactic(s) committed, not closed

```easycrypt
proof.
  byphoare => //.
  proc.
  seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 1%r 1%r 0%r.
  trivial.
  seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r.
  conseq (_ : _ ==> (G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) (_ : _ ==> size G3.cilog <= PKE_.qD).
  seq 13 : (size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD).
  call (_: size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD).
  proc; auto; smt(size_ge0).
  auto; smt(PKE_.qD_pos).
  auto; smt().
  wp.
  seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-03_1122_pr_G4

Run dir: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1`

t=0: `2026-06-03T18:24:15.400000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | lookup mu_mem_le_mu1_size | probability / pr / probability, 1 goal, goal 236 chars | lookup result |  |
| T0.0-2 | +02:04 | [121.9 s](./views/Tree_0_0/thinking/turn_002.md) | 3.1 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | probe byphoare => // | probability / pr / probability, 1 goal, goal 236 chars | accepted probe |  |
| T0.0-3 | +02:11 | [4.7 s](./views/Tree_0_0/thinking/turn_003.md) | 262 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit byphoare => // | probability / pr / probability, 1 goal, goal 236 chars | accepted commit |  |
| T0.0-4 | +02:15 | [3.7 s](./views/Tree_0_0/thinking/turn_004.md) | 260 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 267 chars | accepted commit |  |
| T0.0-5 | +04:50 | [154.1 s](./views/Tree_0_0/thinking/turn_005.md) | 1.9 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | probe seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) ((PKE_.qD%r / order... | phoare / procedure_body / procedure_frontier, 1 goal, goal 2312 chars | accepted probe |  |
| T0.0-6 | +04:56 | [4.7 s](./views/Tree_0_0/thinking/turn_006.md) | 302 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) ((PKE_.qD%r / order... | phoare / procedure_body / seq_cut, 1 goal, goal 2312 chars | accepted commit |  |
| T0.0-7 | +05:19 | [22.5 s](./views/Tree_0_0/thinking/turn_007.md) | 1.5 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | inspect goal_info | hoare / procedure_body / procedure_frontier, 5 goals, goal 1427 chars | read-only inspect |  |
| T0.0-8 | +06:50 | [89.2 s](./views/Tree_0_0/thinking/turn_008.md) | 1.8 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | probe trivial | hoare / procedure_body / procedure_frontier, 5 goals, goal 1427 chars | accepted probe |  |
| T0.0-9 | +06:57 | [5.7 s](./views/Tree_0_0/thinking/turn_009.md) | 291 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit trivial | hoare / procedure_body / procedure_frontier, 5 goals, goal 1427 chars | accepted commit |  |
| T0.0-10 | +08:14 | [76.1 s](./views/Tree_0_0/thinking/turn_010.md) | 1.9 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | probe seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 *... | phoare / procedure_body / procedure_frontier, 4 goals, goal 1532 chars | accepted probe |  |
| T0.0-11 | +08:21 | [5 s](./views/Tree_0_0/thinking/turn_011.md) |  | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 *... | phoare / procedure_body / seq_cut, 4 goals, goal 1532 chars | accepted commit |  |
| T0.0-12 | +13:14 | [293.6 s](./views/Tree_0_0/thinking/turn_012.md) | 376 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | probe conseq (_ : _ ==> (G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) (_ : _ ==>... | phoare / procedure_body / seq_cut, 4 goals, goal 1532 chars | accepted probe |  |
| T0.0-13 | +13:40 | [25.6 s](./views/Tree_0_0/thinking/turn_013.md) | 360 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit conseq (_ : _ ==> (G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) (_ : _ ==>... | phoare / procedure_body / seq_cut, 4 goals, goal 1532 chars | accepted commit |  |
| T0.0-14 | +15:06 | [85.1 s](./views/Tree_0_0/thinking/turn_014.md) | 1.9 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | probe seq 13 : (size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD) | hoare / procedure_body / procedure_frontier, 5 goals, goal 1447 chars | accepted probe |  |
| T0.0-15 | +15:11 | [3.7 s](./views/Tree_0_0/thinking/turn_015.md) | 264 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit seq 13 : (size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD) | hoare / procedure_body / seq_cut, 5 goals, goal 1447 chars | accepted commit |  |
| T0.0-16 | +15:23 | [11.2 s](./views/Tree_0_0/thinking/turn_016.md) | 1.8 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | probe call size | hoare / procedure_body / seq_cut, 6 goals, goal 1037 chars | accepted probe |  |
| T0.0-17 | +15:28 | [3.7 s](./views/Tree_0_0/thinking/turn_017.md) | 266 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit call size | hoare / procedure_body / seq_cut, 6 goals, goal 1037 chars | accepted commit |  |
| T0.0-18 | +15:58 | [29.3 s](./views/Tree_0_0/thinking/turn_018.md) | 1.7 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | probe proc; sp; if; auto; smt(size_ge0) | hoare / procedure_body / seq_cut, 7 goals, goal 285 chars | rejected probe: invalid first instruction |  |
| T0.0-19 | +16:23 | [23.5 s](./views/Tree_0_0/thinking/turn_019.md) | 533 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | probe proc; auto; smt(size_ge0) | hoare / procedure_body / seq_cut, 7 goals, goal 285 chars | accepted probe |  |
| T0.0-20 | +16:27 | [3.5 s](./views/Tree_0_0/thinking/turn_020.md) | 450 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit proc; auto; smt(size_ge0) | hoare / procedure_body / seq_cut, 7 goals, goal 285 chars | accepted commit |  |
| T0.0-21 | +16:44 | [16.9 s](./views/Tree_0_0/thinking/turn_021.md) | 2.1 s | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | probe auto; smt(PKE_.qD_pos) | hoare / procedure_body / seq_cut, 6 goals, goal 706 chars | accepted probe |  |
| T0.0-22 | +16:51 | [4.4 s](./views/Tree_0_0/thinking/turn_022.md) | 608 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit auto; smt(PKE_.qD_pos) | hoare / procedure_body / seq_cut, 6 goals, goal 706 chars | accepted commit |  |
| T0.0-23 | +17:04 | [11.9 s](./views/Tree_0_0/thinking/turn_023.md) | 2.1 s | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | probe auto; smt() | hoare / procedure_body / procedure_frontier, 5 goals, goal 590 chars | accepted probe |  |
| T0.0-24 | +17:10 | [4.5 s](./views/Tree_0_0/thinking/turn_024.md) | 461 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit auto; smt() | hoare / procedure_body / procedure_frontier, 5 goals, goal 590 chars | accepted commit |  |
| T0.0-25 | +20:33 | [202.8 s](./views/Tree_0_0/thinking/turn_025.md) | 212 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | inspect tactic_forms | phoare / procedure_body / seq_cut, 4 goals, goal 1532 chars | read-only inspect |  |
| T0.0-26 | +22:06 | [92.5 s](./views/Tree_0_0/thinking/turn_026.md) | 455 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit wp | phoare / procedure_body / seq_cut, 4 goals, goal 1532 chars | accepted commit |  |
| T0.0-27 | +22:17 | [10.7 s](./views/Tree_0_0/thinking/turn_027.md) | 2.3 s | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | probe rnd | phoare / procedure_body / procedure_frontier, 4 goals, goal 1327 chars | accepted probe |  |
| T0.0-28 | +26:03 | [223 s](./views/Tree_0_0/thinking/turn_028.md) |  | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 *... | phoare / procedure_body / procedure_frontier, 4 goals, goal 1327 chars | accepted commit |  |
| T0.0-29 | +27:26 | [83.4 s](./views/Tree_0_0/thinking/turn_029.md) | 1.6 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | lookup dt1E | phoare / procedure_body / procedure_frontier, 4 goals, goal 1327 chars | lookup result |  |
