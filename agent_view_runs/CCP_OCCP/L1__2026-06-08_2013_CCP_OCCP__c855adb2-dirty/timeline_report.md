# Agent-View Timeline — `CCP_OCCP`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-08_2013_CCP_OCCP |
| lemma | `CCP_OCCP` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 35 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 8 tactic(s) committed, not closed

```easycrypt
proof.
  proc (={glob I, glob OCC}).
  by move=> /> />.
  by move=> /> />.
  by sim.
  by sim.
  proc.
  seq 1 1 : (={n, a, p, k, glob I, glob OCC}).
  auto.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc (={glob I, glob OCC}).
  by move=> />.
  by move=> />.
  sim.
  sim.
  proc.
  sp 1 1.
  seq 1 1 : (={glob I, glob OCC, k, n, a} /\ c{1} = c{2}).
  wp.
  exists* (glob OCC){1}, k{1}, n{1}, p{1}; elim* => gs kk nn pp; call {1} (chacha_spec kk nn pp gs).
  skip; smt().
  wp; exists* (glob OCC){1}, k{1}, n{1}, a{1}, c{1}; elim* => gs kk nn aa cc0; call {1} (poly_spec kk nn aa cc0 gs).
  skip; smt().
  proc; sp 2 2.
  seq 1 1 : (={glob I, glob OCC, k, n, a, c, t, t', result}).
  wp; exists* (glob OCC){1}, k{1}, n{1}, a{1}, c{1}; elim* => gs kk nn aa cc0; call {1} (poly_spec kk nn aa cc0 gs); skip; smt().
  if.
  smt().
  wp; exists* (glob OCC){1}, k{1}, n{1}, c{1}; elim* => gs kk nn cc0; call {1} (chacha_spec kk nn cc0 gs); skip; smt().
  auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_2013_CCP_OCCP

Run dir: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1`

