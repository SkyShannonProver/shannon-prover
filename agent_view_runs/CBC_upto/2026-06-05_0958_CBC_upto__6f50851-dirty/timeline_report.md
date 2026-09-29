# Agent-View Timeline — `CBC_upto`

| field | value |
|---|---|
| commit | `6f50851` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-05_0958_CBC_upto |
| lemma | `CBC_upto` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 104 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  rewrite (doublequery_eq PRFi &m) (doublequery_eq Sample &m).
  rewrite -(DQ_Sample_Compute_pr &m).
  byequiv: DoubleQuery.bad => //.
  proc.
  call (_: DoubleQuery.bad, ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2}, DoubleQuery.bad{1} = DoubleQuery.bad{2}).
  exact A_distinguish_ll.
  proc.
  seq 3 3: (={i, s, c, p} /\ !DoubleQuery.bad{2} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2}).
  auto.
  while (={i, p} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2} /\ (!DoubleQuery.bad{2} => ={s, c, DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})).
  inline *.
  case (DoubleQuery.bad{2}).
  conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2} /\ i{1} = i{2} /\ p{1} = p{2}).
  smt().
  wp.
  rnd{2}.
  seq 4 4: (DoubleQuery.bad{1} /\ DoubleQuery.bad{2} /\ i{1} = i{2} /\ p{1} = p{2}).
  sp.
  auto; smt().
  if{1}.
  auto; smt(dBlock_uffu).
  auto; smt(dBlock_uffu).
  seq 2 2: (={i, s, c, p, x, DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1} /\ !DoubleQuery.bad{2} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2} /\ i{1} < size p{1} /\ i{2} < size p{2}).
  auto.
  smt().
  if.
  smt().
  rcondf{1} 3.
  auto; smt(mem_fdom).
  wp.
  rnd{2}.
  auto; smt(dBlock_uffu).
  rcondt{1} 2.
  auto; smt(mem_fdom).
  auto; smt(get_set_sameE fdom_set).
  auto; smt().
  move=> &2 hbad; proc; inline*.
  while (DoubleQuery.bad) (size p - i).
  move=> z; auto.
  sp 4.
  if; auto; smt(dBlock_uffu).
  auto; smt(dBlock_uffu).
  move=> &1; proc; inline*.
  while (DoubleQuery.bad /\ DoubleQuery.bad{1} = DoubleQuery.bad) (size p - i).
  move=> z; auto; smt(dBlock_uffu).
  auto; smt(dBlock_uffu).
  inline*; auto; smt(fdom0).
  smt().
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-05_0958_CBC_upto

Run dir: `artifacts/eval_suite/cbc_upto_l1_rerun/l1_goal_projection/cbc_upto/r01/2026-06-05_0958_CBC_upto/iteration_1`

