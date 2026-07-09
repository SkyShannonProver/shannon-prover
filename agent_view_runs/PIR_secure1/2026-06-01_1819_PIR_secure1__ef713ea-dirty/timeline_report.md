# Agent-View Timeline — `PIR_secure1`

| field | value |
|---|---|
| commit | `ef713ea` **(dirty/uncommitted)** |
| branch | `ablation/l1-l4-surface` |
| run time | 2026-06-01_1819_PIR_secure1 |
| lemma | `PIR_secure1` |
| source file | `eval/examples/PIR.ec` |
| model | `claude-opus-4-6` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 52 |

Each row below: the view the agent saw → the intent it submitted → the manager result. Click a `turn_NNN.json` link to open that step's exact `ProverWorkspaceView` (copied into `./views/`).

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 10 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  inline *.
  call (_: true).
  auto.
  call (_: true).
  auto.
  call (_: ={PIR.s}).
  auto.
  call (_: ={PIR.s}).
  auto.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc.
  inline *.
  bypr (PIR.s{1}) (PIR.s{2}).
  by move=> &1 &2 a -> ->.
  move=> &1 &2 a; byequiv => //.
  proc; inline *; wp.
  while (={PIR.s, j}); last by auto => /> /#.
  wp; rnd; skip => /> /#.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-01_1819_PIR_secure1

Run dir: `artifacts/eval_suite/l1_l4_surface_ablation/l4_checked_action_surface/pir_secure1_exec/r01/2026-06-01_1819_PIR_secure1/iteration_1`