t=0: `2026-06-09T03:15:34.500000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:48 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc (={glob I, glob OCC}) | equiv / prhl_module / relational_program, 1 goal, goal 393 chars | accepted commit |  |
| T0.0-2 | +00:59 | [9.7 s](./views/Tree_0_0/thinking/turn_002.md) | 306 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit by move=> /> /> | ambient / ambient_logic / relational_program, 6 goals, goal 352 chars | accepted commit |  |
| T0.0-3 | +01:11 | [11.8 s](./views/Tree_0_0/thinking/turn_003.md) | 242 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit by move=> /> /> | ambient / ambient_logic / relational_program, 5 goals, goal 365 chars | accepted commit |  |
| T0.0-4 | +01:21 | [9.8 s](./views/Tree_0_0/thinking/turn_004.md) | 217 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit by sim | equiv / prhl_module / relational_program, 4 goals, goal 336 chars | accepted commit |  |
| T0.0-5 | +01:26 | [4.8 s](./views/Tree_0_0/thinking/turn_005.md) | 238 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit by sim | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | accepted commit |  |
| T0.0-6 | +02:21 | [54.7 s](./views/Tree_0_0/thinking/turn_006.md) | 328 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 366 chars | accepted commit |  |
| T0.0-7 | +03:00 | [38.7 s](./views/Tree_0_0/thinking/turn_007.md) | 307 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit seq 1 1 : (={n, a, p, k, glob I, glob OCC}) | pRHL / call_site / relational_program, 2 goals, goal 1219 chars | accepted commit |  |
| T0.0-8 | +03:05 | [4.7 s](./views/Tree_0_0/thinking/turn_008.md) | 274 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit auto | pRHL / procedure_body / relational_program, 3 goals, goal 775 chars | accepted commit |  |
| T0.0-9 | +03:40 | 35 s |  | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 1123 chars | repair / unhealthy |  |
| T0.0-10 | +03:48 | 7 s |  | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 1123 chars | repair / unhealthy |  |
| T0.0-11 | +03:52 | 4 s |  | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 1123 chars | repair / unhealthy |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc (={glob I, glob OCC}) | equiv / prhl_module / relational_program, 1 goal, goal 393 chars | accepted commit |  |
| T0.1-2 | +00:17 | [15.7 s](./views/Tree_0_1/thinking/turn_002.md) | 256 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit by move=> /> | ambient / ambient_logic / relational_program, 6 goals, goal 352 chars | accepted commit |  |
| T0.1-3 | +00:21 | [3.8 s](./views/Tree_0_1/thinking/turn_003.md) | 185 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit by move=> /> | ambient / ambient_logic / relational_program, 5 goals, goal 365 chars | accepted commit |  |
| T0.1-4 | +00:32 | [10.8 s](./views/Tree_0_1/thinking/turn_004.md) | 183 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit sim | equiv / prhl_module / relational_program, 4 goals, goal 336 chars | accepted commit |  |
| T0.1-5 | +00:45 | [12.8 s](./views/Tree_0_1/thinking/turn_005.md) | 207 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit sim | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | accepted commit |  |
| T0.1-6 | +02:28 | [102.7 s](./views/Tree_0_1/thinking/turn_006.md) | 308 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 366 chars | accepted commit |  |
| T0.1-7 | +03:03 | [34.7 s](./views/Tree_0_1/thinking/turn_007.md) | 288 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit sp 1 1 | pRHL / call_site / relational_program, 2 goals, goal 1219 chars | accepted commit |  |
| T0.1-8 | +03:10 | 7 s |  | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 1212 chars | repair / unhealthy |  |
| T0.1-9 | +03:14 | 4 s |  | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 1212 chars | repair / unhealthy |  |
| T0.1-10 | +03:17 | 2.7 s | 285 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit seq 1 1 : (={glob I, glob OCC, k, n, a} /\ c{1} = c{2}) | pRHL / call_site / relational_program, 2 goals, goal 1212 chars | accepted commit |  |
| T0.1-11 | +03:47 | [29.7 s](./views/Tree_0_1/thinking/turn_011.md) | 280 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit wp | pRHL / call_site / relational_program, 3 goals, goal 1000 chars | accepted commit |  |
| T0.1-12 | +04:06 | [18.7 s](./views/Tree_0_1/thinking/turn_012.md) | 307 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit exists* (glob OCC){1}, k{1}, n{1}, p{1}; elim* => gs kk nn pp; call {1} (chacha_spec kk nn pp... | pRHL / call_site / relational_program, 3 goals, goal 907 chars | accepted commit |  |
| T0.1-13 | +04:21 | [14.6 s](./views/Tree_0_1/thinking/turn_013.md) | 366 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit skip; smt() | pRHL / prhl_module / relational_program, 3 goals, goal 1159 chars | accepted commit |  |
| T0.1-14 | +04:33 | [11.7 s](./views/Tree_0_1/thinking/turn_014.md) | 282 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit wp; exists* (glob OCC){1}, k{1}, n{1}, a{1}, c{1}; elim* => gs kk nn aa cc0; call {1} (poly_s... | pRHL / call_site / relational_program, 2 goals, goal 896 chars | accepted commit |  |
| T0.1-15 | +04:40 | [6.8 s](./views/Tree_0_1/thinking/turn_015.md) | 232 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit skip; smt() | pRHL / prhl_module / relational_program, 2 goals, goal 1138 chars | accepted commit |  |
| T0.1-16 | +05:09 | [28.7 s](./views/Tree_0_1/thinking/turn_016.md) | 327 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit proc; sp 2 2 | equiv / prhl_module / relational_program, 1 goal, goal 353 chars | accepted commit |  |
| T0.1-17 | +05:14 | [4.7 s](./views/Tree_0_1/thinking/turn_017.md) | 284 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit seq 1 1 : (={glob I, glob OCC, k, n, a, c, t, t', result}) | pRHL / call_site / relational_program, 1 goal, goal 1728 chars | accepted commit |  |
| T0.1-18 | +05:21 | [6.6 s](./views/Tree_0_1/thinking/turn_018.md) | 372 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit wp; exists* (glob OCC){1}, k{1}, n{1}, a{1}, c{1}; elim* => gs kk nn aa cc0; call {1} (poly_s... | pRHL / call_site / relational_program, 2 goals, goal 1356 chars | accepted commit |  |
| T0.1-19 | +05:29 | [7.7 s](./views/Tree_0_1/thinking/turn_019.md) | 274 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit if | pRHL / call_site / relational_program, 1 goal, goal 1336 chars | accepted commit |  |
| T0.1-20 | +05:38 | [8.7 s](./views/Tree_0_1/thinking/turn_020.md) | 297 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit smt() | ambient / ambient_logic / relational_program, 3 goals, goal 367 chars | accepted commit |  |
| T0.1-21 | +05:51 | [12.6 s](./views/Tree_0_1/thinking/turn_021.md) | 402 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit wp; exists* (glob OCC){1}, k{1}, n{1}, c{1}; elim* => gs kk nn cc0; call {1} (chacha_spec kk... | pRHL / call_site / relational_program, 2 goals, goal 1196 chars | accepted commit |  |
| T0.1-22 | +06:00 | [8.8 s](./views/Tree_0_1/thinking/turn_022.md) | 221 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit auto | pRHL / prhl_module / relational_program, 1 goal, goal 894 chars | accepted commit |  |
| T0.1-23 | +06:03 | [2.8 s](./views/Tree_0_1/thinking/turn_023.md) | 212 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-24 | +06:12 | 8 s |  | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
