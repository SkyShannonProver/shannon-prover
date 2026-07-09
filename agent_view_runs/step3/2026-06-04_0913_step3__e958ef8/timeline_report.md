# Agent-View Timeline — `step3`

| field | value |
|---|---|
| commit | `e958ef8` |
| branch | `HEAD` |
| run time | 2026-06-04_0913_step3 |
| lemma | `step3` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 89 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 11 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv => //.
  proc.
  inline*.
  wp.
  call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in SplitC1.I2.RO.m{1} => n \in BNR.lenc{1}) /\ (forall n c, (n,c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).
  proc.
  sp; if.
  move=> &1 &2; rewrite /inv_cpa; smt().
  inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc.
  inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.
  sp.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  byequiv => //.
  proc.
  inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish.
  inline{1} G6(BNR_Adv(A), SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO)).distinguish.
  inline{1} G4(BNR_Adv(A), SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)).distinguish.
  inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).kg.
  inline*.
  wp.
  call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n, c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).
  proc.
  sp 1 1.
  if.
  by move=> &1 &2; rewrite /inv_cpa; smt().
  inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.
  inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc.
  sp 5 3.
  seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ p{1}.`1 = n{1} /\ p{2}.`1 = n{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ BNR.lenc{1} = BNR.lenc{2} /\ BNR.ndec{1} = BNR.ndec{2} /\ !(n{1} \in BNR.lenc{1}) /\ (forall nn ci, (nn, ci) \in SplitC2.I1.RO.m{1} => nn \in BNR.lenc{1}) /\ (forall nn ci, (nn, ci) \in SplitC2.I2.RO.m{1} => nn \in BNR.lenc{1}) /\ (forall nn ci, (nn, ci) \in SplitD.ROF.RO.m{1} => nn \in n{1} :: BNR.lenc{1})).
  exlim n{2}, SplitC2.I1.RO.m{1}, SplitC2.I2.RO.m{1} => n0 mr0 ms0; call (equ_cc n0 mr0 ms0).
  by move=> /> *.
  inline*; rcondt{1} 9; 1:(by auto; smt(C.ofintdK C.gt0_max_counter)); rcondt{1} 13; 1:(by auto; smt()); rcondt{1} 17; 1:(by auto; smt()).
  wp; rnd{1}; wp; rnd (fun (u:poly_out) => u + poly1305_eval r5{1} (topol a0{1} c3{1})) (fun (u:poly_out) => u - poly1305_eval r5{1} (topol a0{1} c3{1})); wp; rnd{1}; auto.
  rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_set_sameE oget_some mem_set).
  by auto.
  proc; inline*; auto; rewrite /inv_cpa /=; smt(get_setE mem_set).
  auto; rewrite /inv_cpa /=; smt(mem_empty).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-04_0913_step3

