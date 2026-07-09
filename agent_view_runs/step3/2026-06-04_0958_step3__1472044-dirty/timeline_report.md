# Agent-View Timeline — `step3`

| field | value |
|---|---|
| commit | `1472044` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-04_0958_step3 |
| lemma | `step3` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 4 |
| eval mode | True |
| outcome | proved |
| turns | 127 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 5 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv => //.
  proc.
  inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish.
  inline{1} G6(BNR_Adv(A), SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO)).distinguish.
  inline{1} G4(BNR_Adv(A), SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)).distinguish.
  (* proof not completed in this run *)
```

### `Tree_0_1` — incomplete — 27 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  wp.
  call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).
  proc.
  sp; if.
  rewrite /inv_cpa; smt().
  wp; inline{2} CPA_CCA_Orcls(EncRnd).enc; inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc; sp; wp; inline{2} EncRnd.enc; inline{1} RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc; inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.
  sp.
  seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ n{1} = p{1}.`1 /\ ! (p{1}.`1 \in BNR.lenc{1}) /\ inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall (n0 : nonce) (c3 : C.counter), (n0, c3) \in SplitD.ROF.RO.m{1} => n0 \in p{1}.`1 :: BNR.lenc{1})).
  exists* (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}).
  elim* => mr0 ms0.
  exists* (p{1}.`1); elim* => n0; call (equ_cc n0 mr0 ms0).
  move=> />.
  done.
  wp.
  inline{1} Poly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).mac.
  inline{1} CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)).cc.
  inline{1} SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO).get.
  rcondt{1} 9.
  move=> &m0.
  wp; skip.
  move=> &hr _.
  rewrite /SplitD.test /=.
  smt(C.ofintdK C.gt0_max_counter).
  inline{1} SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO).get.
  (* proof not completed in this run *)
```

### `Tree_0_1_0` — proved

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  wp.
  call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).
  proc.
  sp; if.
  rewrite /inv_cpa; smt().
  wp; inline{2} CPA_CCA_Orcls(EncRnd).enc; inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc; sp; wp; inline{2} EncRnd.enc; inline{1} RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc; inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.
  sp.
  seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ n{1} = p{1}.`1 /\ ! (p{1}.`1 \in BNR.lenc{1}) /\ inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall (n0 : nonce) (c3 : C.counter), (n0, c3) \in SplitD.ROF.RO.m{1} => n0 \in p{1}.`1 :: BNR.lenc{1}) /\ p{1} = p{2}).
  exists* (n{1}), (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}); elim* => n0 mr0 ms0; call (equ_cc n0 mr0 ms0); skip; move=> &1 &2; rewrite /check_plaintext /valid_topol /=; smt().
  wp; inline *.
  rcondt{1} 9; first by move=> &m0; wp; skip; rewrite /SplitD.test /=; smt(@C).
  rcondt{1} 13; first by move=> &m0; rnd; wp; skip => /=; rewrite /inv_cpa; smt().
  rcondt{1} 17; first by move=> &m0; rnd; wp; rnd; wp; skip => /=; rewrite /inv_cpa; smt().
  wp.
  rnd{1}.
  wp.
  rnd (fun (z : poly_out) => z + poly1305_eval r10{1} (topol a0{1} c3{1})) (fun (z : poly_out) => z - poly1305_eval r10{1} (topol a0{1} c3{1})).
  wp; rnd{1}; wp; skip.
  move=> &1 &2; rewrite /inv_cpa /poly1305 /=; smt(mk_rs_ofpair get_set_sameE get_setE mem_set domE poly_out_sub_add poly_out_add_sub).
  skip; smt().
  proc.
  inline *.
  sp.
  skip; rewrite /inv_cpa /=; smt(mem_set get_setE).
  auto.
  rewrite /inv_cpa /=; smt(mem_empty).
  qed.
```

### `Tree_0_1_1` — incomplete — 32 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  wp.
  call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).
  proc.
  sp; if.
  rewrite /inv_cpa; smt().
  wp; inline{2} CPA_CCA_Orcls(EncRnd).enc; inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc; sp; wp; inline{2} EncRnd.enc; inline{1} RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc; inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.
  sp.
  seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ n{1} = p{1}.`1 /\ ! (p{1}.`1 \in BNR.lenc{1}) /\ inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall (n0 : nonce) (c3 : C.counter), (n0, c3) \in SplitD.ROF.RO.m{1} => n0 \in p{1}.`1 :: BNR.lenc{1})).
  exists* (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}).
  elim* => mr0 ms0.
  exists* (p{1}.`1).
  elim* => n0.
  call (equ_cc n0 mr0 ms0).
  skip.
  move=> &1 &2; rewrite /check_plaintext /valid_topol /inv_cpa /=; smt().
  wp.
  inline{1}.
  sp.
  rcondt{1} 1.
  move=> &m0; skip; rewrite /SplitD.test /=; smt(@C).
  sp.
  wp.
  rnd{1}.
  rcondt{1} 2.
  move=> &m0; rnd; skip => /=; rewrite /inv_cpa; smt(@SmtMap).
  rcondt{1} 6.
  move=> &m0; rnd; wp; rnd; skip => /=; rewrite /inv_cpa; smt(@SmtMap).
  wp.
  rnd (fun (s0:poly_out) => s0 + poly1305_eval r10{1} (topol a0{1} c3{1})) (fun (t0:poly_out) => t0 - poly1305_eval r10{1} (topol a0{1} c3{1})).
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-04_0958_step3

Run dir: `artifacts/eval_suite/step3_l1_compare/l1_goal_projection/chacha_step3/r01/2026-06-04_0958_step3/iteration_1`

