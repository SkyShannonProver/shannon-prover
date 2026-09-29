# Agent-View Timeline — `step4_badi`

| field | value |
|---|---|
| commit | `45fe210c` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-09_1431_step4_badi |
| lemma | `step4_badi` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 52 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  move=> [h0nth0 hnth0q].
  byequiv (: ={glob A, glob BNR, glob Mem, glob UFCMA, glob UFCMA_l, glob ROIN.RO, glob ROout, glob ROF} /\ arg{2} = nth0 ==> ((let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) => UFCMA_li.badi{2})) => //.
  proc.
  inline*.
  wp.
  call (: ={BNR.lenc, BNR.ndec, Mem.log, Mem.lc, UFCMA.log, UFCMA.cbad1, UFCMA_l.lbad1, RO.m, SplitC2.I2.RO.m, SplitD.ROF.RO.m} /\ UFCMA_li.i{2} = nth0 /\ UFCMA_li.cbadi{2} = (if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\ (nth0 < size UFCMA_l.lbad1{2} => (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})).
  proc.
  sp; if => //.
  inline CPA_CCA_Orcls(UFCMA_l.O).enc CPA_CCA_Orcls(UFCMA_li.O).enc UFCMA_l.O.enc UFCMA_li.O.enc.
  wp.
  call (: ={SplitC2.I2.RO.m}).
  by auto.
  call (: ={RO.m}).
  by sim.
  call (: ={UFCMA.cbad1, UFCMA_l.lbad1} /\ UFCMA_li.i{2} = nth0 /\ (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\ (nth0 < size UFCMA_l.lbad1{2} => (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})).
  inline UFCMA_li.set_bad1i.
  case (UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec /\ size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}).
  rcondt{1} 2; 1: (by auto => /#); rcondt{2} 2; 1: (by auto => /#); rcondt{2} 2; 1: (by auto => /#); rcondt{2} 4; 1: (by auto => /#).
  wp; rnd; wp; rnd{2}; skip => />.
  move=> &2 hinv hc1 hltq hge hlt t1 _ tL _; rewrite size_cat size_map nth_cat; have -> /= : (nth0 < size UFCMA_l.lbad1{2}) = false by smt(); have hbnd : 0 <= nth0 - size UFCMA_l.lbad1{2} < size lt{2} by smt(); rewrite (nth_map witness) // /=; smt().
  have hbnd : 0 <= nth0 - size UFCMA_l.lbad1{2} < size lt{2} by smt(); rewrite hlt /= (nth_map witness) // /=; smt().
  rewrite hlt /= (nth_map witness) // /=; smt().
  seq 1 1 : (lt{1} = lt{2} /\ ={UFCMA.cbad1, UFCMA_l.lbad1, t} /\ UFCMA_li.i{2} = nth0 /\ (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\ (nth0 < size UFCMA_l.lbad1{2} => (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2}) /\ !(UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec /\ size UFCMA_l.lbad1{2} <= nth0 < size UFCMA_l.lbad1{2} + size lt{2})); 1: by auto => /#.
  if => //.
  rcondf{2} 1; 1: by auto => /#.
  auto => />.
  move=> &2 hinv hneg hc1 hltq; rewrite size_cat size_map nth_cat; case (nth0 < size UFCMA_l.lbad1{2}) => hcase /=; [ have -> /= : (nth0 < size UFCMA_l.lbad1{2} + size lt{2}) = true by smt(size_ge0); by apply (hinv hcase) | by have -> /= : (nth0 < size UFCMA_l.lbad1{2} + size lt{2}) = false by smt() ].
  by apply (hinv hcase).
  call (: ={RO.m}).
  by sim.
  by auto => />.
  proc.
  sp; if => //.
  inline CPA_CCA_Orcls(UFCMA_l.O).dec CPA_CCA_Orcls(UFCMA_li.O).dec UFCMA_l.O.dec UFCMA_li.O.dec.
  by auto => />.
  auto => />.
  split; [smt() | move=> _ _ lbad1_R badi_R hinv hproj; smt(nth_out neq_w1_w2)].
  qed.
```

### `Tree_0_1` — proved

```easycrypt
proof.
  move=> [h0nth0 hnth0q].
  byequiv (: ={glob A, glob BNR, glob Mem, glob UFCMA, glob UFCMA_l, glob ROIN.RO, glob ROout, glob ROF} /\ arg{2} = nth0 ==> ((let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) => UFCMA_li.badi{2})) => //.
  proc.
  inline*.
  wp.
  call (: ={BNR.lenc, BNR.ndec, Mem.log, Mem.lc, UFCMA.log, UFCMA.cbad1, UFCMA_l.lbad1, RO.m, SplitC2.I2.RO.m, SplitD.ROF.RO.m} /\ UFCMA_li.i{2} = nth0 /\ UFCMA_li.cbadi{2} = (if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\ (nth0 < size UFCMA_l.lbad1{2} => (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})).
  proc.
  sp; if => //.
  inline CPA_CCA_Orcls(UFCMA_l.O).enc CPA_CCA_Orcls(UFCMA_li.O).enc UFCMA_l.O.enc UFCMA_li.O.enc.
  wp.
  call (: ={SplitC2.I2.RO.m}).
  by auto.
  call (: ={RO.m}).
  by sim.
  call (: ={UFCMA.cbad1, UFCMA_l.lbad1} /\ UFCMA_li.i{2} = nth0 /\ (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\ (nth0 < size UFCMA_l.lbad1{2} => (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})).
  inline UFCMA_li.set_bad1i.
  case (UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec /\ size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}).
  rcondt{1} 2; 1: (by auto => /#); rcondt{2} 2; 1: (by auto => /#); rcondt{2} 2; 1: (by auto => /#); rcondt{2} 4; 1: (by auto => /#).
  wp; rnd; wp; rnd{2}; skip => />.
  move=> &2 hinv hc1 hltq hge hlt t1 _ tL _; rewrite size_cat size_map nth_cat; have -> /= : (nth0 < size UFCMA_l.lbad1{2}) = false by smt(); have hbnd : 0 <= nth0 - size UFCMA_l.lbad1{2} < size lt{2} by smt(); rewrite (nth_map witness) // /=; smt().
  have hbnd : 0 <= nth0 - size UFCMA_l.lbad1{2} < size lt{2} by smt(); rewrite hlt /= (nth_map witness) // /=; smt().
  rewrite hlt /= (nth_map witness) // /=; smt().
  seq 1 1 : (lt{1} = lt{2} /\ ={UFCMA.cbad1, UFCMA_l.lbad1, t} /\ UFCMA_li.i{2} = nth0 /\ (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\ (nth0 < size UFCMA_l.lbad1{2} => (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2}) /\ !(UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec /\ size UFCMA_l.lbad1{2} <= nth0 < size UFCMA_l.lbad1{2} + size lt{2})); 1: by auto => /#.
  if => //.
  rcondf{2} 1; 1: by auto => /#.
  auto => />.
  move=> &2 hinv hneg hc1 hltq; rewrite size_cat size_map nth_cat; case (nth0 < size UFCMA_l.lbad1{2}) => hcase /=; [ have -> /= : (nth0 < size UFCMA_l.lbad1{2} + size lt{2}) = true by smt(size_ge0); by apply (hinv hcase) | by have -> /= : (nth0 < size UFCMA_l.lbad1{2} + size lt{2}) = false by smt() ].
  by apply (hinv hcase).
  call (: ={RO.m}).
  by sim.
  by auto => />.
  proc.
  sp; if => //.
  inline CPA_CCA_Orcls(UFCMA_l.O).dec CPA_CCA_Orcls(UFCMA_li.O).dec UFCMA_l.O.dec UFCMA_li.O.dec.
  by auto => />.
  auto => />.
  split; [smt() | move=> _ _ lbad1_R badi_R hinv hproj; smt(nth_out neq_w1_w2)].
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-09_1431_step4_badi

Run dir: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1`

t=0: `2026-06-09T21:39:12.800000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 |  | 2.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> [h0nth0 hnth0q] | probability / pr / probability, 1 goal, goal 276 chars | accepted commit |  |
| T0.0-2 | +00:10 | 7.7 s | 285 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit byequiv (: ={glob A, glob BNR, glob Mem, glob UFCMA, glob UFCMA_l, gl... | probability / pr / probability, 1 goal, goal 307 chars | accepted commit |  |
| T0.0-3 | +00:17 | 7.2 s | 1.8 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 1343 chars | accepted commit |  |
| T0.0-4 | +00:28 | 8.3 s | 1.7 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit inline* | pRHL / call_site / seq_cut, 1 goal, goal 2153 chars | accepted commit |  |
| T0.0-5 | +00:44 | 15.3 s | 1.7 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 3881 chars | accepted commit |  |
| T0.0-6 | +01:01 | 14.6 s | 378 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit call (: ={BNR.lenc, BNR.ndec, Mem.log, Mem.lc, UFCMA.log, UFCMA.cbad1... | pRHL / call_site / seq_cut, 1 goal, goal 3605 chars | accepted commit |  |
| T0.0-7 | +01:10 | 8.6 s | 406 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 1518 chars | accepted commit |  |
| T0.0-8 | +01:16 | 5.6 s | 433 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit sp; if => // | pRHL / call_site / relational_program, 3 goals, goal 1960 chars | accepted commit |  |
| T0.0-9 | +01:27 | 10.5 s | 464 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit inline CPA_CCA_Orcls(UFCMA_l.O).enc CPA_CCA_Orcls(UFCMA_li.O).enc UFC... | pRHL / call_site / relational_program, 3 goals, goal 1810 chars | accepted commit |  |
| T0.0-10 | +02:46 | 78.5 s | 482 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit wp | pRHL / call_site / relational_program, 3 goals, goal 4210 chars | accepted commit |  |
| T0.0-11 | +02:53 | 6.6 s | 356 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit call (: ={SplitC2.I2.RO.m}) | pRHL / call_site / relational_program, 3 goals, goal 3748 chars | accepted commit |  |
| T0.0-12 | +03:02 | 8.6 s | 431 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit by auto | pRHL / verification_residue / relational_program, 4 goals, goal 554 chars | accepted commit |  |
| T0.0-13 | +03:10 | 7.6 s | 387 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit call (: ={RO.m}) | pRHL / call_site / relational_program, 3 goals, goal 3915 chars | accepted commit |  |
| T0.0-14 | +03:17 | 6.6 s | 448 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit by sim | pRHL / verification_residue / relational_program, 4 goals, goal 399 chars | accepted commit |  |
| T0.0-15 | +03:29 | 12.1 s | 1.9 s | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit call (: ={UFCMA.cbad1, UFCMA_l.lbad1} /\ UFCMA_li.i{2} = nth0 /\ (UFC... | pRHL / call_site / relational_program, 3 goals, goal 4050 chars | accepted commit |  |
| T0.0-16 | +04:51 | 80.2 s | 1.8 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit inline UFCMA_li.set_bad1i | pRHL / call_site / seq_cut, 4 goals, goal 2683 chars | accepted commit |  |
| T0.0-17 | +05:01 | 8.1 s | 1.9 s | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit case (UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec /\ size UFCMA_l.lba... | pRHL / procedure_body / seq_cut, 4 goals, goal 3055 chars | accepted commit |  |
| T0.0-18 | +05:32 | 29.2 s | 1.8 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit rcondt{1} 2; 1: (by auto => /#); rcondt{2} 2; 1: (by auto => /#); rcondt{2} 2; 1: (by auto =>... | pRHL / procedure_body / seq_cut, 5 goals, goal 3195 chars | accepted commit |  |
| T0.0-19 | +05:44 | 9.7 s | 295 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit wp; rnd; wp; rnd{2}; skip => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 2180 chars | accepted commit |  |
| T0.0-20 | +05:54 | 9.9 s | 5.1 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit smt(size_cat size_map nth_cat nth_map size_ge0) | ambient / ambient_logic, 5 goals, goal 1168 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-21 | +06:56 | 57.1 s | 1.9 s | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit move=> &2 hinv hc1 hltq hge hlt t1 _ tL _; rewrite size_cat size_map nth_cat; have -> /= : (n... | ambient / ambient_logic, 5 goals, goal 1168 chars | rejected commit: [error] invalid focus index: 1 |  |
| T0.0-22 | +07:23 | 24.7 s | 318 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit move=> &2 hinv hc1 hltq hge hlt t1 _ tL _; rewrite size_cat size_map nth_cat; have -> /= : (n... | ambient / ambient_logic, 5 goals, goal 1168 chars | accepted commit |  |
| T0.0-23 | +08:33 | 69.6 s | 379 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit have hbnd : 0 <= nth0 - size UFCMA_l.lbad1{2} < size lt{2} by smt(); rewrite hlt /= (nth_map... | ambient / ambient_logic, 5 goals, goal 945 chars | accepted commit |  |
| T0.0-24 | +09:00 | 27.1 s | 1.9 s | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit rewrite hlt /= (nth_map witness) // /=; smt() | ambient / ambient_logic, 5 goals, goal 998 chars | accepted commit |  |
| T0.0-25 | +09:55 | 52.5 s | 452 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit seq 1 1 : (lt{1} = lt{2} /\ ={UFCMA.cbad1, UFCMA_l.lbad1, t} /\ UFCMA_li.i{2} = nth0 /\ (UFCM... | pRHL / procedure_body / seq_cut, 4 goals, goal 3210 chars | accepted commit |  |
| T0.0-26 | +10:06 | 11.1 s | 1.9 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit if => //; 1: by move=> &1 &2 /# | pRHL / procedure_body / relational_program, 4 goals, goal 3112 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-27 | +10:15 | 6.6 s | 426 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit if => // | pRHL / procedure_body / relational_program, 4 goals, goal 3112 chars | accepted commit |  |
| T0.0-28 | +10:23 | 7.8 s | 5.2 s | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit rcondf{2} 1; 1: (by auto => /#); by auto => />; smt(size_cat size_map nth_cat) | pRHL / procedure_body / relational_program, 4 goals, goal 2783 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-29 | +10:39 | 10.5 s | 490 ms | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit rcondf{2} 1; 1: by auto => /# | pRHL / procedure_body / relational_program, 4 goals, goal 2783 chars | accepted commit |  |
| T0.0-30 | +11:04 | 25.1 s | 1.9 s | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit auto => /> *; rewrite size_cat size_map nth_cat; case (nth0 < size UFCMA_l.lbad1{2}) => /= hc... | pRHL / procedure_body / relational_program, 4 goals, goal 1519 chars | rejected commit: [error] unknown memory: &2 |  |
| T0.0-31 | +11:18 | 11.8 s | 5.2 s | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | commit auto => /> *; rewrite size_cat size_map nth_cat; smt() | pRHL / procedure_body / relational_program, 4 goals, goal 1519 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-32 | +11:53 | 30 s | 5 s | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit auto => /> *; rewrite ?size_cat ?size_map ?nth_cat; smt() | pRHL / procedure_body / relational_program, 4 goals, goal 1519 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-33 | +12:07 | 8.7 s | 271 ms | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | commit auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 1519 chars | accepted commit |  |
| T0.0-34 | +12:42 | 35.1 s | 4.9 s | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | commit move=> &2 hinv hneg hc1 hltq; rewrite size_cat size_map nth_cat; smt() | ambient / ambient_logic, 4 goals, goal 998 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-35 | +13:35 | 48.1 s | 1.9 s | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | commit move=> &2 hinv hneg hc1 hltq; rewrite size_cat size_map nth_cat; case (nth0 < size UFCMA_l.lb... | ambient / ambient_logic, 4 goals, goal 998 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-36 | +14:11 | 33.6 s | 375 ms | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit move=> &2 hinv hneg hc1 hltq; rewrite size_cat size_map nth_cat; case (nth0 < size UFCMA_l.lb... | ambient / ambient_logic, 4 goals, goal 998 chars | accepted commit |  |
| T0.0-37 | +14:23 | 11.6 s | 433 ms | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | commit by apply (hinv hcase) | ambient / ambient_logic, 4 goals, goal 725 chars | accepted commit |  |
| T0.0-38 | +14:57 | 33.6 s | 427 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit call (: ={RO.m}) | pRHL / verification_residue / relational_program, 3 goals, goal 3893 chars | accepted commit |  |
| T0.0-39 | +15:04 | 6.6 s | 429 ms | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | commit by sim | pRHL / procedure_body / relational_program, 4 goals, goal 1682 chars | accepted commit |  |
| T0.0-40 | +15:13 | 8.7 s | 302 ms | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit by auto => /> | pRHL / verification_residue / relational_program, 3 goals, goal 4189 chars | accepted commit |  |
| T0.0-41 | +15:43 | 29.5 s | 459 ms | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 1518 chars | accepted commit |  |
| T0.0-42 | +16:07 | 23.5 s | 518 ms | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit sp; if => // | pRHL / call_site / relational_program, 2 goals, goal 1974 chars | accepted commit |  |
| T0.0-43 | +16:18 | 10.6 s | 399 ms | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | commit inline CPA_CCA_Orcls(UFCMA_l.O).dec CPA_CCA_Orcls(UFCMA_li.O).dec UFC... | pRHL / call_site / relational_program, 2 goals, goal 1813 chars | accepted commit |  |
| T0.0-44 | +16:24 | 5.4 s | 623 ms | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | commit by auto => /> | pRHL / verification_residue / relational_program, 2 goals, goal 1934 chars | accepted commit |  |
| T0.0-45 | +16:47 | 22.8 s | 5.2 s | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | commit by auto => />; smt() | pRHL / procedure_body / relational_program, 1 goal, goal 4841 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-46 | +17:02 | 9.7 s | 284 ms | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | commit auto => /> | pRHL / procedure_body / relational_program, 1 goal, goal 4841 chars | accepted commit |  |
| T0.0-47 | +17:20 | 18.1 s | 4.9 s | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | commit smt() | ambient / ambient_logic, 1 goal, goal 545 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-48 | +17:42 | 17.1 s | 4.9 s | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | commit smt(neq_w1_w2) | ambient / ambient_logic, 1 goal, goal 545 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-49 | +18:11 | 23.6 s | 372 ms | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | commit split; [smt() \| move=> _ _ lbad1_R badi_R hinv hproj; smt(nth_out neq_w1_w2)] | ambient / ambient_logic, 1 goal, goal 545 chars | accepted commit |  |
| T0.0-50 | +18:15 | 4 s |  | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.0-51 | +18:19 | 3.7 s | 265 ms | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-52 | +18:23 | 4 s |  | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
