# Agent-View Timeline — `PIR_correct`

| field | value |
|---|---|
| commit | `64a85215c` **(dirty/uncommitted)** |
| branch | `feat/open-source-prep` |
| run time | 2026-07-08_2049_PIR_correct |
| lemma | `PIR_correct` |
| source file | `eval/examples/PIR.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 60 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 15 tactic(s) committed, not closed

```easycrypt
proof.
  move => hi.
  byphoare (_ : i = i0 /\ 0 <= i0 < N ==> res = a i0) => //.
  proc.
  inline PIR.query.
  wp.
  while (i = i0 /\ 0 <= i0 < N /\ 0 <= j <= N /\ (j <= i0 => PIR.s = PIR.s') /\ (i0 < j => sxor2 PIR.s PIR.s' i0)) (N - j).
  move => z; wp.
  rnd predT.
  skip.
  move => &hr [[[Hinv Hlt] Hz] _]; split.
  exact dbool_ll.
  move => _ v _.
  case: Hinv => [Hi [Hr [Hjb [Hss Hsx]]]]; rewrite Hi /predT /=.
  case: (j{hr} = i0) => Hji.
  rewrite Hji; case: v => Hv.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  move => hi.
  byphoare (_: i = i0 ==> res = a i0) => //.
  proc.
  inline PIR.query.
  wp.
  while (0 <= j <= N /\ i = i0 /\ (j <= i0 => PIR.s = PIR.s') /\ (i0 < j => sxor2 PIR.s PIR.s' i0)) (N - j).
  move => z; wp.
  rnd predT.
  skip.
  move => &hr [[[[Hjb [Hii [Hs Hsx]]] Hjlt] Hz] _].
  split.
  exact dbool_ll.
  move => _ v hv; rewrite /predT /= Hii /=.
  smt(sxor_cons sxor2_cons).
  wp.
  skip => &hr Hi0; split; first by smt().
  move => s1 s' j0; split; first by smt().
  move => hnlt [hb [hi2 [hle hsxi]]]; have h: sxor2 s1 s' i0 by apply hsxi; smt().
  move: h; rewrite /sxor2 /sxor => -[[u1 u2 [-> ->]]|[u1 u2 [-> ->]]].
  rewrite !big_cat big_consT.
  move: (big predT<:int> a u1) (big predT<:int> a u2) => A B.
  rewrite (xorwC (a i0) B) !xorwA.
  have hz : A +^ B +^ A +^ B = zerow by rewrite -xorwA xorwK.
  by rewrite hz xorwC xorw0.
  rewrite xorwC !big_cat big_consT; move: (big predT<:int> a u1) (big predT<:int> a u2) => A B; rewrite (xorwC (a i0) B) !xorwA.
  have hz : A +^ B +^ A +^ B = zerow by rewrite -xorwA xorwK. by rewrite hz xorwC xorw0.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-07-08_2049_PIR_correct

Run dir: `artifacts/eval_suite/demo_pir/l4_checked_action_surface/pir_correct/r01/2026-07-08_2049_PIR_correct/iteration_1`