t=0: `2026-06-04T16:58:48.800000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 287 chars | accepted commit |  |
| T0.0-2 | +00:38 | [35.6 s](./views/Tree_0_0/thinking/turn_002.md) | 400 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | accepted commit |  |
| T0.0-3 | +01:21 | [42.5 s](./views/Tree_0_0/thinking/turn_003.md) | 474 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO... | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted commit |  |
| T0.0-4 | +01:28 | [6.6 s](./views/Tree_0_0/thinking/turn_004.md) | 372 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit inline{1} G6(BNR_Adv(A), SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.R... | pRHL / call_site / relational_program, 1 goal, goal 1308 chars | accepted commit |  |
| T0.0-5 | +01:36 | [7.9 s](./views/Tree_0_0/thinking/turn_005.md) | 2.1 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline{1} G4(BNR_Adv(A), SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pai... | pRHL / call_site / relational_program, 1 goal, goal 1688 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:14 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.9 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 287 chars | accepted commit |  |
| T0.1-2 | +01:43 | [87.1 s](./views/Tree_0_1/thinking/turn_002.md) | 1.9 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline Split1.IdealAll.MainD(G8(BNR_Adv(A)), SplitC2.RO_Pair(ROin, RO... | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | rejected commit: proof state unchanged |  |
| T0.1-3 | +01:50 | [5.2 s](./views/Tree_0_1/thinking/turn_003.md) | 1.8 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit inline * | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | rejected commit: proof state unchanged |  |
| T0.1-4 | +02:46 | [53.5 s](./views/Tree_0_1/thinking/turn_004.md) | 474 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 626 chars | accepted commit |  |
| T0.1-5 | +03:23 | [36.9 s](./views/Tree_0_1/thinking/turn_005.md) | 2.1 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 835 chars | accepted commit |  |
| T0.1-6 | +04:33 | [68 s](./views/Tree_0_1/thinking/turn_006.md) | 2 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 3007 chars | accepted commit |  |
| T0.1-7 | +04:58 | [22.6 s](./views/Tree_0_1/thinking/turn_007.md) | 368 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit call inv_cpa | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | accepted commit |  |
| T0.1-8 | +05:21 | [22.6 s](./views/Tree_0_1/thinking/turn_008.md) | 438 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 908 chars | accepted commit |  |
| T0.1-9 | +05:44 | [22.5 s](./views/Tree_0_1/thinking/turn_009.md) | 503 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit sp | pRHL / call_site / relational_program, 3 goals, goal 1831 chars | accepted commit |  |
| T0.1-10 | +05:55 | [10.5 s](./views/Tree_0_1/thinking/turn_010.md) | 498 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit if | pRHL / call_site / relational_program, 3 goals, goal 1787 chars | accepted commit |  |
| T0.1-11 | +06:28 | [32.4 s](./views/Tree_0_1/thinking/turn_011.md) | 565 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit rewrite /inv_cpa; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 434 chars | accepted commit |  |
| T0.1-12 | +07:49 | [80.5 s](./views/Tree_0_1/thinking/turn_012.md) | 490 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit wp | pRHL / call_site / relational_program, 4 goals, goal 1591 chars | accepted commit |  |
| T0.1-13 | +08:06 | [16.5 s](./views/Tree_0_1/thinking/turn_013.md) | 521 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit inline{2} CPA_CCA_Orcls(EncRnd).enc | pRHL / call_site / relational_program, 4 goals, goal 1544 chars | accepted commit |  |
| T0.1-14 | +08:18 | [11.6 s](./views/Tree_0_1/thinking/turn_014.md) | 442 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(Sp... | pRHL / call_site / relational_program, 4 goals, goal 1730 chars | accepted commit |  |
| T0.1-15 | +08:37 | [18.5 s](./views/Tree_0_1/thinking/turn_015.md) | 473 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit sp; wp | pRHL / call_site / relational_program, 4 goals, goal 1686 chars | accepted commit |  |
| T0.1-16 | +08:45 | [7.6 s](./views/Tree_0_1/thinking/turn_016.md) | 403 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit inline{2} EncRnd.enc | pRHL / call_site / relational_program, 4 goals, goal 1474 chars | accepted commit |  |
| T0.1-17 | +08:57 | [11.4 s](./views/Tree_0_1/thinking/turn_017.md) | 588 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit inline{1} RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(... | pRHL / call_site / relational_program, 4 goals, goal 1925 chars | accepted commit |  |
| T0.1-18 | +09:10 | [12.6 s](./views/Tree_0_1/thinking/turn_018.md) | 421 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO... | pRHL / call_site / relational_program, 4 goals, goal 1868 chars | accepted commit |  |
| T0.1-19 | +10:16 | 66 s |  | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | undo_to_checkpoint | pRHL / call_site / relational_program, 4 goals, goal 2790 chars | checkpoint choices requested |  |
| T0.1-20 | +10:46 | [30.1 s](./views/Tree_0_1/thinking/turn_020.md) | 7.9 s | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | undo_to_checkpoint | pRHL / call_site / relational_program, 4 goals, goal 2790 chars | checkpoint rewind selected |  |
| T0.1-21 | +11:05 | [10.7 s](./views/Tree_0_1/thinking/turn_021.md) | 288 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit call inv_cpa | pRHL / call_site / seq_cut, 1 goal, goal 2559 chars | accepted commit |  |
| T0.1-22 | +11:29 | [23.6 s](./views/Tree_0_1/thinking/turn_022.md) | 433 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 1100 chars | accepted commit |  |
| T0.1-23 | +11:38 | 8.6 s | 357 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit sp; if | pRHL / call_site / relational_program, 3 goals, goal 2027 chars | accepted commit |  |
| T0.1-24 | +11:42 | [3.5 s](./views/Tree_0_1/thinking/turn_024.md) | 534 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit rewrite /inv_cpa; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 540 chars | accepted commit |  |
| T0.1-25 | +11:54 | [11.5 s](./views/Tree_0_1/thinking/turn_025.md) | 462 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit wp; inline{2} CPA_CCA_Orcls(EncRnd).enc; inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO... | pRHL / call_site / relational_program, 4 goals, goal 1789 chars | accepted commit |  |
| T0.1-26 | +12:57 | [62.5 s](./views/Tree_0_1/thinking/turn_026.md) | 498 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit sp | pRHL / call_site / relational_program, 4 goals, goal 3013 chars | accepted commit |  |
| T0.1-27 | +14:08 | [70.5 s](./views/Tree_0_1/thinking/turn_027.md) | 468 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{... | pRHL / call_site / relational_program, 4 goals, goal 2873 chars | accepted commit |  |
| T0.1-28 | +14:25 | [16.7 s](./views/Tree_0_1/thinking/turn_028.md) | 2.3 s | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit call (equ_cc n{1} SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1}) | pRHL / call_site / relational_program, 5 goals, goal 2116 chars | rejected commit: proof state unchanged |  |
| T0.1-29 | +16:25 | [117.7 s](./views/Tree_0_1/thinking/turn_029.md) | 2.3 s | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit call (equ_cc (n{1}) (SplitC2.I1.RO.m{1}) (SplitC2.I2.RO.m{1})) | pRHL / call_site / failure_diagnostic, 5 goals, goal 2116 chars | rejected commit: proof state unchanged |  |
| T0.1-30 | +17:15 | [47.8 s](./views/Tree_0_1/thinking/turn_030.md) | 2.2 s | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit call (equ_cc _ _ _) | pRHL / call_site / failure_diagnostic, 5 goals, goal 2116 chars | rejected commit: proof state unchanged |  |
| T0.1-31 | +19:54 | [156.8 s](./views/Tree_0_1/thinking/turn_031.md) | 3.2 s | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit call (equ_cc (p{1}.`1) (SplitC2.I1.RO.m{1}) (SplitC2.I2.RO.m{1})) | pRHL / call_site / failure_diagnostic, 5 goals, goal 2116 chars | rejected commit: proof state unchanged |  |
| T0.1-32 | +22:09 | [131.8 s](./views/Tree_0_1/thinking/turn_032.md) | 3.2 s | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit exists* (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}); elim* => mr0 ms0; call (equ_cc (p{1}.`1)... | pRHL / call_site / failure_diagnostic, 5 goals, goal 2116 chars | rejected commit: proof state unchanged |  |
| T0.1-33 | +22:21 | [8.5 s](./views/Tree_0_1/thinking/turn_033.md) | 527 ms | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | commit exists* (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}) | pRHL / call_site / relational_program, 5 goals, goal 2116 chars | accepted commit |  |
| T0.1-34 | +22:32 | [10.5 s](./views/Tree_0_1/thinking/turn_034.md) | 492 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit elim* => mr0 ms0 | pRHL / call_site / relational_program, 5 goals, goal 2311 chars | accepted commit |  |
| T0.1-35 | +22:42 | [9.7 s](./views/Tree_0_1/thinking/turn_035.md) | 2.3 s | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit call (equ_cc _ mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2255 chars | rejected commit: proof state unchanged |  |
| T0.1-36 | +24:27 | [102.7 s](./views/Tree_0_1/thinking/turn_036.md) | 2.3 s | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | commit conseq (equ_cc (p{1}.`1) mr0 ms0) | pRHL / call_site / failure_diagnostic, 5 goals, goal 2255 chars | rejected commit: proof state unchanged |  |
| T0.1-37 | +25:44 | [74.4 s](./views/Tree_0_1/thinking/turn_037.md) | 2.6 s | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | commit call equ_cc | pRHL / call_site / relational_program, 5 goals, goal 2255 chars | rejected commit: proof state unchanged |  |
| T0.1-38 | +28:30 | [163.9 s](./views/Tree_0_1/thinking/turn_038.md) | 2.1 s | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | commit transitivity{1} { c2 <@ ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(ROin, ROout... | pRHL / call_site / failure_diagnostic, 5 goals, goal 2255 chars | rejected commit: proof state unchanged |  |
| T0.1-39 | +34:19 | [346.5 s](./views/Tree_0_1/thinking/turn_039.md) | 510 ms | [turn_038.json](./views/Tree_0_1/turn_038.json) · [inline read](./views/Tree_0_1/followups/turn_038.md) | commit inline{2} EncRnd.cc | pRHL / call_site / relational_program, 5 goals, goal 2255 chars | accepted commit |  |
| T0.1-40 | +35:40 | 81.2 s | 1.8 s | [turn_039.json](./views/Tree_0_1/turn_039.json) · [inline read](./views/Tree_0_1/followups/turn_039.md) | undo_last_step | pRHL / call_site / relational_program, 5 goals, goal 3648 chars | undo result |  |
| T0.1-41 | +36:44 | [61.9 s](./views/Tree_0_1/thinking/turn_041.md) | 2.1 s | [turn_040.json](./views/Tree_0_1/turn_040.json) · [inline read](./views/Tree_0_1/followups/turn_040.md) | commit call (equ_cc witness mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2242 chars | accepted commit |  |
| T0.1-42 | +37:04 | 18 s | 2 s | [turn_041.json](./views/Tree_0_1/turn_041.json) · [inline read](./views/Tree_0_1/followups/turn_041.md) | undo_last_step | pRHL / procedure_body / relational_program, 5 goals, goal 2303 chars | undo result |  |
| T0.1-43 | +37:24 | [17.8 s](./views/Tree_0_1/thinking/turn_043.md) | 2.2 s | [turn_042.json](./views/Tree_0_1/turn_042.json) · [inline read](./views/Tree_0_1/followups/turn_042.md) | commit exists* (p{1}.`1); elim* => n0; call (equ_cc n0 mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2242 chars | accepted commit |  |
| T0.1-44 | +38:13 | [46.9 s](./views/Tree_0_1/thinking/turn_044.md) | 5.1 s | [turn_043.json](./views/Tree_0_1/turn_043.json) · [inline read](./views/Tree_0_1/followups/turn_043.md) | commit rewrite /inv_cpa /check_plaintext /valid_topol; smt() | pRHL / procedure_body / relational_program, 5 goals, goal 2322 chars | rejected commit: proof state unchanged |  |
| T0.1-45 | +39:03 | [44.9 s](./views/Tree_0_1/thinking/turn_045.md) | 5.1 s | [turn_044.json](./views/Tree_0_1/turn_044.json) · [inline read](./views/Tree_0_1/followups/turn_044.md) | commit rewrite /check_plaintext /valid_topol; move=> />; smt() | pRHL / procedure_body / relational_program, 5 goals, goal 2322 chars | rejected commit: proof state unchanged |  |
| T0.1-46 | +39:17 | [8.4 s](./views/Tree_0_1/thinking/turn_046.md) | 596 ms | [turn_045.json](./views/Tree_0_1/turn_045.json) · [inline read](./views/Tree_0_1/followups/turn_045.md) | commit move=> /> | pRHL / procedure_body / relational_program, 5 goals, goal 2322 chars | accepted commit |  |
| T0.1-47 | +39:53 | [35.6 s](./views/Tree_0_1/thinking/turn_047.md) | 436 ms | [turn_046.json](./views/Tree_0_1/turn_046.json) · [inline read](./views/Tree_0_1/followups/turn_046.md) | commit done | pRHL / procedure_body / relational_program, 5 goals, goal 1260 chars | accepted commit |  |
| T0.1-48 | +40:58 | [64.6 s](./views/Tree_0_1/thinking/turn_048.md) | 410 ms | [turn_047.json](./views/Tree_0_1/turn_047.json) · [inline read](./views/Tree_0_1/followups/turn_047.md) | commit wp | pRHL / call_site / relational_program, 4 goals, goal 2074 chars | accepted commit |  |
| T0.1-49 | +41:17 | [18.6 s](./views/Tree_0_1/thinking/turn_049.md) | 418 ms | [turn_048.json](./views/Tree_0_1/turn_048.json) · [inline read](./views/Tree_0_1/followups/turn_048.md) | commit inline{1} Poly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(Spl... | pRHL / call_site / relational_program, 4 goals, goal 2010 chars | accepted commit |  |
| T0.1-50 | +41:26 | [8.6 s](./views/Tree_0_1/thinking/turn_050.md) | 402 ms | [turn_049.json](./views/Tree_0_1/turn_049.json) · [inline read](./views/Tree_0_1/followups/turn_049.md) | commit inline{1} CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.... | pRHL / call_site / relational_program, 4 goals, goal 2447 chars | accepted commit |  |
| T0.1-51 | +42:29 | [62.4 s](./views/Tree_0_1/thinking/turn_051.md) | 565 ms | [turn_050.json](./views/Tree_0_1/turn_050.json) · [inline read](./views/Tree_0_1/followups/turn_050.md) | commit inline{1} SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO... | pRHL / call_site / relational_program, 4 goals, goal 2725 chars | accepted commit |  |
| T0.1-52 | +42:51 | [21.7 s](./views/Tree_0_1/thinking/turn_052.md) | 337 ms | [turn_051.json](./views/Tree_0_1/turn_051.json) · [inline read](./views/Tree_0_1/followups/turn_051.md) | commit rcondt{1} 9 | pRHL / call_site / relational_program, 4 goals, goal 3086 chars | accepted commit |  |
| T0.1-53 | +43:27 | [35.7 s](./views/Tree_0_1/thinking/turn_053.md) | 5.3 s | [turn_052.json](./views/Tree_0_1/turn_052.json) · [inline read](./views/Tree_0_1/followups/turn_052.md) | commit auto=> />; rewrite /SplitD.test /=; smt(C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 651 chars | rejected commit: proof state unchanged |  |
| T0.1-54 | +43:43 | [10.7 s](./views/Tree_0_1/thinking/turn_054.md) | 315 ms | [turn_053.json](./views/Tree_0_1/turn_053.json) · [inline read](./views/Tree_0_1/followups/turn_053.md) | commit move=> &m0 | ambient / ambient_logic, 5 goals, goal 651 chars | accepted commit |  |
| T0.1-55 | +44:25 | [41.7 s](./views/Tree_0_1/thinking/turn_055.md) | 301 ms | [turn_054.json](./views/Tree_0_1/turn_054.json) · [inline read](./views/Tree_0_1/followups/turn_054.md) | commit wp; skip | hoare / procedure_body / procedure_frontier, 5 goals, goal 1286 chars | accepted commit |  |
| T0.1-56 | +44:48 | [22.8 s](./views/Tree_0_1/thinking/turn_056.md) | 5.2 s | [turn_055.json](./views/Tree_0_1/turn_055.json) · [inline read](./views/Tree_0_1/followups/turn_055.md) | commit move=> &hr _; rewrite /SplitD.test /=; smt(C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 798 chars | rejected commit: proof state unchanged |  |
| T0.1-57 | +45:07 | [14.1 s](./views/Tree_0_1/thinking/turn_057.md) | 946 ms | [turn_056.json](./views/Tree_0_1/turn_056.json) · [inline read](./views/Tree_0_1/followups/turn_056.md) | commit move=> &hr _ | ambient / ambient_logic, 5 goals, goal 798 chars | accepted commit |  |
| T0.1-58 | +45:13 | [4.7 s](./views/Tree_0_1/thinking/turn_058.md) | 268 ms | [turn_057.json](./views/Tree_0_1/turn_057.json) · [inline read](./views/Tree_0_1/followups/turn_057.md) | commit rewrite /SplitD.test /= | ambient / ambient_logic, 5 goals, goal 648 chars | accepted commit |  |
| T0.1-59 | +45:56 | [42.9 s](./views/Tree_0_1/thinking/turn_059.md) | 2.1 s | [turn_058.json](./views/Tree_0_1/turn_058.json) · [inline read](./views/Tree_0_1/followups/turn_058.md) | commit smt(C.insubdK C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 641 chars | rejected commit: proof state unchanged |  |
| T0.1-60 | +46:17 | [18.5 s](./views/Tree_0_1/thinking/turn_060.md) | 545 ms | [turn_059.json](./views/Tree_0_1/turn_059.json) · [inline read](./views/Tree_0_1/followups/turn_059.md) | commit smt(C.ofintdK C.gt0_max_counter) | ambient / ambient_logic, 5 goals, goal 641 chars | accepted commit |  |
| T0.1-61 | +46:31 | [13.6 s](./views/Tree_0_1/thinking/turn_061.md) | 409 ms | [turn_060.json](./views/Tree_0_1/turn_060.json) · [inline read](./views/Tree_0_1/followups/turn_060.md) | commit inline{1} SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.R... | pRHL / call_site / relational_program, 4 goals, goal 2718 chars | accepted commit |  |

### Tree-0.1.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1.0-1 | +22:49 | [think](./views/Tree_0_1_0/thinking/turn_001.md) | 428 ms | [manager_bootstrap_0_1_0.json](./views/_bootstrap/manager_bootstrap_0_1_0.json) | commit exists* (n{1}), (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}) | pRHL / call_site / relational_program, 5 goals, goal 2116 chars | accepted commit |  |
| T0.1.0-2 | +22:54 | [4.3 s](./views/Tree_0_1_0/thinking/turn_002.md) | 662 ms | [turn_001.json](./views/Tree_0_1_0/turn_001.json) · [inline read](./views/Tree_0_1_0/followups/turn_001.md) | commit elim* => n0 mr0 ms0 | pRHL / call_site / relational_program, 5 goals, goal 2339 chars | accepted commit |  |
| T0.1.0-3 | +23:00 | [5.6 s](./views/Tree_0_1_0/thinking/turn_003.md) | 433 ms | [turn_002.json](./views/Tree_0_1_0/turn_002.json) · [inline read](./views/Tree_0_1_0/followups/turn_002.md) | commit call (equ_cc n0 mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2284 chars | accepted commit |  |
| T0.1.0-4 | +23:34 | [33.6 s](./views/Tree_0_1_0/thinking/turn_004.md) | 439 ms | [turn_003.json](./views/Tree_0_1_0/turn_003.json) · [inline read](./views/Tree_0_1_0/followups/turn_003.md) | commit skip | pRHL / procedure_body / relational_program, 5 goals, goal 2317 chars | accepted commit |  |
| T0.1.0-5 | +24:42 | [68.3 s](./views/Tree_0_1_0/thinking/turn_005.md) | 748 ms | [turn_004.json](./views/Tree_0_1_0/turn_004.json) · [inline read](./views/Tree_0_1_0/followups/turn_004.md) | commit move=> &1 &2; rewrite /check_plaintext /valid_topol /=; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 1922 chars | accepted commit |  |
| T0.1.0-6 | +25:28 | [44.5 s](./views/Tree_0_1_0/thinking/turn_006.md) | 537 ms | [turn_005.json](./views/Tree_0_1_0/turn_005.json) · [inline read](./views/Tree_0_1_0/followups/turn_005.md) | commit wp | pRHL / call_site / relational_program, 4 goals, goal 2074 chars | accepted commit |  |
| T0.1.0-7 | +26:08 | [39.4 s](./views/Tree_0_1_0/thinking/turn_007.md) | 632 ms | [turn_006.json](./views/Tree_0_1_0/turn_006.json) · [inline read](./views/Tree_0_1_0/followups/turn_006.md) | commit inline * | pRHL / call_site / relational_program, 4 goals, goal 2010 chars | accepted commit |  |
| T0.1.0-8 | +27:11 | [62.6 s](./views/Tree_0_1_0/thinking/turn_008.md) | 425 ms | [turn_007.json](./views/Tree_0_1_0/turn_007.json) · [inline read](./views/Tree_0_1_0/followups/turn_007.md) | commit rcondt{1} 9 | pRHL / procedure_body / relational_program, 4 goals, goal 5047 chars | accepted commit |  |
| T0.1.0-9 | +27:47 | [36 s](./views/Tree_0_1_0/thinking/turn_009.md) | 8 s | [turn_008.json](./views/Tree_0_1_0/turn_008.json) · [inline read](./views/Tree_0_1_0/followups/turn_008.md) | commit move=> &m0; wp; skip; rewrite /SplitD.test /=; smt(@C) | ambient / ambient_logic, 5 goals, goal 651 chars | accepted commit |  |
| T0.1.0-10 | +28:27 | [31.6 s](./views/Tree_0_1_0/thinking/turn_010.md) | 411 ms | [turn_009.json](./views/Tree_0_1_0/turn_009.json) · [inline read](./views/Tree_0_1_0/followups/turn_009.md) | commit rcondt{1} 13 | pRHL / procedure_body / seq_cut, 4 goals, goal 4132 chars | accepted commit |  |
| T0.1.0-11 | +28:34 | [6.6 s](./views/Tree_0_1_0/thinking/turn_011.md) | 8.4 s | [turn_010.json](./views/Tree_0_1_0/turn_010.json) · [inline read](./views/Tree_0_1_0/followups/turn_010.md) | commit move=> &m0; rnd; wp; skip => /=; rewrite /inv_cpa; smt() | ambient / ambient_logic, 5 goals, goal 665 chars | accepted commit |  |
| T0.1.0-12 | +28:55 | [12.6 s](./views/Tree_0_1_0/thinking/turn_012.md) | 405 ms | [turn_011.json](./views/Tree_0_1_0/turn_011.json) · [inline read](./views/Tree_0_1_0/followups/turn_011.md) | commit rcondt{1} 17 | pRHL / procedure_body / seq_cut, 4 goals, goal 3996 chars | accepted commit |  |
| T0.1.0-13 | +29:02 | 7.2 s | 7.8 s | [turn_012.json](./views/Tree_0_1_0/turn_012.json) · [inline read](./views/Tree_0_1_0/followups/turn_012.md) | commit move=> &m0; rnd; wp; rnd; wp; skip => /=; rewrite /inv_cpa; smt() | ambient / ambient_logic, 5 goals, goal 666 chars | accepted commit |  |
| T0.1.0-14 | +31:10 | [119.4 s](./views/Tree_0_1_0/thinking/turn_014.md) | 7.6 s | [turn_013.json](./views/Tree_0_1_0/turn_013.json) · [inline read](./views/Tree_0_1_0/followups/turn_013.md) | commit wp | pRHL / procedure_body / seq_cut, 4 goals, goal 3860 chars | accepted commit |  |
| T0.1.0-15 | +34:02 | 165 s |  | [turn_014.json](./views/Tree_0_1_0/turn_014.json) · [inline read](./views/Tree_0_1_0/followups/turn_014.md) | undo_to_checkpoint | pRHL / procedure_body / seq_cut, 4 goals, goal 3940 chars | checkpoint choices requested |  |
| T0.1.0-16 | +35:05 | [63 s](./views/Tree_0_1_0/thinking/turn_016.md) |  | [turn_015.json](./views/Tree_0_1_0/turn_015.json) · [inline read](./views/Tree_0_1_0/followups/turn_015.md) | undo_to_checkpoint | pRHL / procedure_body / seq_cut, 4 goals, goal 3940 chars | checkpoint rewind selected |  |
| T0.1.0-17 | +35:25 | [20.2 s](./views/Tree_0_1_0/thinking/turn_017.md) | 9.8 s | [turn_016.json](./views/Tree_0_1_0/turn_016.json) · [inline read](./views/Tree_0_1_0/followups/turn_016.md) | undo_to_checkpoint | pRHL / procedure_body / seq_cut, 4 goals, goal 3940 chars | checkpoint rewind selected |  |
| T0.1.0-18 | +35:53 | [17.5 s](./views/Tree_0_1_0/thinking/turn_018.md) | 521 ms | [turn_017.json](./views/Tree_0_1_0/turn_017.json) · [inline read](./views/Tree_0_1_0/followups/turn_017.md) | commit seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{... | pRHL / call_site / relational_program, 4 goals, goal 2873 chars | accepted commit |  |
| T0.1.0-19 | +36:10 | [16.4 s](./views/Tree_0_1_0/thinking/turn_019.md) | 587 ms | [turn_018.json](./views/Tree_0_1_0/turn_018.json) · [inline read](./views/Tree_0_1_0/followups/turn_018.md) | commit exists* (n{1}), (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}); elim* => n0 mr0 ms0; call (equ_cc... | pRHL / call_site / relational_program, 5 goals, goal 2136 chars | accepted commit |  |
| T0.1.0-20 | +36:35 | [24.5 s](./views/Tree_0_1_0/thinking/turn_020.md) | 503 ms | [turn_019.json](./views/Tree_0_1_0/turn_019.json) · [inline read](./views/Tree_0_1_0/followups/turn_019.md) | commit wp; inline * | pRHL / call_site / relational_program, 4 goals, goal 2094 chars | accepted commit |  |
| T0.1.0-21 | +36:42 | [6.7 s](./views/Tree_0_1_0/thinking/turn_021.md) | 6.3 s | [turn_020.json](./views/Tree_0_1_0/turn_020.json) · [inline read](./views/Tree_0_1_0/followups/turn_020.md) | commit rcondt{1} 9; first by move=> &m0; wp; skip; rewrite /SplitD.test /=; smt(@C) | pRHL / procedure_body / relational_program, 4 goals, goal 5067 chars | accepted commit |  |
| T0.1.0-22 | +36:53 | [5 s](./views/Tree_0_1_0/thinking/turn_022.md) | 7 s | [turn_021.json](./views/Tree_0_1_0/turn_021.json) · [inline read](./views/Tree_0_1_0/followups/turn_021.md) | commit rcondt{1} 13; first by move=> &m0; rnd; wp; skip => /=; rewrite /inv_cpa; smt() | pRHL / procedure_body / seq_cut, 4 goals, goal 4152 chars | accepted commit |  |
| T0.1.0-23 | +37:04 | [3.4 s](./views/Tree_0_1_0/thinking/turn_023.md) | 7.6 s | [turn_022.json](./views/Tree_0_1_0/turn_022.json) · [inline read](./views/Tree_0_1_0/followups/turn_022.md) | commit rcondt{1} 17; first by move=> &m0; rnd; wp; rnd; wp; skip => /=; rewrite /inv_cpa; smt() | pRHL / procedure_body / seq_cut, 4 goals, goal 4016 chars | accepted commit |  |
| T0.1.0-24 | +38:22 | [71.1 s](./views/Tree_0_1_0/thinking/turn_024.md) | 7.9 s | [turn_023.json](./views/Tree_0_1_0/turn_023.json) · [inline read](./views/Tree_0_1_0/followups/turn_023.md) | commit wp | pRHL / procedure_body / seq_cut, 4 goals, goal 3880 chars | accepted commit |  |
| T0.1.0-25 | +38:42 | [11.9 s](./views/Tree_0_1_0/thinking/turn_025.md) | 7.1 s | [turn_024.json](./views/Tree_0_1_0/turn_024.json) · [inline read](./views/Tree_0_1_0/followups/turn_024.md) | commit rnd{1} | pRHL / procedure_body / seq_cut, 4 goals, goal 3960 chars | accepted commit |  |
| T0.1.0-26 | +38:56 | [6.9 s](./views/Tree_0_1_0/thinking/turn_026.md) | 7.1 s | [turn_025.json](./views/Tree_0_1_0/turn_025.json) · [inline read](./views/Tree_0_1_0/followups/turn_025.md) | commit wp | pRHL / procedure_body / seq_cut, 4 goals, goal 4011 chars | accepted commit |  |
| T0.1.0-27 | +39:29 | [25.4 s](./views/Tree_0_1_0/thinking/turn_027.md) | 558 ms | [turn_026.json](./views/Tree_0_1_0/turn_026.json) · [inline read](./views/Tree_0_1_0/followups/turn_026.md) | commit rnd (fun (z : poly_out) => z + poly1305_eval r10{1} (topol a0{1} c3{1... | pRHL / procedure_body / seq_cut, 4 goals, goal 3756 chars | accepted commit |  |
| T0.1.0-28 | +39:57 | [27.6 s](./views/Tree_0_1_0/thinking/turn_028.md) | 400 ms | [turn_027.json](./views/Tree_0_1_0/turn_027.json) · [inline read](./views/Tree_0_1_0/followups/turn_027.md) | commit wp; rnd{1}; wp; skip | pRHL / procedure_body / relational_program, 4 goals, goal 4142 chars | accepted commit |  |
| T0.1.0-29 | +41:15 | [78.1 s](./views/Tree_0_1_0/thinking/turn_029.md) | 925 ms | [turn_028.json](./views/Tree_0_1_0/turn_028.json) · [inline read](./views/Tree_0_1_0/followups/turn_028.md) | commit move=> &1 &2; rewrite /inv_cpa /poly1305 /=; smt(mk_rs_ofpair get_set_sameE get_setE mem_set... | ambient / ambient_logic / relational_program, 4 goals, goal 2661 chars | accepted commit |  |
| T0.1.0-30 | +41:52 | [35.5 s](./views/Tree_0_1_0/thinking/turn_030.md) | 498 ms | [turn_029.json](./views/Tree_0_1_0/turn_029.json) · [inline read](./views/Tree_0_1_0/followups/turn_029.md) | commit skip; smt() | pRHL / verification_residue / relational_program, 3 goals, goal 878 chars | accepted commit |  |
| T0.1.0-31 | +42:39 | [46.6 s](./views/Tree_0_1_0/thinking/turn_031.md) | 431 ms | [turn_030.json](./views/Tree_0_1_0/turn_030.json) · [inline read](./views/Tree_0_1_0/followups/turn_030.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 1102 chars | accepted commit |  |
| T0.1.0-32 | +43:12 | [32.5 s](./views/Tree_0_1_0/thinking/turn_032.md) | 458 ms | [turn_031.json](./views/Tree_0_1_0/turn_031.json) · [inline read](./views/Tree_0_1_0/followups/turn_031.md) | commit inline * | pRHL / call_site / relational_program, 2 goals, goal 2041 chars | accepted commit |  |
| T0.1.0-33 | +44:15 | [62.7 s](./views/Tree_0_1_0/thinking/turn_033.md) | 3.3 s | [turn_032.json](./views/Tree_0_1_0/turn_032.json) · [inline read](./views/Tree_0_1_0/followups/turn_032.md) | commit rewrite /inv_cpa; sp; if; auto; smt(mem_set get_setE) | pRHL / verification_residue / relational_program, 2 goals, goal 1281 chars | rejected commit: proof state unchanged |  |
| T0.1.0-34 | +44:43 | [24.5 s](./views/Tree_0_1_0/thinking/turn_034.md) | 478 ms | [turn_033.json](./views/Tree_0_1_0/turn_033.json) · [inline read](./views/Tree_0_1_0/followups/turn_033.md) | commit sp | pRHL / verification_residue / relational_program, 2 goals, goal 1281 chars | accepted commit |  |
| T0.1.0-35 | +45:09 | [25.4 s](./views/Tree_0_1_0/thinking/turn_035.md) | 574 ms | [turn_034.json](./views/Tree_0_1_0/turn_034.json) · [inline read](./views/Tree_0_1_0/followups/turn_034.md) | commit skip; rewrite /inv_cpa /=; smt(mem_set get_setE) | pRHL / verification_residue / relational_program, 2 goals, goal 2701 chars | accepted commit |  |
| T0.1.0-36 | +45:58 | [48.6 s](./views/Tree_0_1_0/thinking/turn_036.md) | 3.4 s | [turn_035.json](./views/Tree_0_1_0/turn_035.json) · [inline read](./views/Tree_0_1_0/followups/turn_035.md) | commit wp; rnd{1}; wp; skip; rewrite /inv_cpa /=; smt(mem_empty in_emptyE emptyE) | pRHL / procedure_body / relational_program, 1 goal, goal 1876 chars | rejected commit: proof state unchanged |  |
| T0.1.0-37 | +46:12 | [10.6 s](./views/Tree_0_1_0/thinking/turn_037.md) | 423 ms | [turn_036.json](./views/Tree_0_1_0/turn_036.json) · [inline read](./views/Tree_0_1_0/followups/turn_036.md) | commit auto | pRHL / procedure_body / relational_program, 1 goal, goal 1876 chars | accepted commit |  |
| T0.1.0-38 | +46:34 | [21.4 s](./views/Tree_0_1_0/thinking/turn_038.md) | 578 ms | [turn_037.json](./views/Tree_0_1_0/turn_037.json) · [inline read](./views/Tree_0_1_0/followups/turn_037.md) | commit rewrite /inv_cpa /=; smt(mem_empty) | ambient / ambient_logic / relational_program, 1 goal, goal 1072 chars | accepted commit |  |
| T0.1.0-39 | +46:37 | [2.7 s](./views/Tree_0_1_0/thinking/turn_039.md) | 252 ms | [turn_038.json](./views/Tree_0_1_0/turn_038.json) · [inline read](./views/Tree_0_1_0/followups/turn_038.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1.0-40 | +46:45 | 8 s |  | [turn_039.json](./views/Tree_0_1_0/turn_039.json) · [inline read](./views/Tree_0_1_0/followups/turn_039.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |

### Tree-0.1.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1.1-1 | +31:04 | [think](./views/Tree_0_1_1/thinking/turn_001.md) | 2.6 s | [manager_bootstrap_0_1_1.json](./views/_bootstrap/manager_bootstrap_0_1_1.json) | commit call (equ_cc (p{1}.`1) mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2255 chars | rejected commit: proof state unchanged |  |
| T0.1.1-2 | +33:50 | [163.4 s](./views/Tree_0_1_1/thinking/turn_002.md) | 553 ms | [turn_001.json](./views/Tree_0_1_1/turn_001.json) · [inline read](./views/Tree_0_1_1/followups/turn_001.md) | commit exists* (p{1}.`1) | pRHL / call_site / failure_diagnostic, 5 goals, goal 2255 chars | accepted commit |  |
| T0.1.1-3 | +33:55 | [4.6 s](./views/Tree_0_1_1/thinking/turn_003.md) | 396 ms | [turn_002.json](./views/Tree_0_1_1/turn_002.json) · [inline read](./views/Tree_0_1_1/followups/turn_002.md) | commit elim* => n0 | pRHL / call_site / relational_program, 5 goals, goal 2330 chars | accepted commit |  |
| T0.1.1-4 | +34:00 | [4.6 s](./views/Tree_0_1_1/thinking/turn_004.md) | 362 ms | [turn_003.json](./views/Tree_0_1_1/turn_003.json) · [inline read](./views/Tree_0_1_1/followups/turn_003.md) | commit call (equ_cc n0 mr0 ms0) | pRHL / call_site / relational_program, 5 goals, goal 2289 chars | accepted commit |  |
| T0.1.1-5 | +34:51 | [50.5 s](./views/Tree_0_1_1/thinking/turn_005.md) | 458 ms | [turn_004.json](./views/Tree_0_1_1/turn_004.json) · [inline read](./views/Tree_0_1_1/followups/turn_004.md) | commit skip | pRHL / procedure_body / relational_program, 5 goals, goal 2322 chars | accepted commit |  |
| T0.1.1-6 | +35:11 | [19.4 s](./views/Tree_0_1_1/thinking/turn_006.md) | 639 ms | [turn_005.json](./views/Tree_0_1_1/turn_005.json) · [inline read](./views/Tree_0_1_1/followups/turn_005.md) | commit move=> &1 &2; rewrite /check_plaintext /valid_topol /inv_cpa /=; smt() | ambient / ambient_logic / relational_program, 5 goals, goal 1927 chars | accepted commit |  |
| T0.1.1-7 | +35:59 | [47.6 s](./views/Tree_0_1_1/thinking/turn_007.md) | 401 ms | [turn_006.json](./views/Tree_0_1_1/turn_006.json) · [inline read](./views/Tree_0_1_1/followups/turn_006.md) | commit wp | pRHL / call_site / relational_program, 4 goals, goal 2074 chars | accepted commit |  |
| T0.1.1-8 | +36:44 | [44.5 s](./views/Tree_0_1_1/thinking/turn_008.md) | 485 ms | [turn_007.json](./views/Tree_0_1_1/turn_007.json) · [inline read](./views/Tree_0_1_1/followups/turn_007.md) | commit inline{1} | pRHL / call_site / relational_program, 4 goals, goal 2010 chars | accepted commit |  |
| T0.1.1-9 | +37:02 | [17.6 s](./views/Tree_0_1_1/thinking/turn_009.md) | 445 ms | [turn_008.json](./views/Tree_0_1_1/turn_008.json) · [inline read](./views/Tree_0_1_1/followups/turn_008.md) | commit sp | pRHL / procedure_body / relational_program, 4 goals, goal 5047 chars | accepted commit |  |
| T0.1.1-10 | +37:18 | [15.7 s](./views/Tree_0_1_1/thinking/turn_010.md) | 295 ms | [turn_009.json](./views/Tree_0_1_1/turn_009.json) · [inline read](./views/Tree_0_1_1/followups/turn_009.md) | commit rcondt{1} 1 | pRHL / procedure_body / relational_program, 4 goals, goal 4586 chars | accepted commit |  |
| T0.1.1-11 | +37:38 | [19.5 s](./views/Tree_0_1_1/thinking/turn_011.md) | 6.5 s | [turn_010.json](./views/Tree_0_1_1/turn_010.json) · [inline read](./views/Tree_0_1_1/followups/turn_010.md) | commit move=> &m0; skip; rewrite /SplitD.test /=; smt(@C) | ambient / ambient_logic, 5 goals, goal 808 chars | accepted commit |  |
| T0.1.1-12 | +38:52 | [68 s](./views/Tree_0_1_1/thinking/turn_012.md) | 6 s | [turn_011.json](./views/Tree_0_1_1/turn_011.json) · [inline read](./views/Tree_0_1_1/followups/turn_011.md) | commit sp | pRHL / procedure_body / seq_cut, 4 goals, goal 3750 chars | accepted commit |  |
| T0.1.1-13 | +39:39 | [40.7 s](./views/Tree_0_1_1/thinking/turn_013.md) | 8.3 s | [turn_012.json](./views/Tree_0_1_1/turn_012.json) · [inline read](./views/Tree_0_1_1/followups/turn_012.md) | commit rnd{1} | pRHL / procedure_body / seq_cut, 4 goals, goal 3602 chars | rejected commit: proof state unchanged |  |
| T0.1.1-14 | +40:54 | [66.7 s](./views/Tree_0_1_1/thinking/turn_014.md) | 6.3 s | [turn_013.json](./views/Tree_0_1_1/turn_013.json) · [inline read](./views/Tree_0_1_1/followups/turn_013.md) | commit wp | pRHL / procedure_body / seq_cut, 4 goals, goal 3602 chars | accepted commit |  |
| T0.1.1-15 | +41:29 | [28.6 s](./views/Tree_0_1_1/thinking/turn_015.md) | 6.4 s | [turn_014.json](./views/Tree_0_1_1/turn_014.json) · [inline read](./views/Tree_0_1_1/followups/turn_014.md) | commit rnd{1} | pRHL / procedure_body / seq_cut, 4 goals, goal 3728 chars | accepted commit |  |
| T0.1.1-16 | +43:34 | [118.7 s](./views/Tree_0_1_1/thinking/turn_016.md) | 262 ms | [turn_015.json](./views/Tree_0_1_1/turn_015.json) · [inline read](./views/Tree_0_1_1/followups/turn_015.md) | commit rcondt{1} 2 | pRHL / procedure_body / seq_cut, 4 goals, goal 3762 chars | accepted commit |  |
| T0.1.1-17 | +44:21 | [46.7 s](./views/Tree_0_1_1/thinking/turn_017.md) | 7.3 s | [turn_016.json](./views/Tree_0_1_1/turn_016.json) · [inline read](./views/Tree_0_1_1/followups/turn_016.md) | commit move=> &m0; rnd; skip => /=; rewrite /inv_cpa; smt(@SmtMap) | ambient / ambient_logic, 5 goals, goal 891 chars | accepted commit |  |
| T0.1.1-18 | +44:53 | [24.7 s](./views/Tree_0_1_1/thinking/turn_018.md) | 289 ms | [turn_017.json](./views/Tree_0_1_1/turn_017.json) · [inline read](./views/Tree_0_1_1/followups/turn_017.md) | commit rcondt{1} 6 | pRHL / procedure_body / seq_cut, 4 goals, goal 3628 chars | accepted commit |  |
| T0.1.1-19 | +45:02 | [8.3 s](./views/Tree_0_1_1/thinking/turn_019.md) | 9.7 s | [turn_018.json](./views/Tree_0_1_1/turn_018.json) · [inline read](./views/Tree_0_1_1/followups/turn_018.md) | commit move=> &m0; rnd; wp; rnd; skip => /=; rewrite /inv_cpa; smt(@SmtMap) | ambient / ambient_logic, 5 goals, goal 914 chars | accepted commit |  |
| T0.1.1-20 | +45:40 | [28.6 s](./views/Tree_0_1_1/thinking/turn_020.md) | 8.4 s | [turn_019.json](./views/Tree_0_1_1/turn_019.json) · [inline read](./views/Tree_0_1_1/followups/turn_019.md) | commit wp | pRHL / procedure_body / seq_cut, 4 goals, goal 3472 chars | accepted commit |  |
| T0.1.1-21 | +46:27 | [38.5 s](./views/Tree_0_1_1/thinking/turn_021.md) | 458 ms | [turn_020.json](./views/Tree_0_1_1/turn_020.json) · [inline read](./views/Tree_0_1_1/followups/turn_020.md) | commit rnd (fun (s0:poly_out) => s0 + poly1305_eval r10{1} (topol a0{1} c3{1... | pRHL / procedure_body / seq_cut, 4 goals, goal 3222 chars | accepted commit |  |
