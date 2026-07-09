# Agent-View Timeline — `step2_2`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1436_step2_2 |
| lemma | `step2_2` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 81 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 25 tactic(s) committed, not closed

```easycrypt
proof.
  apply ler_add.
  byequiv (_: ={glob A} ==> ={res}).
  conseq UFCMA_genCC.
  smt().
  done.
  smt().
  byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec StLSke.gs Mem.k c <> None){1} => res{2}).
  proc*.
  inline {2} 1.
  seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}).
  call UFCMA_genCC.
  auto.
  sp; wp.
  while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2} /\ ns{2} = undup (map (fun (p:ciphertext) => p.`1) Mem.lc{2}) /\ (forall (c:ciphertext), c \in Mem.lc{2} => dec StLSke.gs{1} Mem.k{1} c <> None => (c.`1 \in take i{2} ns{2}) => forged{2})) (size ns{2} - i{2}).
  move=> &m0 z; inline FinRO.get; wp; skip.
  move=> &hr [[H Hlt] Hz]; case: H => i_rng [Hlc [Hgs [Hns IH]]].
  split; last by smt(); do 4! (split; first by smt()).
  do 4! (split; first by smt()).
  move=> c Hc Hdec; rewrite (take_nth witness) 1:/# mem_rcons in_cons.
  move=> [Hn0 | Hold]; last by have := IH c Hc Hdec Hold; smt().
  right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); split; first by apply/List.mapP; exists c; rewrite mem_filter /=; smt().
  move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=; rewrite Hgs /=; smt().
  skip.
  move=> &1 &2 [Hns [Hf [Hi [Hlc Hgs]]]]; split; first by rewrite Hi; smt(size_ge0 take0 in_nil).
  move=> forged_R i_R; split; first by move=> [hb _] hsz; smt().
  (* proof not completed in this run *)
```

### `Tree_0_0_r2` — proved

```easycrypt
proof.
  apply ler_add.
  byequiv (_: ={glob A} ==> ={res}).
  conseq UFCMA_genCC.
  smt().
  done.
  smt().
  byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec StLSke.gs Mem.k c <> None){1} => res{2}).
  proc*.
  inline {2} 1.
  seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}).
  call UFCMA_genCC.
  auto.
  sp; wp.
  while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2} /\ ns{2} = undup (map (fun (p:ciphertext) => p.`1) Mem.lc{2}) /\ (forall (c:ciphertext), c \in Mem.lc{2} => dec StLSke.gs{1} Mem.k{1} c <> None => (c.`1 \in take i{2} ns{2}) => forged{2})) (size ns{2} - i{2}).
  move=> &m0 z; inline FinRO.get; wp; skip.
  move=> &hr [[H Hlt] Hz]; case: H => i_rng [Hlc [Hgs [Hns IH]]].
  split; last by smt(); do 4! (split; first by smt()).
  do 4! (split; first by smt()).
  move=> c Hc Hdec; rewrite (take_nth witness) 1:/# mem_rcons in_cons.
  move=> [Hn0 | Hold]; last by have := IH c Hc Hdec Hold; smt().
  right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); split; first by apply/List.mapP; exists c; rewrite mem_filter /=; smt().
  move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=; rewrite Hgs /=; smt().
  skip.
  move=> &1 &2 [Hns [Hf [Hi [Hlc Hgs]]]]; split; first by rewrite Hi; smt(size_ge0 take0 in_nil).
  move=> forged_R i_R; split; first by move=> [hb _] hsz; smt().
  move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]].
  apply (IH c); [ by rewrite -Hlc' | exact Hdec | rewrite take_oversize 1:/# Hns' mem_undup -Hlc'; apply/mapP; exists c => /=; exact Hc ].
  done.
  by move=> &1 &2 H Hc; apply H.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1436_step2_2

Run dir: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1`

t=0: `2026-06-10T21:37:31.500000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 478 chars | read-only inspect |  |
| T0.0-2 | +00:08 | [6.8 s](./views/Tree_0_0/thinking/turn_002.md) | 250 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | inspect lemma_index | probability / pr / probability, 1 goal, goal 478 chars | read-only inspect |  |
| T0.0-3 | +00:35 | [26.1 s](./views/Tree_0_0/thinking/turn_003.md) | 1.9 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | probe apply ler_add | probability / pr / probability, 1 goal, goal 478 chars | accepted probe |  |
| T0.0-4 | +00:44 | [7.3 s](./views/Tree_0_0/thinking/turn_004.md) | 684 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit apply ler_add | probability / pr / probability, 1 goal, goal 478 chars | accepted commit |  |
| T0.0-5 | +01:22 | [37.4 s](./views/Tree_0_0/thinking/turn_005.md) | 1.6 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | inspect pr_bridge_routes | probability / pr / probability, 2 goals, goal 308 chars | read-only inspect |  |
| T0.0-6 | +01:39 | [15.2 s](./views/Tree_0_0/thinking/turn_006.md) | 760 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe byequiv (_: ={glob A} ==> ={res}) | probability / pr / probability, 2 goals, goal 308 chars | accepted probe |  |
| T0.0-7 | +02:11 | [31.8 s](./views/Tree_0_0/thinking/turn_007.md) | 246 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit byequiv (_: ={glob A} ==> ={res}) | probability / pr / probability, 2 goals, goal 308 chars | accepted commit |  |
| T0.0-8 | +02:30 | [18 s](./views/Tree_0_0/thinking/turn_008.md) |  | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | inspect call_site_options | equiv / prhl_module / relational_program, 4 goals, goal 584 chars | read-only inspect |  |
| T0.0-9 | +02:34 | [4.7 s](./views/Tree_0_0/thinking/turn_009.md) | 1.3 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | probe proc | equiv / prhl_module / relational_program, 4 goals, goal 584 chars | accepted probe |  |
| T0.0-10 | +02:42 | [6.7 s](./views/Tree_0_0/thinking/turn_010.md) | 284 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit proc | equiv / prhl_module / relational_program, 4 goals, goal 584 chars | accepted commit |  |
| T0.0-11 | +02:47 | [4.9 s](./views/Tree_0_0/thinking/turn_011.md) | 1.1 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 4 goals, goal 737 chars | read-only inspect |  |
| T0.0-12 | +03:16 | [28 s](./views/Tree_0_0/thinking/turn_012.md) |  | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | inspect propose_invariant | pRHL / call_site / failure_diagnostic, 4 goals, goal 737 chars | read-only inspect |  |
| T0.0-13 | +04:29 | [72.9 s](./views/Tree_0_0/thinking/turn_013.md) | 121 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | inspect call_subgoals | pRHL / call_site / failure_diagnostic, 4 goals, goal 737 chars | read-only inspect |  |
| T0.0-14 | +05:07 | 37.7 s | 1.3 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | undo_last_step | pRHL / call_site / failure_diagnostic, 4 goals, goal 737 chars | undo result |  |
| T0.0-15 | +05:27 | [18.7 s](./views/Tree_0_0/thinking/turn_015.md) | 2.3 s | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | probe conseq UFCMA_genCC | equiv / prhl_module / relational_program, 4 goals, goal 571 chars | accepted probe |  |
| T0.0-16 | +05:37 | [7.7 s](./views/Tree_0_0/thinking/turn_016.md) | 282 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit conseq UFCMA_genCC | equiv / prhl_module / seq_cut, 4 goals, goal 571 chars | accepted commit |  |
| T0.0-17 | +05:44 | [6.8 s](./views/Tree_0_0/thinking/turn_017.md) | 213 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit smt() | ambient / ambient_logic / relational_program, 4 goals, goal 414 chars | accepted commit |  |
| T0.0-18 | +05:50 | [5.7 s](./views/Tree_0_0/thinking/turn_018.md) | 304 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit done | ambient / ambient_logic, 3 goals, goal 171 chars | accepted commit |  |
| T0.0-19 | +05:55 | [4.4 s](./views/Tree_0_0/thinking/turn_019.md) | 613 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit smt() | ambient / ambient_logic / relational_program, 2 goals, goal 195 chars | accepted commit |  |
| T0.0-20 | +09:07 | [191.2 s](./views/Tree_0_0/thinking/turn_020.md) | 1.8 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | probe byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec... | probability / pr / probability, 1 goal, goal 327 chars | accepted probe |  |
| T0.0-21 | +09:29 | [20.8 s](./views/Tree_0_0/thinking/turn_021.md) | 220 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit byequiv (_: ={glob A} ==> (exists (c:ciphertext), c \in Mem.lc /\ dec... | probability / pr / probability, 1 goal, goal 327 chars | accepted commit |  |
| T0.0-22 | +09:36 | [6.7 s](./views/Tree_0_0/thinking/turn_022.md) | 1.3 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | probe proc* | equiv / prhl_module / relational_program, 3 goals, goal 379 chars | accepted probe |  |
| T0.0-23 | +09:42 | [4.7 s](./views/Tree_0_0/thinking/turn_023.md) | 287 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit proc* | equiv / prhl_module / relational_program, 3 goals, goal 379 chars | accepted commit |  |
| T0.0-24 | +12:09 | [146.6 s](./views/Tree_0_0/thinking/turn_024.md) | 1.4 s | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | probe inline {2} 1 | pRHL / call_site / relational_program, 3 goals, goal 440 chars | accepted probe |  |
| T0.0-25 | +12:27 | [16.7 s](./views/Tree_0_0/thinking/turn_025.md) | 313 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit inline {2} 1 | pRHL / call_site / relational_program, 3 goals, goal 440 chars | accepted commit |  |
| T0.0-26 | +13:16 | [48.6 s](./views/Tree_0_0/thinking/turn_026.md) | 1.4 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | probe seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}) | pRHL / call_site / relational_program, 3 goals, goal 1867 chars | accepted probe |  |
| T0.0-27 | +13:25 | [7.7 s](./views/Tree_0_0/thinking/turn_027.md) | 288 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit seq 1 1 : (={Mem.lc} /\ StLSke.gs{1} = RO.m{2}) | pRHL / call_site / seq_cut, 3 goals, goal 1867 chars | accepted commit |  |
| T0.0-28 | +13:39 | [13.5 s](./views/Tree_0_0/thinking/turn_028.md) | 1.5 s | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | probe call UFCMA_genCC | pRHL / call_site / relational_program, 4 goals, goal 541 chars | accepted probe |  |
| T0.0-29 | +13:46 | [5.7 s](./views/Tree_0_0/thinking/turn_029.md) | 304 ms | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit call UFCMA_genCC | pRHL / call_site / relational_program, 4 goals, goal 541 chars | accepted commit |  |
| T0.0-30 | +13:52 | [5.7 s](./views/Tree_0_0/thinking/turn_030.md) | 318 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit auto | pRHL / prhl_module / relational_program, 4 goals, goal 598 chars | accepted commit |  |
| T0.0-31 | +14:45 | [52.6 s](./views/Tree_0_0/thinking/turn_031.md) | 1.4 s | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | probe sp; wp | pRHL / call_site / relational_program, 3 goals, goal 1605 chars | accepted probe |  |
| T0.0-32 | +15:15 | [28.7 s](./views/Tree_0_0/thinking/turn_032.md) | 336 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit sp; wp | pRHL / call_site / relational_program, 3 goals, goal 1605 chars | accepted commit |  |
| T0.0-33 | +17:08 | [112.6 s](./views/Tree_0_0/thinking/turn_033.md) | 1.4 s | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | probe while{2} (0 <= i{2} <= size ns{2}) (size ns{2} - i{2}) | pRHL / call_site / relational_program, 3 goals, goal 1179 chars | accepted probe |  |
| T0.0-34 | +18:13 | [63.7 s](./views/Tree_0_0/thinking/turn_034.md) | 291 ms | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | probe while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ ns{2} =... | pRHL / call_site / relational_program, 3 goals, goal 1179 chars | accepted probe |  |
| T0.0-35 | +20:01 | [107.7 s](./views/Tree_0_0/thinking/turn_035.md) | 260 ms | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | commit while{2} (0 <= i{2} <= size ns{2} /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.... | pRHL / call_site / relational_program, 3 goals, goal 1179 chars | accepted commit |  |
| T0.0-36 | +20:34 | [32.7 s](./views/Tree_0_0/thinking/turn_036.md) | 1.3 s | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | probe move=> &m0 z; inline FinRO.get; wp; skip | phoare / procedure_body / procedure_frontier, 4 goals, goal 1082 chars | accepted probe |  |
| T0.0-37 | +21:04 | [28.8 s](./views/Tree_0_0/thinking/turn_037.md) | 249 ms | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | commit move=> &m0 z; inline FinRO.get; wp; skip | phoare / procedure_body / procedure_frontier, 4 goals, goal 1082 chars | accepted commit |  |
| T0.0-38 | +21:50 | [45.6 s](./views/Tree_0_0/thinking/turn_038.md) | 1.4 s | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | probe move=> &hr [[H Hlt] Hz]; case: H => i_rng eqlc eqgs eqns Hold | ambient / ambient_logic, 4 goals, goal 1122 chars | accepted probe |  |
| T0.0-39 | +22:18 | [26.7 s](./views/Tree_0_0/thinking/turn_039.md) | 266 ms | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | probe move=> &hr [[H Hlt] Hz]; case: H => i_rng [Hlc [Hgs [Hns IH]]] | ambient / ambient_logic, 4 goals, goal 1122 chars | accepted probe |  |
| T0.0-40 | +22:42 | [23.8 s](./views/Tree_0_0/thinking/turn_040.md) | 249 ms | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit move=> &hr [[H Hlt] Hz]; case: H => i_rng [Hlc [Hgs [Hns IH]]] | ambient / ambient_logic, 4 goals, goal 1122 chars | accepted commit |  |
| T0.0-41 | +23:12 | [29.5 s](./views/Tree_0_0/thinking/turn_041.md) | 1.5 s | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | probe split; last by smt(); do 4! (split; first by smt()) | ambient / ambient_logic, 4 goals, goal 1200 chars | accepted probe |  |
| T0.0-42 | +24:58 | [104.7 s](./views/Tree_0_0/thinking/turn_042.md) | 332 ms | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit split; last by smt(); do 4! (split; first by smt()) | ambient / ambient_logic, 4 goals, goal 1200 chars | accepted commit |  |
| T0.0-43 | +25:38 | [39.2 s](./views/Tree_0_0/thinking/turn_043.md) | 1.8 s | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | probe do 5! (split; first by smt()) | ambient / ambient_logic, 4 goals, goal 1239 chars | rejected probe: cannot apply `split/None` on that goal |  |
| T0.0-44 | +26:14 | [34.5 s](./views/Tree_0_0/thinking/turn_044.md) | 515 ms | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | probe do 4! (split; first by smt()) | ambient / ambient_logic, 4 goals, goal 1239 chars | accepted probe |  |
| T0.0-45 | +26:23 | [8.6 s](./views/Tree_0_0/thinking/turn_045.md) | 448 ms | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | commit do 4! (split; first by smt()) | ambient / ambient_logic, 4 goals, goal 1239 chars | accepted commit |  |
| T0.0-46 | +26:37 | [13.9 s](./views/Tree_0_0/thinking/turn_046.md) | 1.1 s | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | lookup test_poly | ambient / ambient_logic, 4 goals, goal 1085 chars | lookup result |  |
| T0.0-47 | +26:51 | [12.8 s](./views/Tree_0_0/thinking/turn_047.md) | 1.2 s | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | lookup dec | ambient / ambient_logic, 4 goals, goal 1085 chars | lookup result |  |
| T0.0-48 | +28:35 | [102.3 s](./views/Tree_0_0/thinking/turn_048.md) | 1.7 s | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | probe move=> c Hc Hdec; rewrite (take_nth witness) 1:/# mem_rcons in_cons | ambient / ambient_logic, 4 goals, goal 1085 chars | accepted probe |  |
| T0.0-49 | +28:43 | [6.7 s](./views/Tree_0_0/thinking/turn_049.md) | 283 ms | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | commit move=> c Hc Hdec; rewrite (take_nth witness) 1:/# mem_rcons in_cons | ambient / ambient_logic, 4 goals, goal 1085 chars | accepted commit |  |
| T0.0-50 | +28:53 | [9.3 s](./views/Tree_0_0/thinking/turn_050.md) | 1.7 s | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | probe move=> [Hn0 \| Hold]; last by have := IH c Hc Hdec Hold; smt() | ambient / ambient_logic, 4 goals, goal 1103 chars | accepted probe |  |
| T0.0-51 | +29:00 | 5.7 s | 342 ms | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit move=> [Hn0 \| Hold]; last by have := IH c Hc Hdec Hold; smt() | ambient / ambient_logic, 4 goals, goal 1103 chars | accepted commit |  |
| T0.0-52 | +30:02 | [61.3 s](./views/Tree_0_0/thinking/turn_052.md) | 1.7 s | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | probe right; rewrite /test_poly hasP; exists (topol c.`2 c.`3, c.`4); split; first by apply/mapP; e... | ambient / ambient_logic, 4 goals, goal 1073 chars | rejected probe: nothing to rewrite |  |
| T0.0-53 | +30:13 | [9.8 s](./views/Tree_0_0/thinking/turn_053.md) | 225 ms | [turn_052.json](./views/Tree_0_0/turn_052.json) · [inline read](./views/Tree_0_0/followups/turn_052.md) | probe right; rewrite /test_poly /= | ambient / ambient_logic, 4 goals, goal 1073 chars | accepted probe |  |
| T0.0-54 | +30:38 | [24.7 s](./views/Tree_0_0/thinking/turn_054.md) | 279 ms | [turn_053.json](./views/Tree_0_0/turn_053.json) · [inline read](./views/Tree_0_0/followups/turn_053.md) | probe right; rewrite /test_poly /=; move=> _; apply/hasP; exists (topol c.`2 c.`3, c.`4); split; fi... | ambient / ambient_logic, 4 goals, goal 1073 chars | rejected probe: the given proof-term proves: |  |
| T0.0-55 | +30:52 | [13.7 s](./views/Tree_0_0/thinking/turn_055.md) | 273 ms | [turn_054.json](./views/Tree_0_0/turn_054.json) · [inline read](./views/Tree_0_0/followups/turn_054.md) | probe right; rewrite /test_poly /=; move=> _; apply/hasP | ambient / ambient_logic, 4 goals, goal 1073 chars | rejected probe: the given proof-term proves: |  |
| T0.0-56 | +30:57 | [4.9 s](./views/Tree_0_0/thinking/turn_056.md) | 1.1 s | [turn_055.json](./views/Tree_0_0/turn_055.json) · [inline read](./views/Tree_0_0/followups/turn_055.md) | lookup hasP | ambient / ambient_logic, 4 goals, goal 1073 chars | lookup result |  |
| T0.0-57 | +31:07 | [8.8 s](./views/Tree_0_0/thinking/turn_057.md) | 215 ms | [turn_056.json](./views/Tree_0_0/turn_056.json) · [inline read](./views/Tree_0_0/followups/turn_056.md) | probe right; rewrite /test_poly /=; move=> _; rewrite List.hasP; exists (topol c.`2 c.`3, c.`4); sp... | ambient / ambient_logic, 4 goals, goal 1073 chars | rejected probe: nothing to rewrite |  |
| T0.0-58 | +31:16 | [8.8 s](./views/Tree_0_0/thinking/turn_058.md) | 230 ms | [turn_057.json](./views/Tree_0_0/turn_057.json) · [inline read](./views/Tree_0_0/followups/turn_057.md) | probe right; rewrite /test_poly /=; move=> _; apply/List.hasP | ambient / ambient_logic, 4 goals, goal 1073 chars | accepted probe |  |
| T0.0-59 | +31:29 | [12.8 s](./views/Tree_0_0/thinking/turn_059.md) | 220 ms | [turn_058.json](./views/Tree_0_0/turn_058.json) · [inline read](./views/Tree_0_0/followups/turn_058.md) | probe right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); spli... | ambient / ambient_logic, 4 goals, goal 1073 chars | rejected probe: cannot find lemma `Hc' |  |
| T0.0-60 | +31:45 | [15.6 s](./views/Tree_0_0/thinking/turn_060.md) | 400 ms | [turn_059.json](./views/Tree_0_0/turn_059.json) · [inline read](./views/Tree_0_0/followups/turn_059.md) | probe right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); spli... | ambient / ambient_logic, 4 goals, goal 1073 chars | accepted probe |  |
| T0.0-61 | +31:54 | [8.7 s](./views/Tree_0_0/thinking/turn_061.md) | 319 ms | [turn_060.json](./views/Tree_0_0/turn_060.json) · [inline read](./views/Tree_0_0/followups/turn_060.md) | commit right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); spli... | ambient / ambient_logic, 4 goals, goal 1073 chars | accepted commit |  |
| T0.0-62 | +32:37 | [42.9 s](./views/Tree_0_0/thinking/turn_062.md) | 2.1 s | [turn_061.json](./views/Tree_0_0/turn_061.json) · [inline read](./views/Tree_0_0/followups/turn_061.md) | probe rewrite /=; move: Hdec; rewrite /dec /genpoly1305 /get Hgs Hn0 /=; smt() | ambient / ambient_logic, 4 goals, goal 1100 chars | rejected probe: nothing to rewrite |  |
| T0.0-63 | +33:01 | [21.7 s](./views/Tree_0_0/thinking/turn_063.md) | 277 ms | [turn_062.json](./views/Tree_0_0/turn_062.json) · [inline read](./views/Tree_0_0/followups/turn_062.md) | probe move: Hdec; rewrite /dec /genpoly1305 /get /= | ambient / ambient_logic, 4 goals, goal 1100 chars | accepted probe |  |
| T0.0-64 | +33:59 | [57.6 s](./views/Tree_0_0/thinking/turn_064.md) | 360 ms | [turn_063.json](./views/Tree_0_0/turn_063.json) · [inline read](./views/Tree_0_0/followups/turn_063.md) | probe move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=; rewrite Hgs... | ambient / ambient_logic, 4 goals, goal 1100 chars | accepted probe |  |
| T0.0-65 | +34:06 | [6.6 s](./views/Tree_0_0/thinking/turn_065.md) | 409 ms | [turn_064.json](./views/Tree_0_0/turn_064.json) · [inline read](./views/Tree_0_0/followups/turn_064.md) | commit move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=; rewrite Hgs... | ambient / ambient_logic, 4 goals, goal 1100 chars | accepted commit |  |
| T0.0-66 | +34:46 | [39.2 s](./views/Tree_0_0/thinking/turn_066.md) | 1.8 s | [turn_065.json](./views/Tree_0_0/turn_065.json) · [inline read](./views/Tree_0_0/followups/turn_065.md) | probe skip | pRHL / procedure_entry / relational_program, 3 goals, goal 1770 chars | accepted probe |  |
| T0.0-67 | +35:20 | [32.6 s](./views/Tree_0_0/thinking/turn_067.md) | 358 ms | [turn_066.json](./views/Tree_0_0/turn_066.json) · [inline read](./views/Tree_0_0/followups/turn_066.md) | commit skip | pRHL / procedure_entry / relational_program, 3 goals, goal 1770 chars | accepted commit |  |
| T0.0-68 | +36:40 | [79.1 s](./views/Tree_0_0/thinking/turn_068.md) | 1.9 s | [turn_067.json](./views/Tree_0_0/turn_067.json) · [inline read](./views/Tree_0_0/followups/turn_067.md) | probe move=> &1 &2 [Hns [Hf [Hi [Hlc Hgs]]]]; split; first by rewrite Hi; smt(size_ge0 take0 in_nil) | ambient / ambient_logic / relational_program, 3 goals, goal 1625 chars | accepted probe |  |
| T0.0-69 | +36:48 | [6.6 s](./views/Tree_0_0/thinking/turn_069.md) | 412 ms | [turn_068.json](./views/Tree_0_0/turn_068.json) · [inline read](./views/Tree_0_0/followups/turn_068.md) | commit move=> &1 &2 [Hns [Hf [Hi [Hlc Hgs]]]]; split; first by rewrite Hi; smt(size_ge0 take0 in_nil) | ambient / ambient_logic / relational_program, 3 goals, goal 1625 chars | accepted commit |  |
| T0.0-70 | +36:55 | [6.2 s](./views/Tree_0_0/thinking/turn_070.md) | 1.8 s | [turn_069.json](./views/Tree_0_0/turn_069.json) · [inline read](./views/Tree_0_0/followups/turn_069.md) | probe move=> forged_R i_R; split; first by move=> [hb _] hsz; smt() | ambient / ambient_logic / relational_program, 3 goals, goal 1355 chars | accepted probe |  |
| T0.0-71 | +37:04 | [7.6 s](./views/Tree_0_0/thinking/turn_071.md) | 352 ms | [turn_070.json](./views/Tree_0_0/turn_070.json) · [inline read](./views/Tree_0_0/followups/turn_070.md) | commit move=> forged_R i_R; split; first by move=> [hb _] hsz; smt() | ambient / ambient_logic / relational_program, 3 goals, goal 1355 chars | accepted commit |  |

### Tree-0.0.r2

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0.r2-1 | +38:23 | [think](./views/Tree_0_0_r2/thinking/turn_001.md) | 2.1 s | [manager_bootstrap_0_0_r2.json](./views/_bootstrap/manager_bootstrap_0_0_r2.json) | probe move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]]; apply (IH c); first by rewrite -H... | ambient / ambient_logic / relational_program, 3 goals, goal 914 chars | rejected probe: manager reported rejection |  |
| T0.0.r2-2 | +38:32 | [6.9 s](./views/Tree_0_0_r2/thinking/turn_002.md) | 105 ms | [turn_001.json](./views/Tree_0_0_r2/turn_001.json) · [inline read](./views/Tree_0_0_r2/followups/turn_001.md) | inspect diagnose | ambient / ambient_logic / relational_program, 3 goals, goal 914 chars | read-only inspect |  |
| T0.0.r2-3 | +38:40 | 7.8 s | 202 ms | [turn_002.json](./views/Tree_0_0_r2/turn_002.json) · [inline read](./views/Tree_0_0_r2/followups/turn_002.md) | probe move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]] | ambient / ambient_logic / relational_program, 3 goals, goal 914 chars | accepted probe |  |
| T0.0.r2-4 | +39:04 | [23.7 s](./views/Tree_0_0_r2/thinking/turn_004.md) | 323 ms | [turn_003.json](./views/Tree_0_0_r2/turn_003.json) · [inline read](./views/Tree_0_0_r2/followups/turn_003.md) | commit move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]] | ambient / ambient_logic / relational_program, 3 goals, goal 914 chars | accepted commit |  |
| T0.0.r2-5 | +39:28 | [23 s](./views/Tree_0_0_r2/thinking/turn_005.md) | 2 s | [turn_004.json](./views/Tree_0_0_r2/turn_004.json) · [inline read](./views/Tree_0_0_r2/followups/turn_004.md) | probe apply (IH c); [ by rewrite -Hlc' \| exact Hdec \| rewrite take_oversize 1:/# Hns' mem_undup -Hl... | ambient / ambient_logic / relational_program, 3 goals, goal 918 chars | accepted probe |  |
| T0.0.r2-6 | +39:35 | [5.7 s](./views/Tree_0_0_r2/thinking/turn_006.md) | 327 ms | [turn_005.json](./views/Tree_0_0_r2/turn_005.json) · [inline read](./views/Tree_0_0_r2/followups/turn_005.md) | commit apply (IH c); [ by rewrite -Hlc' \| exact Hdec \| rewrite take_oversize 1:/# Hns' mem_undup -Hl... | ambient / ambient_logic / relational_program, 3 goals, goal 918 chars | accepted commit |  |
| T0.0.r2-7 | +39:40 | 4.7 s | 283 ms | [turn_006.json](./views/Tree_0_0_r2/turn_006.json) · [inline read](./views/Tree_0_0_r2/followups/turn_006.md) | commit done | ambient / ambient_logic, 2 goals, goal 171 chars | accepted commit |  |
| T0.0.r2-8 | +39:45 | [4.8 s](./views/Tree_0_0_r2/thinking/turn_008.md) | 199 ms | [turn_007.json](./views/Tree_0_0_r2/turn_007.json) · [inline read](./views/Tree_0_0_r2/followups/turn_007.md) | commit by move=> &1 &2 H Hc; apply H | ambient / ambient_logic / relational_program, 1 goal, goal 436 chars | accepted commit |  |
| T0.0.r2-9 | +39:49 | [3.8 s](./views/Tree_0_0_r2/thinking/turn_009.md) | 202 ms | [turn_008.json](./views/Tree_0_0_r2/turn_008.json) · [inline read](./views/Tree_0_0_r2/followups/turn_008.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0.r2-10 | +39:54 | 4 s |  | [turn_009.json](./views/Tree_0_0_r2/turn_009.json) · [inline read](./views/Tree_0_0_r2/followups/turn_009.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