Run dir: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1`

t=0: `2026-06-04T16:13:23+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:04 | [think](./views/Tree_0_0/thinking/turn_001.md) | 4.1 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe byequiv=>// | probability / pr / probability, 1 goal, goal 287 chars | accepted probe |  |
| T0.0-2 | +00:22 | [13.7 s](./views/Tree_0_0/thinking/turn_002.md) | 309 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 287 chars | accepted commit |  |
| T0.0-3 | +00:41 | [19 s](./views/Tree_0_0/thinking/turn_003.md) |  | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | inspect proof_map | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | read-only inspect |  |
| T0.0-4 | +01:01 | [20 s](./views/Tree_0_0/thinking/turn_004.md) |  | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | inspect call_site_options | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | read-only inspect |  |
| T0.0-5 | +01:18 | [17.1 s](./views/Tree_0_0/thinking/turn_005.md) | 1.9 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | probe proc | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | accepted probe |  |
| T0.0-6 | +02:03 | [42.6 s](./views/Tree_0_0/thinking/turn_006.md) | 360 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | accepted commit |  |
| T0.0-7 | +02:56 | [52.8 s](./views/Tree_0_0/thinking/turn_007.md) | 2.2 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | probe inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO... | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted probe |  |
| T0.0-8 | +04:08 | [69.7 s](./views/Tree_0_0/thinking/turn_008.md) | 317 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | probe inline* | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted probe |  |
| T0.0-9 | +05:27 | [78.8 s](./views/Tree_0_0/thinking/turn_009.md) | 2.2 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit inline* | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted commit |  |
| T0.0-10 | +06:18 | [48.5 s](./views/Tree_0_0/thinking/turn_010.md) | 3.5 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | probe wp | pRHL / call_site / seq_cut, 1 goal, goal 3007 chars | accepted probe |  |
| T0.0-11 | +07:11 | [50 s](./views/Tree_0_0/thinking/turn_011.md) | 2 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 3007 chars | accepted commit |  |
| T0.0-12 | +07:24 | [10.8 s](./views/Tree_0_0/thinking/turn_012.md) | 183 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | inspect call_subgoals | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | read-only inspect |  |
| T0.0-13 | +07:39 | [14.8 s](./views/Tree_0_0/thinking/turn_013.md) | 174 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | inspect call_subgoals | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | read-only inspect |  |
| T0.0-14 | +07:55 | [15.7 s](./views/Tree_0_0/thinking/turn_014.md) | 329 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit call inv_cpa | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | accepted commit |  |
| T0.0-15 | +08:23 | [28.1 s](./views/Tree_0_0/thinking/turn_015.md) | 1.9 s | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | probe proc | equiv / prhl_module / relational_program, 3 goals, goal 1298 chars | accepted probe |  |
| T0.0-16 | +09:13 | [48.5 s](./views/Tree_0_0/thinking/turn_016.md) | 518 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 1298 chars | accepted commit |  |
| T0.0-17 | +09:35 | [21.2 s](./views/Tree_0_0/thinking/turn_017.md) | 1.8 s | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | probe sp; if | pRHL / call_site / relational_program, 3 goals, goal 2229 chars | accepted probe |  |
| T0.0-18 | +09:58 | [20.6 s](./views/Tree_0_0/thinking/turn_018.md) | 413 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit sp; if | pRHL / call_site / relational_program, 3 goals, goal 2229 chars | accepted commit |  |
| T0.0-19 | +10:23 | [25.1 s](./views/Tree_0_0/thinking/turn_019.md) | 1.9 s | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | probe move=> &1 &2; rewrite /inv_cpa; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 643 chars | accepted probe |  |
| T0.0-20 | +10:31 | [5.5 s](./views/Tree_0_0/thinking/turn_020.md) | 485 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit move=> &1 &2; rewrite /inv_cpa; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 643 chars | accepted commit |  |
| T0.0-21 | +11:12 | [41.1 s](./views/Tree_0_0/thinking/turn_021.md) | 1.9 s | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | probe inline{2} CPA_CCA_Orcls(EncRnd).enc | pRHL / call_site / relational_program, 4 goals, goal 1993 chars | accepted probe |  |
| T0.0-22 | +12:11 | [56.7 s](./views/Tree_0_0/thinking/turn_022.md) | 315 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | probe inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc | pRHL / call_site / relational_program, 4 goals, goal 1993 chars | accepted probe |  |
| T0.0-23 | +12:26 | [15.4 s](./views/Tree_0_0/thinking/turn_023.md) | 648 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc | pRHL / call_site / relational_program, 4 goals, goal 1993 chars | accepted commit |  |
| T0.0-24 | +12:45 | [17.8 s](./views/Tree_0_0/thinking/turn_024.md) | 2.2 s | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | probe inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(Sp... | pRHL / call_site / relational_program, 4 goals, goal 2622 chars | accepted probe |  |
| T0.0-25 | +13:50 | [62.5 s](./views/Tree_0_0/thinking/turn_025.md) | 476 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(Sp... | pRHL / call_site / relational_program, 4 goals, goal 2622 chars | accepted commit |  |
| T0.0-26 | +15:10 | [80.5 s](./views/Tree_0_0/thinking/turn_026.md) | 504 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit sp | pRHL / call_site / relational_program, 4 goals, goal 3531 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 |  | 4 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 287 chars | read-only inspect |  |
| T0.1-2 | +00:20 | 16.1 s | 929 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | probe byequiv=>// | probability / pr / probability, 1 goal, goal 287 chars | accepted probe |  |
| T0.1-3 | +00:27 | 5.6 s | 356 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 287 chars | accepted commit |  |
| T0.1-4 | +01:01 | 34 s |  | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | inspect call_site_options | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | read-only inspect |  |
| T0.1-5 | +01:46 | 45.2 s | 1.8 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | probe proc | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | accepted probe |  |
| T0.1-6 | +01:55 | 6.6 s | 394 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | accepted commit |  |
| T0.1-7 | +02:38 | 43.1 s | 1.9 s | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | probe inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO... | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted probe |  |
| T0.1-8 | +03:28 | 47.5 s | 482 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO... | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted commit |  |
| T0.1-9 | +03:34 | 5.6 s | 418 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit inline{1} G6(BNR_Adv(A), SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.R... | pRHL / call_site / relational_program, 1 goal, goal 1308 chars | accepted commit |  |
| T0.1-10 | +03:42 | 7.9 s | 2.1 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit inline{1} G4(BNR_Adv(A), SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pai... | pRHL / call_site / relational_program, 1 goal, goal 1688 chars | accepted commit |  |
| T0.1-11 | +08:06 | [262.4 s](./views/Tree_0_1/thinking/turn_011.md) | 3.6 s | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO... | pRHL / call_site / seq_cut, 1 goal, goal 2914 chars | accepted commit |  |
| T0.1-12 | +08:46 | 35.7 s | 300 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | probe inline* | pRHL / call_site / seq_cut, 1 goal, goal 2381 chars | accepted probe |  |
| T0.1-13 | +09:29 | 43 s | 2 s | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit inline* | pRHL / call_site / seq_cut, 1 goal, goal 2381 chars | accepted commit |  |
| T0.1-14 | +09:36 | 5.2 s | 1.8 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 3007 chars | accepted commit |  |
| T0.1-15 | +09:48 | 9.9 s | 134 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | inspect call_subgoals | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | read-only inspect |  |
| T0.1-16 | +10:07 | 18.7 s | 300 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit call inv_cpa | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | accepted commit |  |
| T0.1-17 | +11:11 | [63.6 s](./views/Tree_0_1/thinking/turn_017.md) | 428 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 1100 chars | accepted commit |  |
| T0.1-18 | +11:33 | 21.6 s | 405 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit sp 1 1 | pRHL / call_site / relational_program, 3 goals, goal 2027 chars | accepted commit |  |
| T0.1-19 | +11:45 | 11.6 s | 439 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit if | pRHL / call_site / relational_program, 3 goals, goal 1983 chars | accepted commit |  |
| T0.1-20 | +12:03 | 18.4 s | 594 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit by move=> &1 &2; rewrite /inv_cpa; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 540 chars | accepted commit |  |
| T0.1-21 | +13:03 | 59 s | 2 s | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | probe inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(Sp... | pRHL / call_site / relational_program, 4 goals, goal 1789 chars | accepted probe |  |
| T0.1-22 | +13:21 | 15.5 s | 485 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(Sp... | pRHL / call_site / relational_program, 4 goals, goal 1789 chars | accepted commit |  |
| T0.1-23 | +13:29 | 7.6 s | 442 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc | pRHL / call_site / relational_program, 4 goals, goal 3286 chars | accepted commit |  |
| T0.1-24 | +14:45 | 75.9 s | 1.1 s | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit sp 5 3 | pRHL / call_site / relational_program, 4 goals, goal 3321 chars | accepted commit |  |
| T0.1-25 | +15:35 | [49.5 s](./views/Tree_0_1/thinking/turn_025.md) | 516 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{... | pRHL / call_site / relational_program, 4 goals, goal 3097 chars | accepted commit |  |
| T0.1-26 | +15:51 | 14.6 s | 427 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit exlim n{2}, SplitC2.I1.RO.m{1}, SplitC2.I2.RO.m{1} => n0 mr0 ms0; call (equ_cc n0 mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2270 chars | accepted commit |  |
| T0.1-27 | +16:23 | 32 s | 5 s | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | probe by rewrite /inv_cpa /check_plaintext /valid_topol /=; smt() | pRHL / prhl_module / relational_program, 5 goals, goal 2476 chars | rejected probe: cannot prove goal (strict) |  |
| T0.1-28 | +17:10 | 41.6 s | 418 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | probe move=> /> * | pRHL / prhl_module / relational_program, 5 goals, goal 2476 chars | accepted probe |  |
| T0.1-29 | +18:06 | [56.4 s](./views/Tree_0_1/thinking/turn_029.md) | 552 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit by move=> /> * | pRHL / prhl_module / relational_program, 5 goals, goal 2476 chars | accepted commit |  |
| T0.1-30 | +19:05 | [57.9 s](./views/Tree_0_1/thinking/turn_030.md) | 2.1 s | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | probe inline*{1} | pRHL / call_site / relational_program, 4 goals, goal 2416 chars | rejected probe: parse error |  |
| T0.1-31 | +19:19 | 11.6 s | 389 ms | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | probe inline* | pRHL / call_site / relational_program, 4 goals, goal 2416 chars | accepted probe |  |
| T0.1-32 | +20:07 | [48.4 s](./views/Tree_0_1/thinking/turn_032.md) | 580 ms | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit inline* | pRHL / call_site / relational_program, 4 goals, goal 2416 chars | accepted commit |  |
| T0.1-33 | +20:24 | 15.7 s | 323 ms | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | commit rcondt{1} 9 | pRHL / procedure_body / relational_program, 4 goals, goal 5600 chars | accepted commit |  |
| T0.1-34 | +21:13 | 49 s | 2 s | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | probe by auto; smt(C.insubdK C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 836 chars | rejected probe: cannot find lemma `C.insubdK' |  |
| T0.1-35 | +22:02 | 47.5 s | 544 ms | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | probe by auto; smt(C.ofintdK C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 836 chars | accepted probe |  |
| T0.1-36 | +22:07 | [4.2 s](./views/Tree_0_1/thinking/turn_036.md) | 5.8 s | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | commit by auto; smt(C.ofintdK C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 836 chars | accepted commit |  |
| T0.1-37 | +23:19 | 66.3 s | 723 ms | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | probe rcondt{1} 13; 1: (by auto; smt()) | pRHL / procedure_body / seq_cut, 4 goals, goal 4620 chars | accepted probe |  |
| T0.1-38 | +23:30 | 9.5 s | 6.5 s | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | commit rcondt{1} 13; 1: (by auto; smt()) | pRHL / procedure_body / seq_cut, 4 goals, goal 4620 chars | accepted commit |  |
| T0.1-39 | +24:44 | [67.8 s](./views/Tree_0_1/thinking/turn_039.md) | 7.2 s | [turn_038.json](./views/Tree_0_1/turn_038.json) · [inline read](./views/Tree_0_1/followups/turn_038.md) | commit rcondt{1} 17; 1: (by auto; smt()) | pRHL / procedure_body / seq_cut, 4 goals, goal 4476 chars | accepted commit |  |
| T0.1-40 | +25:53 | [62 s](./views/Tree_0_1/thinking/turn_040.md) | 8 s | [turn_039.json](./views/Tree_0_1/turn_039.json) · [inline read](./views/Tree_0_1/followups/turn_039.md) | commit wp | pRHL / procedure_body / seq_cut, 4 goals, goal 4332 chars | accepted commit |  |
| T0.1-41 | +26:33 | [31.8 s](./views/Tree_0_1/thinking/turn_041.md) | 7.2 s | [turn_040.json](./views/Tree_0_1/turn_040.json) · [inline read](./views/Tree_0_1/followups/turn_040.md) | commit rnd{1}; wp | pRHL / procedure_body / seq_cut, 4 goals, goal 4031 chars | accepted commit |  |
| T0.1-42 | +27:22 | [41.6 s](./views/Tree_0_1/thinking/turn_042.md) | 431 ms | [turn_041.json](./views/Tree_0_1/turn_041.json) · [inline read](./views/Tree_0_1/followups/turn_041.md) | probe rnd (fun (u:poly_out) => u + poly1305_eval r5{1} (topol a0{1} c3{1}))... | pRHL / procedure_body / seq_cut, 4 goals, goal 3829 chars | accepted probe |  |
| T0.1-43 | +28:11 | [49.3 s](./views/Tree_0_1/thinking/turn_043.md) | 709 ms | [turn_042.json](./views/Tree_0_1/turn_042.json) · [inline read](./views/Tree_0_1/followups/turn_042.md) | commit rnd (fun (u:poly_out) => u + poly1305_eval r5{1} (topol a0{1} c3{1})) (fun (u:poly_out) => u... | pRHL / procedure_body / seq_cut, 4 goals, goal 3829 chars | accepted commit |  |
| T0.1-44 | +28:46 | [34.1 s](./views/Tree_0_1/thinking/turn_044.md) | 5.9 s | [turn_043.json](./views/Tree_0_1/turn_043.json) · [inline read](./views/Tree_0_1/followups/turn_043.md) | probe auto => /=; rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub... | pRHL / procedure_body / relational_program, 4 goals, goal 3984 chars | rejected probe: cannot prove goal (strict) |  |
| T0.1-45 | +29:20 | [28.4 s](./views/Tree_0_1/thinking/turn_045.md) | 613 ms | [turn_044.json](./views/Tree_0_1/turn_044.json) · [inline read](./views/Tree_0_1/followups/turn_044.md) | commit auto | pRHL / procedure_body / relational_program, 4 goals, goal 3984 chars | accepted commit |  |
| T0.1-46 | +30:34 | [72.9 s](./views/Tree_0_1/thinking/turn_046.md) | 3.1 s | [turn_045.json](./views/Tree_0_1/turn_045.json) · [inline read](./views/Tree_0_1/followups/turn_045.md) | probe move=> &1 &2 hpre r5_0 hr5; split; first by move=> tR _; smt(poly_out_sub_add) | ambient / ambient_logic / relational_program, 4 goals, goal 7313 chars | rejected probe: cannot apply `split/None` on that goal |  |
| T0.1-47 | +33:07 | 150 s |  | [turn_046.json](./views/Tree_0_1/turn_046.json) · [inline read](./views/Tree_0_1/followups/turn_046.md) | undo_to_checkpoint | ambient / ambient_logic / relational_program, 4 goals, goal 7313 chars | checkpoint choices requested |  |
| T0.1-48 | +34:41 | [94.1 s](./views/Tree_0_1/thinking/turn_048.md) | 15.9 s | [turn_047.json](./views/Tree_0_1/turn_047.json) · [inline read](./views/Tree_0_1/followups/turn_047.md) | undo_to_checkpoint | ambient / ambient_logic / relational_program, 4 goals, goal 7313 chars | checkpoint rewind selected |  |
| T0.1-49 | +35:11 | [13.6 s](./views/Tree_0_1/thinking/turn_049.md) | 449 ms | [turn_048.json](./views/Tree_0_1/turn_048.json) · [inline read](./views/Tree_0_1/followups/turn_048.md) | commit seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{... | pRHL / call_site / relational_program, 4 goals, goal 3097 chars | accepted commit |  |
| T0.1-50 | +35:18 | [6.6 s](./views/Tree_0_1/thinking/turn_050.md) | 391 ms | [turn_049.json](./views/Tree_0_1/turn_049.json) · [inline read](./views/Tree_0_1/followups/turn_049.md) | commit exlim n{2}, SplitC2.I1.RO.m{1}, SplitC2.I2.RO.m{1} => n0 mr0 ms0; call (equ_cc n0 mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2310 chars | accepted commit |  |
| T0.1-51 | +35:26 | 7.6 s | 443 ms | [turn_050.json](./views/Tree_0_1/turn_050.json) · [inline read](./views/Tree_0_1/followups/turn_050.md) | commit by move=> /> * | pRHL / prhl_module / relational_program, 5 goals, goal 2520 chars | accepted commit |  |
| T0.1-52 | +36:00 | [34.4 s](./views/Tree_0_1/thinking/turn_052.md) | 2.6 s | [turn_051.json](./views/Tree_0_1/turn_051.json) · [inline read](./views/Tree_0_1/followups/turn_051.md) | probe inline*; rcondt{1} 9; 1:(by auto; smt(C.ofintdK C.gt0_max_counter)); rcondt{1} 13; 1:(by auto... | pRHL / call_site / relational_program, 4 goals, goal 2456 chars | accepted probe |  |
| T0.1-53 | +36:11 | 8 s | 8 s | [turn_052.json](./views/Tree_0_1/turn_052.json) · [inline read](./views/Tree_0_1/followups/turn_052.md) | commit inline*; rcondt{1} 9; 1:(by auto; smt(C.ofintdK C.gt0_max_counter)); rcondt{1} 13; 1:(by auto... | pRHL / call_site / relational_program, 4 goals, goal 2456 chars | accepted commit |  |
| T0.1-54 | +36:30 | 11.5 s | 512 ms | [turn_053.json](./views/Tree_0_1/turn_053.json) · [inline read](./views/Tree_0_1/followups/turn_053.md) | commit wp; rnd{1}; wp; rnd (fun (u:poly_out) => u + poly1305_eval r5{1} (topol a0{1} c3{1})) (fun (u... | pRHL / procedure_body / seq_cut, 4 goals, goal 4372 chars | accepted commit |  |
| T0.1-55 | +36:53 | [22.3 s](./views/Tree_0_1/thinking/turn_055.md) | 2.7 s | [turn_054.json](./views/Tree_0_1/turn_054.json) · [inline read](./views/Tree_0_1/followups/turn_054.md) | probe rewrite /= !get_set_sameE /= !mk_rs_ofpair /= /poly1305 /inv_cpa /=; smt(poly_out_sub_add pol... | ambient / ambient_logic / relational_program, 4 goals, goal 7355 chars | rejected probe: nothing to rewrite |  |
| T0.1-56 | +37:52 | [56.2 s](./views/Tree_0_1/thinking/turn_056.md) | 809 ms | [turn_055.json](./views/Tree_0_1/turn_055.json) · [inline read](./views/Tree_0_1/followups/turn_055.md) | probe rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_set_sam... | ambient / ambient_logic / relational_program, 4 goals, goal 7355 chars | accepted probe |  |
| T0.1-57 | +38:11 | [18.1 s](./views/Tree_0_1/thinking/turn_057.md) | 852 ms | [turn_056.json](./views/Tree_0_1/turn_056.json) · [inline read](./views/Tree_0_1/followups/turn_056.md) | commit rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_set_sam... | ambient / ambient_logic / relational_program, 4 goals, goal 7355 chars | accepted commit |  |
| T0.1-58 | +38:46 | [33.6 s](./views/Tree_0_1/thinking/turn_058.md) | 375 ms | [turn_057.json](./views/Tree_0_1/turn_057.json) · [inline read](./views/Tree_0_1/followups/turn_057.md) | commit by auto | pRHL / verification_residue / relational_program, 3 goals, goal 878 chars | accepted commit |  |
| T0.1-59 | +39:18 | [32.4 s](./views/Tree_0_1/thinking/turn_059.md) | 3.6 s | [turn_058.json](./views/Tree_0_1/turn_058.json) · [inline read](./views/Tree_0_1/followups/turn_058.md) | probe proc; inline*; auto; rewrite /inv_cpa /=; smt(get_setE mem_set) | equiv / prhl_module / relational_program, 2 goals, goal 1102 chars | accepted probe |  |
| T0.1-60 | +39:29 | 7.3 s | 711 ms | [turn_059.json](./views/Tree_0_1/turn_059.json) · [inline read](./views/Tree_0_1/followups/turn_059.md) | commit proc; inline*; auto; rewrite /inv_cpa /=; smt(get_setE mem_set) | equiv / prhl_module / relational_program, 2 goals, goal 1102 chars | accepted commit |  |
| T0.1-61 | +40:04 | [33.7 s](./views/Tree_0_1/thinking/turn_061.md) | 3.3 s | [turn_060.json](./views/Tree_0_1/turn_060.json) · [inline read](./views/Tree_0_1/followups/turn_060.md) | probe auto; rewrite /inv_cpa /=; smt(mem_empty) | pRHL / procedure_body / relational_program, 1 goal, goal 1876 chars | accepted probe |  |
| T0.1-62 | +40:13 | [5.5 s](./views/Tree_0_1/thinking/turn_062.md) | 493 ms | [turn_061.json](./views/Tree_0_1/turn_061.json) · [inline read](./views/Tree_0_1/followups/turn_061.md) | commit auto; rewrite /inv_cpa /=; smt(mem_empty) | pRHL / procedure_body / relational_program, 1 goal, goal 1876 chars | accepted commit |  |
| T0.1-63 | +40:19 | [5.7 s](./views/Tree_0_1/thinking/turn_063.md) | 290 ms | [turn_062.json](./views/Tree_0_1/turn_062.json) · [inline read](./views/Tree_0_1/followups/turn_062.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