t=0: `2026-07-09T03:50:40.080000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:55 | [think](./views/Tree_0_0/thinking/turn_001.md) | 758 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move => hi | probability / pr / probability, 1 goal, goal 181 chars | accepted commit |  |
| T0.0-2 | +01:04 | 8 s |  | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | unknown | probability / pr / probability, 1 goal, goal 194 chars | repair / unhealthy |  |
| T0.0-3 | +01:10 | [5.9 s](./views/Tree_0_0/thinking/turn_003.md) | 137 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit byphoare (_ : i = i0 /\ 0 <= i0 < N ==> res = a i0) => // | probability / pr / probability, 1 goal, goal 194 chars | accepted commit |  |
| T0.0-4 | +01:17 | [6.9 s](./views/Tree_0_0/thinking/turn_004.md) | 148 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 229 chars | accepted commit |  |
| T0.0-5 | +01:22 | [4.9 s](./views/Tree_0_0/thinking/turn_005.md) | 132 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline PIR.query | phoare / procedure_body / procedure_frontier, 1 goal, goal 1055 chars | accepted commit |  |
| T0.0-6 | +01:30 | [7.9 s](./views/Tree_0_0/thinking/turn_006.md) | 138 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1151 chars | accepted commit |  |
| T0.0-7 | +01:41 | [10.9 s](./views/Tree_0_0/thinking/turn_007.md) | 94 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | tactic_forms | phoare / procedure_body / procedure_frontier, 1 goal, goal 1039 chars | manager result |  |
| T0.0-8 | +02:07 | [25.8 s](./views/Tree_0_0/thinking/turn_008.md) | 176 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit while (i = i0 /\ 0 <= i0 < N /\ 0 <= j <= N /\ (j <= i0 => PIR.s = PI... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1039 chars | accepted commit |  |
| T0.0-9 | +02:37 | [29.8 s](./views/Tree_0_0/thinking/turn_009.md) | 198 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit move => z; wp | phoare / procedure_body / procedure_frontier, 2 goals, goal 621 chars | accepted commit |  |
| T0.0-10 | +03:09 | [31.9 s](./views/Tree_0_0/thinking/turn_010.md) | 79 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | tactic_forms | phoare / procedure_body / procedure_frontier, 2 goals, goal 1335 chars | manager result |  |
| T0.0-11 | +03:50 | [40.9 s](./views/Tree_0_0/thinking/turn_011.md) | 142 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit rnd predT | phoare / procedure_body / procedure_frontier, 2 goals, goal 1335 chars | accepted commit |  |
| T0.0-12 | +04:12 | [21.9 s](./views/Tree_0_0/thinking/turn_012.md) | 122 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit skip | phoare / procedure_body / procedure_frontier, 2 goals, goal 1467 chars | accepted commit |  |
| T0.0-13 | +04:46 | [33.9 s](./views/Tree_0_0/thinking/turn_013.md) | 143 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit move => &hr [[[Hinv Hlt] Hz] _]; split | ambient / ambient_logic, 2 goals, goal 1537 chars | accepted commit |  |
| T0.0-14 | +05:02 | 15.9 s | 136 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit exact dbool_ll | ambient / ambient_logic, 3 goals, goal 454 chars | accepted commit |  |
| T0.0-15 | +05:26 | [24.2 s](./views/Tree_0_0/thinking/turn_015.md) | 765 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit move => _ v _; case: Hinv => Hi Hr Hjb Hss Hsx; rewrite Hi /predT /= | ambient / ambient_logic, 2 goals, goal 1494 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-16 | +05:52 | [24.8 s](./views/Tree_0_0/thinking/turn_016.md) | 205 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit move => _ v _ | ambient / ambient_logic, 2 goals, goal 1494 chars | accepted commit |  |
| T0.0-17 | +06:14 | [22.2 s](./views/Tree_0_0/thinking/turn_017.md) | 822 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit case: Hinv => Hi Hr Hjb Hss Hsx; rewrite Hi /predT /= | ambient / ambient_logic, 2 goals, goal 1374 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-18 | +06:46 | [31.1 s](./views/Tree_0_0/thinking/turn_018.md) | 898 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit move: Hinv => [Hi Hr Hjb Hss Hsx]; rewrite Hi /predT /= | ambient / ambient_logic, 2 goals, goal 1374 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-19 | +07:03 | [16.1 s](./views/Tree_0_0/thinking/turn_019.md) | 859 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit move: Hinv => [Hi Hr Hjb Hss Hsx] | ambient / ambient_logic, 2 goals, goal 1374 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-20 | +08:02 | [57.8 s](./views/Tree_0_0/thinking/turn_020.md) | 198 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit case: Hinv => [Hi [Hr [Hjb [Hss Hsx]]]]; rewrite Hi /predT /= | ambient / ambient_logic, 2 goals, goal 1374 chars | accepted commit |  |
| T0.0-21 | +08:53 | [50.8 s](./views/Tree_0_0/thinking/turn_021.md) | 166 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit case: (j{hr} = i0) => Hji | ambient / ambient_logic, 2 goals, goal 1276 chars | accepted commit |  |
| T0.0-22 | +09:23 | [29.9 s](./views/Tree_0_0/thinking/turn_022.md) | 142 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit rewrite Hji; case: v => Hv | ambient / ambient_logic, 3 goals, goal 837 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 920 ms | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit move => hi | probability / pr / probability, 1 goal, goal 181 chars | accepted commit |  |
| T0.1-2 | +00:03 | 1.9 s | 145 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit byphoare (_: i = i0 ==> res = a i0) => // | probability / pr / probability, 1 goal, goal 194 chars | accepted commit |  |
| T0.1-3 | +00:06 | 2.9 s | 148 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 214 chars | accepted commit |  |
| T0.1-4 | +00:09 | 2.9 s | 144 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit inline PIR.query | phoare / procedure_body / procedure_frontier, 1 goal, goal 1040 chars | accepted commit |  |
| T0.1-5 | +00:14 | 4.9 s | 140 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1136 chars | accepted commit |  |
| T0.1-6 | +00:20 | 5.9 s | 100 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | tactic_forms | phoare / procedure_body / procedure_frontier, 1 goal, goal 1024 chars | manager result |  |
| T0.1-7 | +00:32 | 11.8 s | 167 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit while (0 <= j <= N /\ i = i0 /\ (j <= i0 => PIR.s = PIR.s') /\ (i0 <... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1024 chars | accepted commit |  |
| T0.1-8 | +00:52 | 19.8 s | 167 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit move => z; wp | phoare / procedure_body / procedure_frontier, 2 goals, goal 566 chars | accepted commit |  |
| T0.1-9 | +01:00 | 7.9 s | 94 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | tactic_forms | phoare / procedure_body / procedure_frontier, 2 goals, goal 1214 chars | manager result |  |
| T0.1-10 | +01:32 | 31.9 s | 135 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit rnd predT | phoare / procedure_body / procedure_frontier, 2 goals, goal 1214 chars | accepted commit |  |
| T0.1-11 | +02:22 | 49.8 s | 175 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit skip | phoare / procedure_body / procedure_frontier, 2 goals, goal 1342 chars | accepted commit |  |
| T0.1-12 | +02:39 | 16.9 s | 139 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit move => &hr [[[[Hjb [Hii [Hs Hsx]]] Hjlt] Hz] _] | ambient / ambient_logic, 2 goals, goal 1421 chars | accepted commit |  |
| T0.1-13 | +02:42 | 2.8 s | 163 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit split; first by rewrite dbool_ll | ambient / ambient_logic, 2 goals, goal 1368 chars | rejected commit: structural-fingerprint-equal |  |
| T0.1-14 | +02:53 | 11.1 s | 856 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit split | ambient / ambient_logic, 2 goals, goal 1368 chars | accepted commit |  |
| T0.1-15 | +02:57 | 2.9 s | 145 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit exact dbool_ll | ambient / ambient_logic, 3 goals, goal 416 chars | accepted commit |  |
| T0.1-16 | +03:08 | 10.9 s | 142 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit move => _ v hv; rewrite /predT /= Hii /= | ambient / ambient_logic, 2 goals, goal 1368 chars | accepted commit |  |
| T0.1-17 | +03:47 | 38.6 s | 352 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit smt(sxor_cons sxor2_cons) | ambient / ambient_logic, 2 goals, goal 1197 chars | accepted commit |  |
| T0.1-18 | +04:00 | [12.9 s](./views/Tree_0_1/thinking/turn_018.md) | 141 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 761 chars | accepted commit |  |
| T0.1-19 | +04:05 | 5.0 s | 979 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit skip => &hr Hi0; split; first by smt(N_pos) | phoare / procedure_body / procedure_frontier, 1 goal, goal 681 chars | rejected commit: [error] cannot find lemma `N_pos' |  |
| T0.1-20 | +04:15 | 8.9 s | 149 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit skip => &hr Hi0; split; first by smt() | phoare / procedure_body / procedure_frontier, 1 goal, goal 681 chars | accepted commit |  |
| T0.1-21 | +04:32 | [17.2 s](./views/Tree_0_1/thinking/turn_021.md) | 759 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | operator_lemmas | ambient / ambient_logic, 1 goal, goal 553 chars | manager result |  |
| T0.1-22 | +04:53 | [20.3 s](./views/Tree_0_1/thinking/turn_022.md) | 712 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | operator_lemmas | ambient / ambient_logic, 1 goal, goal 553 chars | manager result |  |
| T0.1-23 | +05:07 | 12.8 s | 189 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit move => s1 s' j0; split; first by smt() | ambient / ambient_logic, 1 goal, goal 553 chars | accepted commit |  |
| T0.1-24 | +05:22 | 14.8 s | 167 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit move => hnlt [hb [hi2 [hle hsxi]]]; have h: sxor2 s1 s' i0 by apply hsxi; smt() | ambient / ambient_logic, 1 goal, goal 413 chars | accepted commit |  |
| T0.1-25 | +05:28 | 5.9 s | 143 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit move: h; rewrite /sxor2 /sxor => -[[u1 u2 [-> ->]]\|[u1 u2 [-> ->]]] | ambient / ambient_logic, 1 goal, goal 438 chars | accepted commit |  |
| T0.1-26 | +05:39 | 10.6 s | 4.4 s | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit rewrite !big_cat big_consT; smt(xorwA xorwC xorwK xorw0) | ambient / ambient_logic, 2 goals, goal 483 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-27 | +05:56 | 12.9 s | 140 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit rewrite !big_cat big_consT | ambient / ambient_logic, 2 goals, goal 483 chars | accepted commit |  |
| T0.1-28 | +06:17 | 20.8 s | 4.2 s | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit move: (big predT<:int> a u1) (big predT<:int> a u2) => A B; smt(xorwA xorwC xorwK xorw0) | ambient / ambient_logic, 2 goals, goal 521 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-29 | +06:47 | [25.9 s](./views/Tree_0_1/thinking/turn_029.md) | 143 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit move: (big predT<:int> a u1) (big predT<:int> a u2) => A B | ambient / ambient_logic, 2 goals, goal 521 chars | accepted commit |  |
| T0.1-30 | +07:23 | [36 s](./views/Tree_0_1/thinking/turn_030.md) | 1 s | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit smt(xorwA xorwC xorwK xorw0 add0r addrr addrA addrC) | ambient / ambient_logic, 2 goals, goal 461 chars | rejected commit: [error] cannot find lemma `addrr' |  |
| T0.1-31 | +08:17 | [52.9 s](./views/Tree_0_1/thinking/turn_031.md) | 4.1 s | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit smt(xorwA xorwC xorwK xorw0) | ambient / ambient_logic, 2 goals, goal 461 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-32 | +08:55 | [33.8 s](./views/Tree_0_1/thinking/turn_032.md) | 172 ms | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit rewrite (xorwC (a i0) B) !xorwA | ambient / ambient_logic, 2 goals, goal 461 chars | accepted commit |  |
| T0.1-33 | +09:19 | 23.9 s | 149 ms | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | commit have hz : A +^ B +^ A +^ B = zerow by rewrite -xorwA xorwK | ambient / ambient_logic, 2 goals, goal 457 chars | accepted commit |  |
| T0.1-34 | +09:21 | 1.8 s | 163 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit by rewrite hz xorwC xorw0 | ambient / ambient_logic, 2 goals, goal 486 chars | accepted commit |  |
| T0.1-35 | +09:43 | [21.8 s](./views/Tree_0_1/thinking/turn_035.md) | 197 ms | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit rewrite xorwC !big_cat big_consT; move: (big predT<:int> a u1) (big predT<:int> a u2) => A B;... | ambient / ambient_logic, 1 goal, goal 468 chars | accepted commit |  |
| T0.1-36 | +09:47 | [3.8 s](./views/Tree_0_1/thinking/turn_036.md) | 159 ms | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | commit have hz : A +^ B +^ A +^ B = zerow by rewrite -xorwA xorwK. by rewrit... | ambient / ambient_logic, 1 goal, goal 442 chars | accepted commit |  |
| T0.1-37 | +09:50 | [2.9 s](./views/Tree_0_1/thinking/turn_037.md) | 145 ms | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-38 | +09:55 | 5 s |  | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
