# Agent-View Timeline — `CCP_OCCP`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-08_2002_CCP_OCCP |
| lemma | `CCP_OCCP` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 39 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 5 tactic(s) committed, not closed

```easycrypt
proof.
  proc*.
  call (_: ={glob OCC, glob I}).
  sim.
  sim.
  proc.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc*.
  call (_: ={glob OCC, glob I}).
  sim.
  sim.
  proc.
  sp.
  seq 1 0 : (c{1} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{1}) k{1} n{1} 1 p{1} /\ (n{2}, a{2}, p{2}) = nap{2} /\ c{2} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{2}) k{2} n{2} 1 p{2} /\ t{2} = genpoly1305 (cc OCC.gs{2}) k{2} n{2} (topol a{2} c{2}) /\ (n{1}, a{1}, p{1}) = nap{1} /\ k{1} = k{2} /\ nap{1} = nap{2} /\ OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}).
  exists* OCC.gs{1}, k{1}, n{1}, p{1}; elim* => gs0 k0 n0 p0; call{1} (chacha_spec k0 n0 p0 gs0).
  auto.
  exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0 a0 c0 gs0).
  auto.
  proc.
  sp 2 2.
  seq 1 1 : (t'{1} = t'{2} /\ result{1} = result{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ c{1} = c{2} /\ t{1} = t{2} /\ k{1} = k{2} /\ OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}).
  exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0 a0 c0 gs0).
  auto.
  if.
  smt().
  wp; exists* OCC.gs{1}, k{1}, n{1}, c{1}; elim* => gs0 k0 n0 c0; call{1} (chacha_spec k0 n0 c0 gs0).
  auto.
  auto.
  auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_2002_CCP_OCCP

Run dir: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1`