t=0: `2026-06-02T01:20:32.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:28 | [think](./views/Tree_0_0/thinking/turn_001.md) | 6.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe proc | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted probe |  |
| T0.0-2 | +00:41 | [7.6 s](./views/Tree_0_0/thinking/turn_002.md) | 409 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted commit |  |
| T0.0-3 | +00:52 | [10.5 s](./views/Tree_0_0/thinking/turn_003.md) | 473 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) | commit inline * | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected commit: manager reported rejection |  |
| T0.0-4 | +01:26 | [33 s](./views/Tree_0_0/thinking/turn_004.md) | 3 s | [turn_003.json](./views/Tree_0_0/turn_003.json) | probe sim | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | accepted probe |  |
| T0.0-5 | +02:54 | [84.7 s](./views/Tree_0_0/thinking/turn_005.md) | 293 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) | probe wp | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: manager reported rejection |  |
| T0.0-6 | +03:51 | [56.7 s](./views/Tree_0_0/thinking/turn_006.md) | 281 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) | probe sp 2 | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: expecting a goal of the form: hoare[S], phoare[S] |  |
| T0.0-7 | +04:35 | [43.8 s](./views/Tree_0_0/thinking/turn_007.md) | 241 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) | probe inline PIR.query | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: manager reported rejection |  |
| T0.0-8 | +05:17 | [41.7 s](./views/Tree_0_0/thinking/turn_008.md) | 272 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) | probe seq 2: (={PIR.s, j}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: seq onsided: a pre and a post is expected |  |
| T0.0-9 | +05:34 | [16.8 s](./views/Tree_0_0/thinking/turn_009.md) | 242 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) | probe while (={PIR.s, j}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: invalid last instruction |  |
| T0.0-10 | +06:23 | [48.8 s](./views/Tree_0_0/thinking/turn_010.md) | 215 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) | probe sim / {i} {i} | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: parse error |  |
| T0.0-11 | +07:08 | [45.7 s](./views/Tree_0_0/thinking/turn_011.md) | 347 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) | probe call true | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | accepted probe |  |
| T0.0-12 | +07:29 | [20.6 s](./views/Tree_0_0/thinking/turn_012.md) | 400 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) | commit call true | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | accepted commit |  |
| T0.0-13 | +07:44 | [14.5 s](./views/Tree_0_0/thinking/turn_013.md) | 1.5 s | [turn_012.json](./views/Tree_0_0/turn_012.json) | probe auto | pRHL / verification_residue / relational_program, 2 goals, goal 296 chars | accepted probe |  |
| T0.0-14 | +07:59 | [13.7 s](./views/Tree_0_0/thinking/turn_014.md) | 322 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) | commit auto | pRHL / verification_residue / relational_program, 2 goals, goal 296 chars | accepted commit |  |
| T0.0-15 | +08:09 | [9.6 s](./views/Tree_0_0/thinking/turn_015.md) | 354 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) | commit call true | pRHL / verification_residue / relational_program, 1 goal, goal 1136 chars | accepted commit |  |
| T0.0-16 | +08:18 | [8.7 s](./views/Tree_0_0/thinking/turn_016.md) | 318 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) | commit auto | pRHL / verification_residue / relational_program, 2 goals, goal 296 chars | accepted commit |  |
| T0.0-17 | +10:01 | 102 s |  | [turn_016.json](./views/Tree_0_0/turn_016.json) | undo_to_checkpoint | pRHL / verification_residue / relational_program, 1 goal, goal 1214 chars | checkpoint choices requested |  |
| T0.0-18 | +10:31 | [30 s](./views/Tree_0_0/thinking/turn_018.md) |  | [turn_017.json](./views/Tree_0_0/turn_017.json) | undo_to_checkpoint | pRHL / verification_residue / relational_program, 1 goal, goal 1214 chars | checkpoint rewind selected |  |
| T0.0-19 | +10:39 | [8.4 s](./views/Tree_0_0/thinking/turn_019.md) | 15.6 s | [turn_018.json](./views/Tree_0_0/turn_018.json) | undo_to_checkpoint | pRHL / verification_residue / relational_program, 1 goal, goal 1214 chars | checkpoint rewind selected |  |
| T0.0-20 | +11:17 | [22.1 s](./views/Tree_0_0/thinking/turn_020.md) | 11.9 s | [turn_019.json](./views/Tree_0_0/turn_019.json) | probe call (_: ={PIR.s}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | accepted probe |  |
| T0.0-21 | +11:41 | [12.5 s](./views/Tree_0_0/thinking/turn_021.md) | 521 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) | commit call (_: ={PIR.s}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | accepted commit |  |
| T0.0-22 | +11:51 | [9.4 s](./views/Tree_0_0/thinking/turn_022.md) | 1.6 s | [turn_021.json](./views/Tree_0_0/turn_021.json) | commit auto | pRHL / verification_residue / relational_program, 2 goals, goal 326 chars | accepted commit |  |
| T0.0-23 | +12:03 | [10.7 s](./views/Tree_0_0/thinking/turn_023.md) | 335 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) | commit call (_: ={PIR.s}) | pRHL / verification_residue / relational_program, 1 goal, goal 1166 chars | accepted commit |  |
| T0.0-24 | +12:11 | [7.5 s](./views/Tree_0_0/thinking/turn_024.md) | 473 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) | commit auto | pRHL / verification_residue / relational_program, 2 goals, goal 326 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.8 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | probe proc | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted probe |  |
| T0.1-2 | +00:35 | [32.1 s](./views/Tree_0_1/thinking/turn_002.md) | 878 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted commit |  |
| T0.1-3 | +00:54 | [18 s](./views/Tree_0_1/thinking/turn_003.md) | 2 s | [turn_002.json](./views/Tree_0_1/turn_002.json) | probe inline *; wp | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: manager reported rejection |  |
| T0.1-4 | +01:10 | [13.7 s](./views/Tree_0_1/thinking/turn_004.md) | 278 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) | probe inline * | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: manager reported rejection |  |
| T0.1-5 | +01:26 | [15.7 s](./views/Tree_0_1/thinking/turn_005.md) | 255 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) | probe wp | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: manager reported rejection |  |
| T0.1-6 | +01:49 | [23.7 s](./views/Tree_0_1/thinking/turn_006.md) | 302 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) | probe sim | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | accepted probe |  |
| T0.1-7 | +02:17 | [26.7 s](./views/Tree_0_1/thinking/turn_007.md) | 280 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) | probe while (={PIR.s, j}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: invalid last instruction |  |
| T0.1-8 | +03:55 | [97.7 s](./views/Tree_0_1/thinking/turn_008.md) | 253 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) | probe inline PIR.query | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: manager reported rejection |  |
| T0.1-9 | +04:23 | [27.8 s](./views/Tree_0_1/thinking/turn_009.md) | 223 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) | probe seq 3: (={PIR.s}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: seq onsided: a pre and a post is expected |  |
| T0.1-10 | +04:55 | [31.9 s](./views/Tree_0_1/thinking/turn_010.md) | 114 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) | inspect tactic_forms | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | read-only inspect |  |
| T0.1-11 | +06:14 | [79.5 s](./views/Tree_0_1/thinking/turn_011.md) | 548 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) | commit inline * | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected commit: manager reported rejection |  |
| T0.1-12 | +06:35 | [20.4 s](./views/Tree_0_1/thinking/turn_012.md) | 2.6 s | [turn_011.json](./views/Tree_0_1/turn_011.json) | probe sim (: true ==> ={PIR.s}) | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected probe: parse error |  |
| T0.1-13 | +07:11 | 33 s |  | [turn_012.json](./views/Tree_0_1/turn_012.json) | undo_last_step | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | undo result |  |
| T0.1-14 | +07:53 | 42 s |  | [turn_013.json](./views/Tree_0_1/turn_013.json) | undo_to_checkpoint | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | checkpoint choices requested |  |
| T0.1-15 | +08:01 | [8.6 s](./views/Tree_0_1/thinking/turn_015.md) | 1.4 s | [turn_014.json](./views/Tree_0_1/turn_014.json) | undo_to_checkpoint | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | checkpoint rewind selected |  |
| T0.1-16 | +09:05 | [61.8 s](./views/Tree_0_1/thinking/turn_016.md) | 3.2 s | [turn_015.json](./views/Tree_0_1/turn_015.json) | probe bypr (PIR.s{1}) (PIR.s{2}) | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted probe |  |
| T0.1-17 | +09:41 | [33.7 s](./views/Tree_0_1/thinking/turn_017.md) | 312 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) | probe proc; sim /i | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | rejected probe: unknown variable or constant: `i' |  |
| T0.1-18 | +10:38 | [55.7 s](./views/Tree_0_1/thinking/turn_018.md) | 1.3 s | [turn_017.json](./views/Tree_0_1/turn_017.json) | commit bypr (PIR.s{1}) (PIR.s{2}) | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted commit |  |
| T0.1-19 | +10:49 | [10.1 s](./views/Tree_0_1/thinking/turn_019.md) | 5.9 s | [turn_018.json](./views/Tree_0_1/turn_018.json) | commit by move=> &1 &2 a -> -> | ambient / ambient_logic / relational_program, 2 goals, goal 220 chars | accepted commit |  |
| T0.1-20 | +11:23 | [28.5 s](./views/Tree_0_1/thinking/turn_020.md) | 13.5 s | [turn_019.json](./views/Tree_0_1/turn_019.json) | probe move=> &1 &2 a; byequiv => // | probability / pr / probability, 1 goal, goal 233 chars | accepted probe |  |
| T0.1-21 | +12:01 | [24.6 s](./views/Tree_0_1/thinking/turn_021.md) | 385 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) | commit move=> &1 &2 a; byequiv => // | probability / pr / probability, 1 goal, goal 233 chars | accepted commit |  |
| T0.1-22 | +12:10 | [8.7 s](./views/Tree_0_1/thinking/turn_022.md) | 2.3 s | [turn_021.json](./views/Tree_0_1/turn_021.json) | probe proc; inline *; wp | equiv / prhl_module / relational_program, 1 goal, goal 279 chars | accepted probe |  |
| T0.1-23 | +12:29 | [16.7 s](./views/Tree_0_1/thinking/turn_023.md) | 334 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) | commit proc; inline *; wp | equiv / prhl_module / relational_program, 1 goal, goal 279 chars | accepted commit |  |
| T0.1-24 | +12:43 | [12.9 s](./views/Tree_0_1/thinking/turn_024.md) | 3.1 s | [turn_023.json](./views/Tree_0_1/turn_023.json) | probe while (={PIR.s, j}); last by auto => /> /# | pRHL / verification_residue / relational_program, 1 goal, goal 1112 chars | accepted probe |  |
| T0.1-25 | +13:02 | [16.5 s](./views/Tree_0_1/thinking/turn_025.md) | 514 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) | commit while (={PIR.s, j}); last by auto => /> /# | pRHL / verification_residue / relational_program, 1 goal, goal 1112 chars | accepted commit |  |
| T0.1-26 | +13:16 | [13.2 s](./views/Tree_0_1/thinking/turn_026.md) | 1.8 s | [turn_025.json](./views/Tree_0_1/turn_025.json) | probe wp; rnd; skip => /> /# | pRHL / verification_residue / relational_program, 1 goal, goal 982 chars | accepted probe |  |
| T0.1-27 | +13:23 | [4.7 s](./views/Tree_0_1/thinking/turn_027.md) | 252 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) | commit wp; rnd; skip => /> /# | pRHL / verification_residue / relational_program, 1 goal, goal 982 chars | accepted commit |  |
| T0.1-28 | +13:30 | [6.8 s](./views/Tree_0_1/thinking/turn_028.md) | 237 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
