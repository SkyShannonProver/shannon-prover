# Agent-View Timeline — `cpa_ddh0`

| field | value |
|---|---|
| commit | `ef713ea` |
| branch | `ablation/l1-l4-surface` |
| run time | 2026-06-01_1402_cpa_ddh0 |
| lemma | `cpa_ddh0` |
| source file | `eval/examples/elgamal.ec` |
| model | `claude-opus-4-6` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 41 |

Each row below: the view the agent saw → the intent it submitted → the manager result. Click a `turn_NNN.json` link to open that step's exact `ProverWorkspaceView` (copied into `./views/`).

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  swap{1} 7 -5.
  wp.
  call (_: ={glob A}).
  call (_: true).
  wp.
  rnd.
  call (_: true).
  wp.
  rnd.
  rnd.
  skip.
  smt(pow_pow).
  progress.
  smt().
  congr.
  exact pow_pow.
  by rewrite expM.
  qed.
```

### `Tree_0_1` — incomplete — 19 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  swap{1} 7 -3.
  wp.
  call (_: true).
  wp.
  rnd.
  swap{1} 4 -1.
  call (_: true).
  wp.
  rnd.
  wp.
  rnd.
  skip.
  progress.
  by rewrite pow_pow.
  congr.
  smt().
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-01_1402_cpa_ddh0

Run dir: `artifacts/eval_suite/l1_l4_surface_ablation/l1_goal_projection/cpa_ddh0_exec/r01/2026-06-01_1402_cpa_ddh0/iteration_1`

t=0: `2026-06-01T21:02:55.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 195 chars | accepted commit |  |
| T0.0-2 | +00:25 | [22.9 s](./views/Tree_0_0/thinking/turn_002.md) | 2.1 s | [turn_001.json](./views/Tree_0_0/turn_001.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 264 chars | accepted commit |  |
| T0.0-3 | +00:43 | [16.2 s](./views/Tree_0_0/thinking/turn_003.md) | 1.8 s | [turn_002.json](./views/Tree_0_0/turn_002.json) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 963 chars | accepted commit |  |
| T0.0-4 | +02:58 | [133.6 s](./views/Tree_0_0/thinking/turn_004.md) | 1.4 s | [turn_003.json](./views/Tree_0_0/turn_003.json) | commit swap{1} 7 -5 | pRHL / call_site / seq_cut, 1 goal, goal 1158 chars | accepted commit |  |
| T0.0-5 | +03:12 | [12.7 s](./views/Tree_0_0/thinking/turn_005.md) | 1.3 s | [turn_004.json](./views/Tree_0_0/turn_004.json) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 1158 chars | accepted commit |  |
| T0.0-6 | +03:58 | [44.6 s](./views/Tree_0_0/thinking/turn_006.md) | 2.4 s | [turn_005.json](./views/Tree_0_0/turn_005.json) | commit call (_: ={glob A}) | pRHL / call_site / relational_program, 1 goal, goal 1169 chars | rejected commit: proof state unchanged |  |
| T0.0-7 | +05:38 | [97.6 s](./views/Tree_0_0/thinking/turn_007.md) | 1.4 s | [turn_006.json](./views/Tree_0_0/turn_006.json) | commit call true | pRHL / call_site / failure_diagnostic, 1 goal, goal 1169 chars | accepted commit |  |
| T0.0-8 | +06:16 | [36.7 s](./views/Tree_0_0/thinking/turn_008.md) | 1.3 s | [turn_007.json](./views/Tree_0_0/turn_007.json) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 1144 chars | accepted commit |  |
| T0.0-9 | +06:43 | [25.6 s](./views/Tree_0_0/thinking/turn_009.md) | 1.4 s | [turn_008.json](./views/Tree_0_0/turn_008.json) | commit rnd | pRHL / call_site / seq_cut, 1 goal, goal 1140 chars | accepted commit |  |
| T0.0-10 | +07:21 | [36.6 s](./views/Tree_0_0/thinking/turn_010.md) | 1.4 s | [turn_009.json](./views/Tree_0_0/turn_009.json) | commit call true | pRHL / call_site / relational_program, 1 goal, goal 1195 chars | accepted commit |  |
| T0.0-11 | +07:46 | [23.7 s](./views/Tree_0_0/thinking/turn_011.md) | 308 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 1345 chars | accepted commit |  |
| T0.0-12 | +07:56 | [8.8 s](./views/Tree_0_0/thinking/turn_012.md) | 239 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) | commit rnd | pRHL / procedure_body / relational_program, 1 goal, goal 1209 chars | accepted commit |  |
| T0.0-13 | +08:04 | [7.8 s](./views/Tree_0_0/thinking/turn_013.md) | 231 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) | commit rnd | pRHL / procedure_body / seq_cut, 1 goal, goal 1283 chars | accepted commit |  |
| T0.0-14 | +08:12 | [7.8 s](./views/Tree_0_0/thinking/turn_014.md) | 229 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) | commit skip | pRHL / procedure_entry / relational_program, 1 goal, goal 1379 chars | accepted commit |  |
| T0.0-15 | +08:38 | [26.6 s](./views/Tree_0_0/thinking/turn_015.md) | 1.4 s | [turn_014.json](./views/Tree_0_0/turn_014.json) | commit smt(pow_pow) | ambient / ambient_logic / relational_program, 1 goal, goal 1161 chars | rejected commit: proof state unchanged |  |
| T0.0-16 | +08:49 | [8.8 s](./views/Tree_0_0/thinking/turn_016.md) | 250 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) | commit progress | ambient / ambient_logic / relational_program, 1 goal, goal 1161 chars | accepted commit |  |
| T0.0-17 | +09:11 | [22.3 s](./views/Tree_0_0/thinking/turn_017.md) | 4.7 s | [turn_016.json](./views/Tree_0_0/turn_016.json) | commit smt() | ambient / ambient_logic, 1 goal, goal 553 chars | rejected commit: proof state unchanged |  |
| T0.0-18 | +09:55 | [38.7 s](./views/Tree_0_0/thinking/turn_018.md) | 297 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) | commit congr | ambient / ambient_logic, 1 goal, goal 553 chars | accepted commit |  |
| T0.0-19 | +10:07 | [12.5 s](./views/Tree_0_0/thinking/turn_019.md) | 1.5 s | [turn_018.json](./views/Tree_0_0/turn_018.json) | commit exact pow_pow | ambient / ambient_logic, 1 goal, goal 467 chars | rejected commit: proof state unchanged |  |
| T0.0-20 | +11:05 | [55.7 s](./views/Tree_0_0/thinking/turn_020.md) | 287 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) | commit by rewrite expM | ambient / ambient_logic, 1 goal, goal 467 chars | accepted commit |  |
| T0.0-21 | +11:10 | [4.8 s](./views/Tree_0_0/thinking/turn_021.md) | 199 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-22 | +11:14 | 4 s |  | [turn_021.json](./views/Tree_0_0/turn_021.json) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +01:22 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 195 chars | accepted commit |  |
| T0.1-2 | +01:31 | [7.4 s](./views/Tree_0_1/thinking/turn_002.md) | 1.6 s | [turn_001.json](./views/Tree_0_1/turn_001.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 264 chars | accepted commit |  |
| T0.1-3 | +01:44 | [10.7 s](./views/Tree_0_1/thinking/turn_003.md) | 1.3 s | [turn_002.json](./views/Tree_0_1/turn_002.json) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 963 chars | accepted commit |  |
| T0.1-4 | +03:04 | [79.7 s](./views/Tree_0_1/thinking/turn_004.md) | 1.3 s | [turn_003.json](./views/Tree_0_1/turn_003.json) | commit swap{1} 7 -3 | pRHL / call_site / seq_cut, 1 goal, goal 1158 chars | accepted commit |  |
| T0.1-5 | +03:47 | [41.5 s](./views/Tree_0_1/thinking/turn_005.md) | 1.5 s | [turn_004.json](./views/Tree_0_1/turn_004.json) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 1158 chars | accepted commit |  |
| T0.1-6 | +04:28 | [39.5 s](./views/Tree_0_1/thinking/turn_006.md) | 1.5 s | [turn_005.json](./views/Tree_0_1/turn_005.json) | commit call true | pRHL / call_site / relational_program, 1 goal, goal 1169 chars | accepted commit |  |
| T0.1-7 | +04:57 | [27.5 s](./views/Tree_0_1/thinking/turn_007.md) | 1.5 s | [turn_006.json](./views/Tree_0_1/turn_006.json) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 1144 chars | accepted commit |  |
| T0.1-8 | +05:22 | [23.5 s](./views/Tree_0_1/thinking/turn_008.md) | 1.5 s | [turn_007.json](./views/Tree_0_1/turn_007.json) | commit rnd | pRHL / call_site / seq_cut, 1 goal, goal 1140 chars | accepted commit |  |
| T0.1-9 | +05:55 | [31.6 s](./views/Tree_0_1/thinking/turn_009.md) | 3.4 s | [turn_008.json](./views/Tree_0_1/turn_008.json) | commit swap{1} 4 -1 | pRHL / call_site / seq_cut, 1 goal, goal 1195 chars | accepted commit |  |
| T0.1-10 | +06:05 | [6.6 s](./views/Tree_0_1/thinking/turn_010.md) | 3.4 s | [turn_009.json](./views/Tree_0_1/turn_009.json) | commit call true | pRHL / call_site / relational_program, 1 goal, goal 1195 chars | accepted commit |  |
| T0.1-11 | +06:29 | [20.6 s](./views/Tree_0_1/thinking/turn_011.md) | 3.4 s | [turn_010.json](./views/Tree_0_1/turn_010.json) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 1345 chars | accepted commit |  |
| T0.1-12 | +06:56 | [23.6 s](./views/Tree_0_1/thinking/turn_012.md) | 1.4 s | [turn_011.json](./views/Tree_0_1/turn_011.json) | commit rnd | pRHL / procedure_body / seq_cut, 1 goal, goal 1245 chars | accepted commit |  |
| T0.1-13 | +07:06 | [7.7 s](./views/Tree_0_1/thinking/turn_013.md) | 257 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 1316 chars | accepted commit |  |
| T0.1-14 | +07:12 | [5.8 s](./views/Tree_0_1/thinking/turn_014.md) | 246 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) | commit rnd | pRHL / procedure_body / seq_cut, 1 goal, goal 1281 chars | accepted commit |  |
| T0.1-15 | +07:25 | [12.8 s](./views/Tree_0_1/thinking/turn_015.md) | 228 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) | commit skip | pRHL / procedure_entry / relational_program, 1 goal, goal 1377 chars | accepted commit |  |
| T0.1-16 | +08:02 | [36.7 s](./views/Tree_0_1/thinking/turn_016.md) | 292 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) | commit progress | ambient / ambient_logic / relational_program, 1 goal, goal 1159 chars | accepted commit |  |
| T0.1-17 | +08:44 | [42.6 s](./views/Tree_0_1/thinking/turn_017.md) | 1.4 s | [turn_016.json](./views/Tree_0_1/turn_016.json) | commit by rewrite pow_pow | ambient / ambient_logic, 1 goal, goal 553 chars | rejected commit: proof state unchanged |  |
| T0.1-18 | +09:07 | [20.7 s](./views/Tree_0_1/thinking/turn_018.md) | 282 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) | commit congr | ambient / ambient_logic, 1 goal, goal 553 chars | accepted commit |  |
| T0.1-19 | +09:28 | [21.4 s](./views/Tree_0_1/thinking/turn_019.md) | 4.6 s | [turn_018.json](./views/Tree_0_1/turn_018.json) | commit smt() | ambient / ambient_logic, 1 goal, goal 467 chars | rejected commit: proof state unchanged |  |