t=0: `2026-06-09T03:02:48+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) |  | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect call_site_options | equiv / prhl_module / relational_program, 1 goal, goal 393 chars | read-only inspect |  |
| T0.0-2 | +00:06 | [5.5 s](./views/Tree_0_0/thinking/turn_002.md) | 1.5 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc* | equiv / prhl_module / relational_program, 1 goal, goal 393 chars | accepted commit |  |
| T0.0-3 | +00:16 | [8.6 s](./views/Tree_0_0/thinking/turn_003.md) | 1.4 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 1 goal, goal 456 chars | read-only inspect |  |
| T0.0-4 | +00:27 | [9.7 s](./views/Tree_0_0/thinking/turn_004.md) | 333 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit call (_: ={glob OCC, glob I}) | pRHL / call_site / failure_diagnostic, 1 goal, goal 456 chars | accepted commit |  |
| T0.0-5 | +00:39 | [11.6 s](./views/Tree_0_0/thinking/turn_005.md) | 436 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit sim | equiv / prhl_module / relational_program, 5 goals, goal 336 chars | accepted commit |  |
| T0.0-6 | +00:44 | [4.8 s](./views/Tree_0_0/thinking/turn_006.md) | 229 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit sim | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted commit |  |
| T0.0-7 | +02:08 | [83.7 s](./views/Tree_0_0/thinking/turn_007.md) | 291 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 366 chars | accepted commit |  |
| T0.0-8 | +02:55 | 47 s |  | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | unknown | pRHL / call_site / relational_program, 3 goals, goal 1219 chars | repair / unhealthy |  |
| T0.0-9 | +02:59 | 4 s |  | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | unknown | pRHL / call_site / relational_program, 3 goals, goal 1219 chars | repair / unhealthy |  |
| T0.0-10 | +03:03 | 4 s |  | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | unknown | pRHL / call_site / relational_program, 3 goals, goal 1219 chars | repair / unhealthy |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:03 | [think](./views/Tree_0_1/thinking/turn_001.md) | 145 ms | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect lemma_index | equiv / prhl_module / relational_program, 1 goal, goal 393 chars | read-only inspect |  |
| T0.1-2 | +00:45 | [42.2 s](./views/Tree_0_1/thinking/turn_002.md) | 1.8 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit proc* | equiv / prhl_module / relational_program, 1 goal, goal 393 chars | accepted commit |  |
| T0.1-3 | +00:51 | [3.8 s](./views/Tree_0_1/thinking/turn_003.md) | 1.2 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 1 goal, goal 456 chars | read-only inspect |  |
| T0.1-4 | +01:02 | [9.8 s](./views/Tree_0_1/thinking/turn_004.md) | 244 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit call (_: ={glob OCC, glob I}) | pRHL / call_site / failure_diagnostic, 1 goal, goal 456 chars | accepted commit |  |
| T0.1-5 | +01:13 | [10.6 s](./views/Tree_0_1/thinking/turn_005.md) | 351 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit sim | equiv / prhl_module / relational_program, 5 goals, goal 336 chars | accepted commit |  |
| T0.1-6 | +01:25 | [11.8 s](./views/Tree_0_1/thinking/turn_006.md) | 239 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit sim | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted commit |  |
| T0.1-7 | +02:48 | [82.7 s](./views/Tree_0_1/thinking/turn_007.md) | 309 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 366 chars | accepted commit |  |
| T0.1-8 | +02:52 | [3.7 s](./views/Tree_0_1/thinking/turn_008.md) | 272 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit sp | pRHL / call_site / relational_program, 3 goals, goal 1219 chars | accepted commit |  |
| T0.1-9 | +03:27 | [34.7 s](./views/Tree_0_1/thinking/turn_009.md) | 278 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0... | pRHL / call_site / relational_program, 3 goals, goal 1048 chars | accepted commit |  |
| T0.1-10 | +03:41 | [13.7 s](./views/Tree_0_1/thinking/turn_010.md) | 272 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit exists* OCC.gs{1}, k{1}, n{1}, p{1}; elim* => gs1 k1 n1 p1; call{1} (chacha_spec k1 n1 p1 gs1) | pRHL / call_site / relational_program, 3 goals, goal 1379 chars | accepted commit |  |
| T0.1-11 | +04:32 | 50.7 s | 1.3 s | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | undo_last_step | pRHL / prhl_module / relational_program, 3 goals, goal 1659 chars | undo result |  |
| T0.1-12 | +04:51 | 17.9 s | 1.1 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | undo_last_step | pRHL / call_site / relational_program, 3 goals, goal 1366 chars | undo result |  |
| T0.1-13 | +05:28 | [35.8 s](./views/Tree_0_1/thinking/turn_013.md) | 1.2 s | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit seq 1 0 : (c{1} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{1}) k{1}... | pRHL / call_site / relational_program, 3 goals, goal 1035 chars | accepted commit |  |
| T0.1-14 | +05:52 | [22.7 s](./views/Tree_0_1/thinking/turn_014.md) | 273 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit exists* OCC.gs{1}, k{1}, n{1}, p{1}; elim* => gs0 k0 n0 p0; call{1} (chacha_spec k0 n0 p0 gs0) | pRHL / call_site / relational_program, 4 goals, goal 1243 chars | accepted commit |  |
| T0.1-15 | +06:01 | [8.7 s](./views/Tree_0_1/thinking/turn_015.md) | 282 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit auto | pRHL / prhl_module / relational_program, 4 goals, goal 1510 chars | accepted commit |  |
| T0.1-16 | +06:16 | [14.7 s](./views/Tree_0_1/thinking/turn_016.md) | 269 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0... | pRHL / call_site / relational_program, 3 goals, goal 1004 chars | accepted commit |  |
| T0.1-17 | +06:44 | [27.8 s](./views/Tree_0_1/thinking/turn_017.md) | 219 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit auto | pRHL / prhl_module / relational_program, 3 goals, goal 1336 chars | accepted commit |  |
| T0.1-18 | +07:12 | [27.7 s](./views/Tree_0_1/thinking/turn_018.md) | 305 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 368 chars | accepted commit |  |
| T0.1-19 | +07:43 | [30.7 s](./views/Tree_0_1/thinking/turn_019.md) | 308 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit sp 2 2 | pRHL / call_site / relational_program, 2 goals, goal 1785 chars | accepted commit |  |
| T0.1-20 | +08:07 | [23.7 s](./views/Tree_0_1/thinking/turn_020.md) | 291 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit seq 1 1 : (t'{1} = t'{2} /\ result{1} = result{2} /\ n{1} = n{2} /\ a... | pRHL / call_site / relational_program, 2 goals, goal 1743 chars | accepted commit |  |
| T0.1-21 | +08:19 | [11.7 s](./views/Tree_0_1/thinking/turn_021.md) | 311 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0... | pRHL / call_site / relational_program, 3 goals, goal 1358 chars | accepted commit |  |
| T0.1-22 | +08:24 | [4.7 s](./views/Tree_0_1/thinking/turn_022.md) | 282 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit auto | pRHL / procedure_body / relational_program, 3 goals, goal 1743 chars | accepted commit |  |
| T0.1-23 | +08:45 | [20.7 s](./views/Tree_0_1/thinking/turn_023.md) | 261 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit if | pRHL / call_site / relational_program, 2 goals, goal 1353 chars | accepted commit |  |
| T0.1-24 | +08:54 | [8.7 s](./views/Tree_0_1/thinking/turn_024.md) | 310 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit smt() | ambient / ambient_logic / relational_program, 4 goals, goal 369 chars | accepted commit |  |
| T0.1-25 | +09:07 | [12.7 s](./views/Tree_0_1/thinking/turn_025.md) | 302 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit wp; exists* OCC.gs{1}, k{1}, n{1}, c{1}; elim* => gs0 k0 n0 c0; call{1} (chacha_spec k0 n0 c0... | pRHL / call_site / relational_program, 3 goals, goal 1199 chars | accepted commit |  |
| T0.1-26 | +09:36 | [28.7 s](./views/Tree_0_1/thinking/turn_026.md) | 292 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit auto | pRHL / prhl_module / relational_program, 3 goals, goal 1341 chars | accepted commit |  |
| T0.1-27 | +09:43 | [6.7 s](./views/Tree_0_1/thinking/turn_027.md) | 261 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit auto | pRHL / prhl_module / relational_program, 2 goals, goal 912 chars | accepted commit |  |
| T0.1-28 | +09:52 | [8.8 s](./views/Tree_0_1/thinking/turn_028.md) | 202 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit auto | pRHL / verification_residue / relational_program, 1 goal, goal 678 chars | accepted commit |  |
| T0.1-29 | +09:56 | [3.8 s](./views/Tree_0_1/thinking/turn_029.md) | 200 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