t=0: `2026-06-05T17:04:24.500000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit rewrite (doublequery_eq PRFi &m) (doublequery_eq Sample &m) | probability / pr / probability, 1 goal, goal 305 chars | accepted commit |  |
| T0.0-2 | +00:09 | [7.5 s](./views/Tree_0_0/thinking/turn_002.md) | 534 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit rewrite -(DQ_Sample_Compute_pr &m) | probability / pr / probability, 1 goal, goal 344 chars | accepted commit |  |
| T0.0-3 | +00:32 | 22 s |  | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | unknown | probability / pr / probability, 1 goal, goal 375 chars | repair / unhealthy |  |
| T0.0-4 | +00:40 | [8.6 s](./views/Tree_0_0/thinking/turn_004.md) | 1.4 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2}... | probability / pr / probability, 1 goal, goal 375 chars | rejected commit: proof state unchanged |  |
| T0.0-5 | +01:40 | [58.8 s](./views/Tree_0_0/thinking/turn_005.md) | 179 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit byequiv: DoubleQuery.bad => // | probability / pr / failure_diagnostic, 1 goal, goal 375 chars | accepted commit |  |
| T0.0-6 | +02:26 | [45.8 s](./views/Tree_0_0/thinking/turn_006.md) | 177 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 687 chars | accepted commit |  |
| T0.0-7 | +02:45 | [18.8 s](./views/Tree_0_0/thinking/turn_007.md) | 184 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit call DoubleQuery.bad | pRHL / call_site / relational_program, 2 goals, goal 670 chars | accepted commit |  |
| T0.0-8 | +02:56 | [10.8 s](./views/Tree_0_0/thinking/turn_008.md) | 164 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit exact A_distinguish_ll | ambient / ambient_logic, 6 goals, goal 227 chars | accepted commit |  |
| T0.0-9 | +05:23 | [146.8 s](./views/Tree_0_0/thinking/turn_009.md) | 208 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit proc | equiv / prhl_module / relational_program, 5 goals, goal 485 chars | accepted commit |  |
| T0.0-10 | +11:03 | [339.8 s](./views/Tree_0_0/thinking/turn_010.md) | 196 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit seq 3 3: (={i, s, c, p} /\ !DoubleQuery.bad{2} /\ ={DoubleQuery.qs} /... | pRHL / call_site / relational_program, 5 goals, goal 1415 chars | accepted commit |  |
| T0.0-11 | +11:07 | [3.8 s](./views/Tree_0_0/thinking/turn_011.md) | 227 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit auto | pRHL / verification_residue / relational_program, 6 goals, goal 678 chars | accepted commit |  |
| T0.0-12 | +11:19 | [11.8 s](./views/Tree_0_0/thinking/turn_012.md) | 206 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit while (={i, p} /\ (!DoubleQuery.bad{2} => ={s, c, DoubleQuery.qs} /\... | pRHL / call_site / relational_program, 5 goals, goal 1192 chars | accepted commit |  |
| T0.0-13 | +12:14 | [54.8 s](./views/Tree_0_0/thinking/turn_013.md) | 235 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit inline * | pRHL / call_site / relational_program, 6 goals, goal 1142 chars | accepted commit |  |
| T0.0-14 | +13:48 | [93.8 s](./views/Tree_0_0/thinking/turn_014.md) | 194 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit case (DoubleQuery.bad{2}) | pRHL / procedure_body / relational_program, 6 goals, goal 1838 chars | accepted commit |  |
| T0.0-15 | +14:51 | [62.8 s](./views/Tree_0_0/thinking/turn_015.md) | 180 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit conseq (_: _ ==> DoubleQuery.bad{2} /\ i{1} = i{2} /\ p{1} = p{2}) | pRHL / procedure_body / relational_program, 7 goals, goal 1868 chars | accepted commit |  |
| T0.0-16 | +15:00 | [8.7 s](./views/Tree_0_0/thinking/turn_016.md) | 265 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit smt() | ambient / ambient_logic / relational_program, 8 goals, goal 803 chars | accepted commit |  |
| T0.0-17 | +15:18 | [17.8 s](./views/Tree_0_0/thinking/turn_017.md) | 190 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit wp | pRHL / procedure_body / relational_program, 7 goals, goal 1692 chars | accepted commit |  |
| T0.0-18 | +15:56 | [37.8 s](./views/Tree_0_0/thinking/turn_018.md) | 208 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit rnd{2} | pRHL / procedure_body / relational_program, 7 goals, goal 1272 chars | accepted commit |  |
| T0.0-19 | +16:34 | [37.8 s](./views/Tree_0_0/thinking/turn_019.md) | 181 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit seq 4 4: (DoubleQuery.bad{2} /\ i{1} = i{2} /\ p{1} = p{2}) | pRHL / procedure_body / relational_program, 7 goals, goal 1348 chars | accepted commit |  |
| T0.0-20 | +16:40 | [5.8 s](./views/Tree_0_0/thinking/turn_020.md) | 203 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit auto | pRHL / verification_residue / relational_program, 8 goals, goal 837 chars | accepted commit |  |
| T0.0-21 | +16:59 | [18.8 s](./views/Tree_0_0/thinking/turn_021.md) | 205 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit if{1} | pRHL / procedure_body / relational_program, 7 goals, goal 741 chars | accepted commit |  |
| T0.0-22 | +17:18 | [18.8 s](./views/Tree_0_0/thinking/turn_022.md) | 228 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 8 goals, goal 639 chars | accepted commit |  |
| T0.0-23 | +17:27 | [8.8 s](./views/Tree_0_0/thinking/turn_023.md) | 218 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit auto; smt(dBlock_uffu) | pRHL / verification_residue / relational_program, 7 goals, goal 544 chars | accepted commit |  |
| T0.0-24 | +17:54 | [26.8 s](./views/Tree_0_0/thinking/turn_024.md) | 229 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit sp | pRHL / procedure_body / relational_program, 6 goals, goal 1869 chars | accepted commit |  |
| T0.0-25 | +18:06 | 11.8 s | 1.2 s | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | undo_last_step | pRHL / procedure_body / relational_program, 6 goals, goal 3591 chars | undo result |  |
| T0.0-26 | +18:38 | [30.8 s](./views/Tree_0_0/thinking/turn_026.md) | 1.2 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit seq 2 2: (={i, s, c, p, x, DoubleQuery.qs} /\ fdom PRFi.m{1} = Double... | pRHL / procedure_body / relational_program, 6 goals, goal 1856 chars | accepted commit |  |
| T0.0-27 | +18:44 | [4.8 s](./views/Tree_0_0/thinking/turn_027.md) | 179 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit auto | pRHL / verification_residue / relational_program, 7 goals, goal 872 chars | accepted commit |  |
| T0.0-28 | +18:53 | [8.8 s](./views/Tree_0_0/thinking/turn_028.md) | 232 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit smt() | ambient / ambient_logic / relational_program, 7 goals, goal 723 chars | accepted commit |  |
| T0.0-29 | +18:58 | [4.8 s](./views/Tree_0_0/thinking/turn_029.md) | 195 ms | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit if | pRHL / procedure_body / relational_program, 6 goals, goal 1697 chars | accepted commit |  |
| T0.0-30 | +19:03 | [4.8 s](./views/Tree_0_0/thinking/turn_030.md) | 239 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit smt() | ambient / ambient_logic / relational_program, 8 goals, goal 453 chars | accepted commit |  |
| T0.0-31 | +19:47 | [43.8 s](./views/Tree_0_0/thinking/turn_031.md) | 160 ms | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | commit rcondf{1} 3 | pRHL / procedure_body / relational_program, 7 goals, goal 1604 chars | accepted commit |  |
| T0.0-32 | +20:00 | [12.8 s](./views/Tree_0_0/thinking/turn_032.md) | 247 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit auto; smt(mem_fdom) | ambient / ambient_logic, 8 goals, goal 530 chars | accepted commit |  |
| T0.0-33 | +20:11 | [10.8 s](./views/Tree_0_0/thinking/turn_033.md) | 203 ms | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | commit wp | pRHL / procedure_body / relational_program, 7 goals, goal 1440 chars | accepted commit |  |
| T0.0-34 | +20:28 | [16.8 s](./views/Tree_0_0/thinking/turn_034.md) | 213 ms | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | commit rnd{2} | pRHL / procedure_body / relational_program, 7 goals, goal 1123 chars | accepted commit |  |
| T0.0-35 | +20:39 | [10.8 s](./views/Tree_0_0/thinking/turn_035.md) | 235 ms | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | commit auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 7 goals, goal 1157 chars | accepted commit |  |
| T0.0-36 | +20:55 | [15.9 s](./views/Tree_0_0/thinking/turn_036.md) | 148 ms | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit rcondt{1} 2 | pRHL / procedure_body / relational_program, 6 goals, goal 1540 chars | accepted commit |  |
| T0.0-37 | +21:01 | [5.6 s](./views/Tree_0_0/thinking/turn_037.md) | 1.4 s | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | commit auto; smt(mem_fdom) | ambient / ambient_logic, 7 goals, goal 504 chars | accepted commit |  |
| T0.0-38 | +21:25 | [22.7 s](./views/Tree_0_0/thinking/turn_038.md) | 284 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit auto; smt(get_set_sameE fdom_set) | pRHL / procedure_body / seq_cut, 6 goals, goal 1443 chars | accepted commit |  |
| T0.0-39 | +21:42 | [16.8 s](./views/Tree_0_0/thinking/turn_039.md) | 210 ms | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | commit auto; smt() | pRHL / verification_residue / relational_program, 5 goals, goal 1110 chars | accepted commit |  |
| T0.0-40 | +22:24 | [41.8 s](./views/Tree_0_0/thinking/turn_040.md) | 175 ms | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit move=> &2 _; proc; inline* | ambient / ambient_logic, 4 goals, goal 223 chars | accepted commit |  |
| T0.0-41 | +22:40 | [15.8 s](./views/Tree_0_0/thinking/turn_041.md) | 188 ms | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | commit while (true) (size p - i) | phoare / procedure_body / procedure_frontier, 4 goals, goal 1407 chars | accepted commit |  |
| T0.0-42 | +22:55 | [14.5 s](./views/Tree_0_0/thinking/turn_042.md) | 4.5 s | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit move=> z; auto; smt(dBlock_uffu) | ambient / ambient_logic, 5 goals, goal 292 chars | rejected commit: proof state unchanged |  |
| T0.0-43 | +23:39 | [39.8 s](./views/Tree_0_0/thinking/turn_043.md) | 165 ms | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | commit move=> z; auto | ambient / ambient_logic, 5 goals, goal 292 chars | accepted commit |  |
| T0.0-44 | +25:51 | [131.8 s](./views/Tree_0_0/thinking/turn_044.md) | 174 ms | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | commit sp 4 | phoare / procedure_body / procedure_frontier, 5 goals, goal 684 chars | accepted commit |  |
| T0.0-45 | +26:02 | [10.8 s](./views/Tree_0_0/thinking/turn_045.md) | 234 ms | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | commit if; auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 5 goals, goal 805 chars | accepted commit |  |
| T0.0-46 | +26:10 | [7.8 s](./views/Tree_0_0/thinking/turn_046.md) | 195 ms | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | commit auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 4 goals, goal 418 chars | accepted commit |  |
| T0.0-47 | +26:23 | [12.8 s](./views/Tree_0_0/thinking/turn_047.md) | 172 ms | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | commit move=> _; proc; inline* | ambient / ambient_logic, 3 goals, goal 277 chars | accepted commit |  |
| T0.0-48 | +26:32 | [8.8 s](./views/Tree_0_0/thinking/turn_048.md) | 153 ms | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | commit while (DoubleQuery.bad) (size p - i) | phoare / procedure_body / procedure_frontier, 3 goals, goal 1267 chars | accepted commit |  |
| T0.0-49 | +26:46 | [13.8 s](./views/Tree_0_0/thinking/turn_049.md) | 186 ms | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | commit move=> z; auto; smt(dBlock_uffu) | ambient / ambient_logic, 4 goals, goal 336 chars | accepted commit |  |
| T0.0-50 | +26:52 | [5.8 s](./views/Tree_0_0/thinking/turn_050.md) | 219 ms | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | commit auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 3 goals, goal 514 chars | accepted commit |  |
| T0.0-51 | +27:08 | [15.4 s](./views/Tree_0_0/thinking/turn_051.md) | 4.6 s | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit inline*; auto; smt(fdom0) | pRHL / procedure_body / relational_program, 2 goals, goal 826 chars | rejected commit: proof state unchanged |  |
| T0.0-52 | +34:50 | 457 s |  | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | fresh_restart | pRHL / procedure_body / relational_program, 2 goals, goal 826 chars | fresh restart confirmation requested |  |
| T0.0-53 | +35:04 | [15 s](./views/Tree_0_0/thinking/turn_053.md) |  | [turn_052.json](./views/Tree_0_0/turn_052.json) · [inline read](./views/Tree_0_0/followups/turn_052.md) | fresh_restart | pRHL / procedure_body / relational_program, 2 goals, goal 826 chars | fresh restart confirmed |  |
| T0.0-54 | +35:23 | [18.9 s](./views/Tree_0_0/thinking/turn_054.md) | 1.1 s | [turn_053.json](./views/Tree_0_0/turn_053.json) · [inline read](./views/Tree_0_0/followups/turn_053.md) | fresh_restart | pRHL / procedure_body / relational_program, 2 goals, goal 826 chars | fresh restart confirmed |  |
| T0.0-55 | +35:31 | [6.6 s](./views/Tree_0_0/thinking/turn_055.md) | 1.4 s | [turn_054.json](./views/Tree_0_0/turn_054.json) · [inline read](./views/Tree_0_0/followups/turn_054.md) | commit rewrite (doublequery_eq PRFi &m) (doublequery_eq Sample &m) | probability / pr / probability, 1 goal, goal 305 chars | accepted commit |  |
| T0.0-56 | +35:37 | 4.5 s | 543 ms | [turn_055.json](./views/Tree_0_0/turn_055.json) · [inline read](./views/Tree_0_0/followups/turn_055.md) | commit rewrite -(DQ_Sample_Compute_pr &m) | probability / pr / probability, 1 goal, goal 344 chars | accepted commit |  |
| T0.0-57 | +35:41 | 3.8 s | 176 ms | [turn_056.json](./views/Tree_0_0/turn_056.json) · [inline read](./views/Tree_0_0/followups/turn_056.md) | commit byequiv: DoubleQuery.bad => // | probability / pr / probability, 1 goal, goal 375 chars | accepted commit |  |
| T0.0-58 | +35:44 | 2.8 s | 196 ms | [turn_057.json](./views/Tree_0_0/turn_057.json) · [inline read](./views/Tree_0_0/followups/turn_057.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 687 chars | accepted commit |  |
| T0.0-59 | +35:52 | [7.8 s](./views/Tree_0_0/thinking/turn_059.md) | 153 ms | [turn_058.json](./views/Tree_0_0/turn_058.json) · [inline read](./views/Tree_0_0/followups/turn_058.md) | commit call DoubleQuery.bad | pRHL / call_site / relational_program, 2 goals, goal 670 chars | accepted commit |  |
| T0.0-60 | +36:05 | [12.8 s](./views/Tree_0_0/thinking/turn_060.md) | 162 ms | [turn_059.json](./views/Tree_0_0/turn_059.json) · [inline read](./views/Tree_0_0/followups/turn_059.md) | commit exact A_distinguish_ll | ambient / ambient_logic, 6 goals, goal 227 chars | accepted commit |  |
| T0.0-61 | +36:21 | [15.8 s](./views/Tree_0_0/thinking/turn_061.md) | 190 ms | [turn_060.json](./views/Tree_0_0/turn_060.json) · [inline read](./views/Tree_0_0/followups/turn_060.md) | commit proc | equiv / prhl_module / relational_program, 5 goals, goal 638 chars | accepted commit |  |
| T0.0-62 | +36:28 | [6.8 s](./views/Tree_0_0/thinking/turn_062.md) | 173 ms | [turn_061.json](./views/Tree_0_0/turn_061.json) · [inline read](./views/Tree_0_0/followups/turn_061.md) | commit seq 3 3: (={i, s, c, p} /\ !DoubleQuery.bad{2} /\ ={DoubleQuery.qs} /... | pRHL / call_site / relational_program, 5 goals, goal 1568 chars | accepted commit |  |
| T0.0-63 | +36:33 | [4.8 s](./views/Tree_0_0/thinking/turn_063.md) | 230 ms | [turn_062.json](./views/Tree_0_0/turn_062.json) · [inline read](./views/Tree_0_0/followups/turn_062.md) | commit auto | pRHL / verification_residue / relational_program, 6 goals, goal 772 chars | accepted commit |  |
| T0.0-64 | +36:40 | [6.8 s](./views/Tree_0_0/thinking/turn_064.md) | 192 ms | [turn_063.json](./views/Tree_0_0/turn_063.json) · [inline read](./views/Tree_0_0/followups/turn_063.md) | commit while (={i, p} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2} /\ (!Double... | pRHL / call_site / relational_program, 5 goals, goal 1345 chars | accepted commit |  |
| T0.0-65 | +36:45 | [4.8 s](./views/Tree_0_0/thinking/turn_065.md) | 214 ms | [turn_064.json](./views/Tree_0_0/turn_064.json) · [inline read](./views/Tree_0_0/followups/turn_064.md) | commit inline * | pRHL / call_site / relational_program, 6 goals, goal 1234 chars | accepted commit |  |
| T0.0-66 | +36:50 | 4.8 s | 215 ms | [turn_065.json](./views/Tree_0_0/turn_065.json) · [inline read](./views/Tree_0_0/followups/turn_065.md) | commit case (DoubleQuery.bad{2}) | pRHL / procedure_body / relational_program, 6 goals, goal 1930 chars | accepted commit |  |
| T0.0-67 | +37:05 | [14.8 s](./views/Tree_0_0/thinking/turn_067.md) | 179 ms | [turn_066.json](./views/Tree_0_0/turn_066.json) · [inline read](./views/Tree_0_0/followups/turn_066.md) | commit conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2} /\ i{1} = i... | pRHL / procedure_body / relational_program, 7 goals, goal 1961 chars | accepted commit |  |
| T0.0-68 | +37:11 | [5.8 s](./views/Tree_0_0/thinking/turn_068.md) | 250 ms | [turn_067.json](./views/Tree_0_0/turn_067.json) · [inline read](./views/Tree_0_0/followups/turn_067.md) | commit smt() | ambient / ambient_logic / relational_program, 8 goals, goal 896 chars | accepted commit |  |
| T0.0-69 | +37:32 | [20.8 s](./views/Tree_0_0/thinking/turn_069.md) | 183 ms | [turn_068.json](./views/Tree_0_0/turn_068.json) · [inline read](./views/Tree_0_0/followups/turn_068.md) | commit wp | pRHL / procedure_body / relational_program, 7 goals, goal 1761 chars | accepted commit |  |
| T0.0-70 | +37:40 | [7.8 s](./views/Tree_0_0/thinking/turn_070.md) | 229 ms | [turn_069.json](./views/Tree_0_0/turn_069.json) · [inline read](./views/Tree_0_0/followups/turn_069.md) | commit rnd{2} | pRHL / procedure_body / relational_program, 7 goals, goal 1345 chars | accepted commit |  |
| T0.0-71 | +37:48 | [7.8 s](./views/Tree_0_0/thinking/turn_071.md) | 208 ms | [turn_070.json](./views/Tree_0_0/turn_070.json) · [inline read](./views/Tree_0_0/followups/turn_070.md) | commit seq 4 4: (DoubleQuery.bad{1} /\ DoubleQuery.bad{2} /\ i{1} = i{2} /\... | pRHL / procedure_body / relational_program, 7 goals, goal 1421 chars | accepted commit |  |
| T0.0-72 | +38:24 | [35.8 s](./views/Tree_0_0/thinking/turn_072.md) | 210 ms | [turn_071.json](./views/Tree_0_0/turn_071.json) · [inline read](./views/Tree_0_0/followups/turn_071.md) | commit sp | pRHL / verification_residue / relational_program, 8 goals, goal 906 chars | accepted commit |  |
| T0.0-73 | +38:38 | [13.8 s](./views/Tree_0_0/thinking/turn_073.md) | 232 ms | [turn_072.json](./views/Tree_0_0/turn_072.json) · [inline read](./views/Tree_0_0/followups/turn_072.md) | commit auto; smt() | pRHL / verification_residue / relational_program, 8 goals, goal 3089 chars | accepted commit |  |
| T0.0-74 | +38:46 | [7.8 s](./views/Tree_0_0/thinking/turn_074.md) | 207 ms | [turn_073.json](./views/Tree_0_0/turn_073.json) · [inline read](./views/Tree_0_0/followups/turn_073.md) | commit if{1} | pRHL / procedure_body / relational_program, 7 goals, goal 789 chars | accepted commit |  |
| T0.0-75 | +38:50 | [3.8 s](./views/Tree_0_0/thinking/turn_075.md) | 249 ms | [turn_074.json](./views/Tree_0_0/turn_074.json) · [inline read](./views/Tree_0_0/followups/turn_074.md) | commit auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 8 goals, goal 687 chars | accepted commit |  |
| T0.0-76 | +38:55 | [4.8 s](./views/Tree_0_0/thinking/turn_076.md) | 224 ms | [turn_075.json](./views/Tree_0_0/turn_075.json) · [inline read](./views/Tree_0_0/followups/turn_075.md) | commit auto; smt(dBlock_uffu) | pRHL / verification_residue / relational_program, 7 goals, goal 592 chars | accepted commit |  |
| T0.0-77 | +39:05 | [9.8 s](./views/Tree_0_0/thinking/turn_077.md) | 187 ms | [turn_076.json](./views/Tree_0_0/turn_076.json) · [inline read](./views/Tree_0_0/followups/turn_076.md) | commit seq 2 2: (={i, s, c, p, x, DoubleQuery.qs} /\ fdom PRFi.m{1} = Double... | pRHL / procedure_body / relational_program, 6 goals, goal 1962 chars | accepted commit |  |
| T0.0-78 | +39:10 | [4.8 s](./views/Tree_0_0/thinking/turn_078.md) | 200 ms | [turn_077.json](./views/Tree_0_0/turn_077.json) · [inline read](./views/Tree_0_0/followups/turn_077.md) | commit auto | pRHL / verification_residue / relational_program, 7 goals, goal 966 chars | accepted commit |  |
| T0.0-79 | +39:14 | 3.8 s | 210 ms | [turn_078.json](./views/Tree_0_0/turn_078.json) · [inline read](./views/Tree_0_0/followups/turn_078.md) | commit smt() | ambient / ambient_logic / relational_program, 7 goals, goal 817 chars | accepted commit |  |
| T0.0-80 | +39:27 | [12.8 s](./views/Tree_0_0/thinking/turn_080.md) | 182 ms | [turn_079.json](./views/Tree_0_0/turn_079.json) · [inline read](./views/Tree_0_0/followups/turn_079.md) | commit if | pRHL / procedure_body / relational_program, 6 goals, goal 1790 chars | accepted commit |  |
| T0.0-81 | +39:34 | [6.8 s](./views/Tree_0_0/thinking/turn_081.md) | 241 ms | [turn_080.json](./views/Tree_0_0/turn_080.json) · [inline read](./views/Tree_0_0/followups/turn_080.md) | commit smt() | ambient / ambient_logic / relational_program, 8 goals, goal 500 chars | accepted commit |  |
| T0.0-82 | +39:46 | [11.8 s](./views/Tree_0_0/thinking/turn_082.md) | 177 ms | [turn_081.json](./views/Tree_0_0/turn_081.json) · [inline read](./views/Tree_0_0/followups/turn_081.md) | commit rcondf{1} 3 | pRHL / procedure_body / relational_program, 7 goals, goal 1699 chars | accepted commit |  |
| T0.0-83 | +39:54 | [7.8 s](./views/Tree_0_0/thinking/turn_083.md) | 222 ms | [turn_082.json](./views/Tree_0_0/turn_082.json) · [inline read](./views/Tree_0_0/followups/turn_082.md) | commit auto; smt(mem_fdom) | ambient / ambient_logic, 8 goals, goal 593 chars | accepted commit |  |
| T0.0-84 | +40:03 | [8.8 s](./views/Tree_0_0/thinking/turn_084.md) | 191 ms | [turn_083.json](./views/Tree_0_0/turn_083.json) · [inline read](./views/Tree_0_0/followups/turn_083.md) | commit wp | pRHL / procedure_body / relational_program, 7 goals, goal 1535 chars | accepted commit |  |
| T0.0-85 | +40:17 | [13.8 s](./views/Tree_0_0/thinking/turn_085.md) | 216 ms | [turn_084.json](./views/Tree_0_0/turn_084.json) · [inline read](./views/Tree_0_0/followups/turn_084.md) | commit rnd{2} | pRHL / procedure_body / relational_program, 7 goals, goal 1204 chars | accepted commit |  |
| T0.0-86 | +40:31 | [13.8 s](./views/Tree_0_0/thinking/turn_086.md) | 238 ms | [turn_085.json](./views/Tree_0_0/turn_085.json) · [inline read](./views/Tree_0_0/followups/turn_085.md) | commit auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 7 goals, goal 1240 chars | accepted commit |  |
| T0.0-87 | +40:35 | [3.8 s](./views/Tree_0_0/thinking/turn_087.md) | 154 ms | [turn_086.json](./views/Tree_0_0/turn_086.json) · [inline read](./views/Tree_0_0/followups/turn_086.md) | commit rcondt{1} 2 | pRHL / procedure_body / relational_program, 6 goals, goal 1635 chars | accepted commit |  |
| T0.0-88 | +40:40 | 4.5 s | 1.5 s | [turn_087.json](./views/Tree_0_0/turn_087.json) · [inline read](./views/Tree_0_0/followups/turn_087.md) | commit auto; smt(mem_fdom) | ambient / ambient_logic, 7 goals, goal 567 chars | accepted commit |  |
| T0.0-89 | +40:50 | [8.7 s](./views/Tree_0_0/thinking/turn_089.md) | 252 ms | [turn_088.json](./views/Tree_0_0/turn_088.json) · [inline read](./views/Tree_0_0/followups/turn_088.md) | commit auto; smt(get_set_sameE fdom_set) | pRHL / procedure_body / seq_cut, 6 goals, goal 1538 chars | accepted commit |  |
| T0.0-90 | +41:00 | [9.8 s](./views/Tree_0_0/thinking/turn_090.md) | 208 ms | [turn_089.json](./views/Tree_0_0/turn_089.json) · [inline read](./views/Tree_0_0/followups/turn_089.md) | commit auto; smt() | pRHL / verification_residue / relational_program, 5 goals, goal 1284 chars | accepted commit |  |
| T0.0-91 | +41:41 | [40.8 s](./views/Tree_0_0/thinking/turn_091.md) | 176 ms | [turn_090.json](./views/Tree_0_0/turn_090.json) · [inline read](./views/Tree_0_0/followups/turn_090.md) | commit move=> &2 hbad; proc; inline* | ambient / ambient_logic, 4 goals, goal 337 chars | accepted commit |  |
| T0.0-92 | +41:49 | [7.8 s](./views/Tree_0_0/thinking/turn_092.md) | 188 ms | [turn_091.json](./views/Tree_0_0/turn_091.json) · [inline read](./views/Tree_0_0/followups/turn_091.md) | commit while (DoubleQuery.bad) (size p - i) | phoare / procedure_body / procedure_frontier, 4 goals, goal 1496 chars | accepted commit |  |
| T0.0-93 | +42:05 | [15.8 s](./views/Tree_0_0/thinking/turn_093.md) | 179 ms | [turn_092.json](./views/Tree_0_0/turn_092.json) · [inline read](./views/Tree_0_0/followups/turn_092.md) | commit move=> z; auto | ambient / ambient_logic, 5 goals, goal 368 chars | accepted commit |  |
| T0.0-94 | +42:14 | [8.8 s](./views/Tree_0_0/thinking/turn_094.md) | 177 ms | [turn_093.json](./views/Tree_0_0/turn_093.json) · [inline read](./views/Tree_0_0/followups/turn_093.md) | commit sp 4 | phoare / procedure_body / procedure_frontier, 5 goals, goal 749 chars | accepted commit |  |
| T0.0-95 | +42:28 | [13.8 s](./views/Tree_0_0/thinking/turn_095.md) | 226 ms | [turn_094.json](./views/Tree_0_0/turn_094.json) · [inline read](./views/Tree_0_0/followups/turn_094.md) | commit if; auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 5 goals, goal 926 chars | accepted commit |  |
| T0.0-96 | +42:40 | [11.8 s](./views/Tree_0_0/thinking/turn_096.md) | 233 ms | [turn_095.json](./views/Tree_0_0/turn_095.json) · [inline read](./views/Tree_0_0/followups/turn_095.md) | commit auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 4 goals, goal 572 chars | accepted commit |  |
| T0.0-97 | +43:03 | [22.8 s](./views/Tree_0_0/thinking/turn_097.md) | 169 ms | [turn_096.json](./views/Tree_0_0/turn_096.json) · [inline read](./views/Tree_0_0/followups/turn_096.md) | commit move=> &1; proc; inline* | ambient / ambient_logic, 3 goals, goal 353 chars | accepted commit |  |
| T0.0-98 | +43:14 | [10.8 s](./views/Tree_0_0/thinking/turn_098.md) | 198 ms | [turn_097.json](./views/Tree_0_0/turn_097.json) · [inline read](./views/Tree_0_0/followups/turn_097.md) | commit while (DoubleQuery.bad /\ DoubleQuery.bad{1} = DoubleQuery.bad) (size... | phoare / procedure_body / procedure_frontier, 3 goals, goal 1338 chars | accepted commit |  |
| T0.0-99 | +43:22 | [7.8 s](./views/Tree_0_0/thinking/turn_099.md) | 200 ms | [turn_098.json](./views/Tree_0_0/turn_098.json) · [inline read](./views/Tree_0_0/followups/turn_098.md) | commit move=> z; auto; smt(dBlock_uffu) | ambient / ambient_logic, 4 goals, goal 461 chars | accepted commit |  |
| T0.0-100 | +43:28 | [5.8 s](./views/Tree_0_0/thinking/turn_100.md) | 228 ms | [turn_099.json](./views/Tree_0_0/turn_099.json) · [inline read](./views/Tree_0_0/followups/turn_099.md) | commit auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 3 goals, goal 590 chars | accepted commit |  |
| T0.0-101 | +43:37 | [8.8 s](./views/Tree_0_0/thinking/turn_101.md) | 217 ms | [turn_100.json](./views/Tree_0_0/turn_100.json) · [inline read](./views/Tree_0_0/followups/turn_100.md) | commit inline*; auto; smt(fdom0) | pRHL / procedure_body / relational_program, 2 goals, goal 988 chars | accepted commit |  |
| T0.0-102 | +43:47 | [9.8 s](./views/Tree_0_0/thinking/turn_102.md) | 187 ms | [turn_101.json](./views/Tree_0_0/turn_101.json) · [inline read](./views/Tree_0_0/followups/turn_101.md) | commit smt() | ambient / ambient_logic / relational_program, 1 goal, goal 333 chars | accepted commit |  |
| T0.0-103 | +43:52 | [4.9 s](./views/Tree_0_0/thinking/turn_103.md) | 148 ms | [turn_102.json](./views/Tree_0_0/turn_102.json) · [inline read](./views/Tree_0_0/followups/turn_102.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-104 | +44:42 | 50 s |  | [turn_103.json](./views/Tree_0_0/turn_103.json) · [inline read](./views/Tree_0_0/followups/turn_103.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
