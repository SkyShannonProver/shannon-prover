# Agent-View Timeline — `mee_decrypt_correct`

| field | value |
|---|---|
| commit | `80bd763` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_0130_mee_decrypt_correct |
| lemma | `mee_decrypt_correct` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-opus-4-6` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | incomplete (timeout/open) |
| turns | 48 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  sp.
  seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ ek = _ek /\ mk = _mk /\ p = None).
  while (true).
  (* proof not completed in this run *)
```

### `Tree_0_1` — incomplete — 9 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  sp.
  seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ mk = _mk /\ p = None).
  while (true).
  wp; call (_: true); auto.
  auto.
  while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witness _c) (take i c) /\ s = last (head witness _c) (take i c) /\ p = None /\ ek = _ek /\ mk = _mk /\ c = behead _c) (size c - i).
  move=> z.
  wp.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_0130_mee_decrypt_correct

Run dir: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1`

t=0: `2026-06-06T08:30:49+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:05 | [think](./views/Tree_0_0/thinking/turn_001.md) | 3.4 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 300 chars | accepted probe |  |
| T0.0-2 | +00:33 | [24.7 s](./views/Tree_0_0/thinking/turn_002.md) | 265 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 300 chars | accepted commit |  |
| T0.0-3 | +00:38 | [5.1 s](./views/Tree_0_0/thinking/turn_003.md) | 1.9 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | probe inline * | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.0-4 | +01:07 | [26.7 s](./views/Tree_0_0/thinking/turn_004.md) | 288 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | probe inline PRPc.PseudoRP.fi | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.0-5 | +01:21 | [14 s](./views/Tree_0_0/thinking/turn_005.md) |  | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | inspect call_site_options | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | read-only inspect |  |
| T0.0-6 | +01:40 | [18.7 s](./views/Tree_0_0/thinking/turn_006.md) | 334 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe hoare | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | accepted probe |  |
| T0.0-7 | +02:09 | [29.1 s](./views/Tree_0_0/thinking/turn_007.md) | 1.9 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | lookup PRPc.PseudoRP.fi | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | lookup result |  |
| T0.0-8 | +02:39 | [27.7 s](./views/Tree_0_0/thinking/turn_008.md) | 327 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | probe inline PseudoRP.fi | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: unknown procedure: PseudoRP.fi |  |
| T0.0-9 | +03:04 | [24.8 s](./views/Tree_0_0/thinking/turn_009.md) | 184 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | inspect tactic_forms | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | read-only inspect |  |
| T0.0-10 | +03:52 | [47.8 s](./views/Tree_0_0/thinking/turn_010.md) | 173 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | inspect tactic_forms | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | read-only inspect |  |
| T0.0-11 | +04:45 | [52.6 s](./views/Tree_0_0/thinking/turn_011.md) | 375 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | probe sp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | accepted probe |  |
| T0.0-12 | +06:25 | [99.6 s](./views/Tree_0_0/thinking/turn_012.md) | 365 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | probe inline MEEt.PRPc.PseudoRP.fi | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.0-13 | +06:48 | [22.6 s](./views/Tree_0_0/thinking/turn_013.md) | 376 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | probe inline MAC.verify | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.0-14 | +08:16 | [87.7 s](./views/Tree_0_0/thinking/turn_014.md) | 343 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit sp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | accepted commit |  |
| T0.0-15 | +08:24 | [8.1 s](./views/Tree_0_0/thinking/turn_015.md) | 1.9 s | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | probe inline * | phoare / procedure_body / procedure_frontier, 1 goal, goal 1203 chars | rejected probe: manager reported rejection |  |
| T0.0-16 | +08:35 | [8.7 s](./views/Tree_0_0/thinking/turn_016.md) | 265 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | probe wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1203 chars | rejected probe: manager reported rejection |  |
| T0.0-17 | +10:19 | [103.7 s](./views/Tree_0_0/thinking/turn_017.md) | 315 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | probe seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ e... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1203 chars | accepted probe |  |
| T0.0-18 | +11:02 | [42.7 s](./views/Tree_0_0/thinking/turn_018.md) | 302 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | probe while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ p = None /\ c = be... | phoare / procedure_body / seq_cut, 1 goal, goal 1203 chars | rejected probe: invalid last instruction |  |
| T0.0-19 | +13:17 | [134.7 s](./views/Tree_0_0/thinking/turn_019.md) | 330 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ e... | phoare / procedure_body / seq_cut, 1 goal, goal 1203 chars | accepted commit |  |
| T0.0-20 | +13:34 | [16.9 s](./views/Tree_0_0/thinking/turn_020.md) | 2.1 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | probe while (true) (size c - i) | hoare / procedure_body / procedure_frontier, 5 goals, goal 872 chars | rejected probe: invalid arguments |  |
| T0.0-21 | +14:08 | [31.7 s](./views/Tree_0_0/thinking/turn_021.md) | 336 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | probe while (true) | hoare / procedure_body / procedure_frontier, 5 goals, goal 872 chars | accepted probe |  |
| T0.0-22 | +14:23 | [14.5 s](./views/Tree_0_0/thinking/turn_022.md) | 497 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit while (true) | hoare / procedure_body / procedure_frontier, 5 goals, goal 872 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 4 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | probe proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 300 chars | accepted probe |  |
| T0.1-2 | +00:30 | [25.7 s](./views/Tree_0_1/thinking/turn_002.md) | 318 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 300 chars | accepted commit |  |
| T0.1-3 | +00:58 | [28.5 s](./views/Tree_0_1/thinking/turn_003.md) | 2.5 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | probe inline * | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.1-4 | +01:23 | [21.9 s](./views/Tree_0_1/thinking/turn_004.md) | 109 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | inspect tactic_forms | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | read-only inspect |  |
| T0.1-5 | +01:42 | [18.7 s](./views/Tree_0_1/thinking/turn_005.md) | 270 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | probe inline PRPc.PseudoRP.fi | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.1-6 | +02:02 | [20 s](./views/Tree_0_1/thinking/turn_006.md) |  | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | inspect call_site_options | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | read-only inspect |  |
| T0.1-7 | +02:12 | [9.7 s](./views/Tree_0_1/thinking/turn_007.md) | 341 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | probe sp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | accepted probe |  |
| T0.1-8 | +04:12 | [120.5 s](./views/Tree_0_1/thinking/turn_008.md) | 527 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | probe wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | rejected probe: manager reported rejection |  |
| T0.1-9 | +04:28 | [14.6 s](./views/Tree_0_1/thinking/turn_009.md) | 389 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit sp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1311 chars | accepted commit |  |
| T0.1-10 | +08:02 | [214 s](./views/Tree_0_1/thinking/turn_010.md) | 2 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | probe while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witnes... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1203 chars | rejected probe: invalid last instruction |  |
| T0.1-11 | +08:43 | [38.7 s](./views/Tree_0_1/thinking/turn_011.md) | 313 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | probe seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ m... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1203 chars | accepted probe |  |
| T0.1-12 | +09:20 | [36.6 s](./views/Tree_0_1/thinking/turn_012.md) | 424 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ m... | phoare / procedure_body / seq_cut, 1 goal, goal 1203 chars | accepted commit |  |
| T0.1-13 | +09:38 | [17.9 s](./views/Tree_0_1/thinking/turn_013.md) | 2.1 s | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | probe while (true) | hoare / procedure_body / procedure_frontier, 5 goals, goal 872 chars | accepted probe |  |
| T0.1-14 | +09:53 | [12.7 s](./views/Tree_0_1/thinking/turn_014.md) | 316 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit while (true) | hoare / procedure_body / procedure_frontier, 5 goals, goal 872 chars | accepted commit |  |
| T0.1-15 | +10:10 | [16.8 s](./views/Tree_0_1/thinking/turn_015.md) | 2.2 s | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | probe wp; call (_: true); auto | hoare / procedure_body / procedure_frontier, 6 goals, goal 594 chars | accepted probe |  |
| T0.1-16 | +10:31 | [18.7 s](./views/Tree_0_1/thinking/turn_016.md) | 308 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit wp; call (_: true); auto | hoare / procedure_body / procedure_frontier, 6 goals, goal 594 chars | accepted commit |  |
| T0.1-17 | +10:45 | [13.7 s](./views/Tree_0_1/thinking/turn_017.md) | 292 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit auto | hoare / procedure_body / procedure_frontier, 5 goals, goal 592 chars | accepted commit |  |
| T0.1-18 | +11:00 | [14.9 s](./views/Tree_0_1/thinking/turn_018.md) | 2.1 s | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | probe while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witnes... | phoare / procedure_body / procedure_frontier, 4 goals, goal 969 chars | accepted probe |  |
| T0.1-19 | +11:55 | [52.6 s](./views/Tree_0_1/thinking/turn_019.md) | 442 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witnes... | phoare / procedure_body / procedure_frontier, 4 goals, goal 969 chars | accepted commit |  |
| T0.1-20 | +12:17 | [21.8 s](./views/Tree_0_1/thinking/turn_020.md) | 2.2 s | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | probe move=> z | phoare / procedure_body / procedure_frontier, 5 goals, goal 810 chars | accepted probe |  |
| T0.1-21 | +12:29 | [9.7 s](./views/Tree_0_1/thinking/turn_021.md) | 348 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit move=> z | phoare / procedure_body / procedure_frontier, 5 goals, goal 810 chars | accepted commit |  |
| T0.1-22 | +12:35 | [6 s](./views/Tree_0_1/thinking/turn_022.md) | 2 s | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | probe inline PRPc.PseudoRP.fi | phoare / procedure_body / procedure_frontier, 5 goals, goal 1044 chars | rejected probe: manager reported rejection |  |
| T0.1-23 | +13:05 | [27.7 s](./views/Tree_0_1/thinking/turn_023.md) | 341 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | probe inline * | phoare / procedure_body / procedure_frontier, 5 goals, goal 1044 chars | rejected probe: manager reported rejection |  |
| T0.1-24 | +13:20 | [14.9 s](./views/Tree_0_1/thinking/turn_024.md) | 134 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | inspect tactic_forms | phoare / procedure_body / procedure_frontier, 5 goals, goal 1044 chars | read-only inspect |  |
| T0.1-25 | +13:49 | [28.6 s](./views/Tree_0_1/thinking/turn_025.md) | 354 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | probe wp | phoare / procedure_body / procedure_frontier, 5 goals, goal 1044 chars | accepted probe |  |
| T0.1-26 | +14:30 | [40.6 s](./views/Tree_0_1/thinking/turn_026.md) | 381 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit wp | phoare / procedure_body / procedure_frontier, 5 goals, goal 1044 chars | accepted commit |  |
