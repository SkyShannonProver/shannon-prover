# Agent-View Timeline — `step2_2`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1355_step2_2 |
| lemma | `step2_2` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 60 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  have h1 : Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] = Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res].
  byequiv UFCMA_genCC => //.
  have h2 : Pr[UFCMA(A, St).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec StLSke.gs Mem.k c <> None] <= Pr[UFCMA_poly(A, FinRO).main() @ &m : res].
  have ha : Pr[UFCMA(A, St).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec StLSke.gs Mem.k c <> None] = Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : exists (c : ciphertext), (c \in Mem.lc) /\ dec RO.m Mem.k c <> None].
  byequiv UFCMA_genCC => //.
  have dec_kindep : forall gs (k1 k2 : key) (c : ciphertext), (dec gs k1 c <> None) <=> (dec gs k2 c <> None).
  move=> gs k1 k2 [n a cph t]; rewrite /dec /genpoly1305 /get /=; smt().
  move=> &1 &2 [[_ ->] ->].
  smt().
  rewrite ha.
  byequiv (_: ={glob A} ==> (exists (c : ciphertext), (c \in Mem.lc) /\ dec RO.m Mem.k c <> None){1} => res{2}) => //.
  proc.
  inline{2} 1.
  seq 2 2 : (={glob A, Mem.lc, Mem.k, RO.m}).
  sim.
  sp 0 3.
  while{2} (0 <= i{2} <= size ns{2} /\ ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ Mem.k{1} = Mem.k{2} /\ (forall (c : ciphertext), (c \in Mem.lc{2}) => dec RO.m{2} Mem.k{2} c <> None => (c.`1 \in take i{2} ns{2}) => forged{2})) (size ns{2} - i{2}).
  move=> &m0 z.
  inline FinRO.get.
  wp.
  skip.
  move=> &hr [[[[hge0i hlei] [hns [hlc [hro [hk IH]]]]] hi] hz] /=.
  have Hcrux : forall (c : ciphertext), c \in Mem.lc{hr} => dec RO.m{hr} Mem.k{hr} c <> None<:nonce * associated_data * bytes> => c.`1 \in take (i{hr} + 1) ns{hr} => forged{hr} || test_poly (nth witness<:nonce> ns{hr} i{hr}) Mem.lc{hr} (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`1 (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`2.
  move=> c hcmem hdec hcin.
  have heq : take (i{hr} + 1) ns{hr} = rcons (take i{hr} ns{hr}) (nth witness<:nonce> ns{hr} i{hr}) by apply (take_nth witness<:nonce>); smt().
  move: hcin; rewrite heq mem_rcons in_cons => -[hc1|hc1].
  rewrite -hc1.
  have h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`1 (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`2.
  rewrite /test_poly /=.
  rewrite hasP.
  exists (topol c.`2 c.`3, c.`4) => /=.
  split.
  rewrite mapP; exists c => //=; rewrite mem_filter /=; exact hcmem.
  move: hdec; rewrite /dec /get /genpoly1305 /=; smt().
  smt().
  have hf := IH c hcmem hdec hc1; smt().
  smt().
  skip.
  smt(mem_undup map_f take_size take0 size_ge0).
  smt().
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1355_step2_2

Run dir: `artifacts/eval_suite/rerun_struct_core/l1_goal_projection/step2_2/r01/2026-06-10_1355_step2_2/iteration_1`

t=0: `2026-06-10T20:58:34.200000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit have h1 : Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @... | probability / pr / probability, 1 goal, goal 478 chars | accepted commit |  |
| T0.0-2 | +00:06 | [4.3 s](./views/Tree_0_0/thinking/turn_002.md) | 690 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit byequiv UFCMA_genCC => // | probability / pr / probability, 2 goals, goal 307 chars | accepted commit |  |
| T0.0-3 | +00:20 | [13.4 s](./views/Tree_0_0/thinking/turn_003.md) | 566 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit have h2 : Pr[UFCMA(A, St).main() @ &m : exists (c : ciphertext), (c \... | probability / pr / probability, 1 goal, goal 665 chars | accepted commit |  |
| T0.0-4 | +01:13 | [51.7 s](./views/Tree_0_0/thinking/turn_004.md) | 275 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit byequiv (_: ={glob A} ==> (exists (c : ciphertext), (c \in Mem.lc) /\... | probability / pr / probability, 2 goals, goal 516 chars | accepted commit |  |
| T0.0-5 | +05:27 | 254.5 s | 1.5 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | undo_last_step | equiv / prhl_module / relational_program, 2 goals, goal 553 chars | undo result |  |
| T0.0-6 | +05:58 | [29.4 s](./views/Tree_0_0/thinking/turn_006.md) | 1.6 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit have ha : Pr[UFCMA(A, St).main() @ &m : exists (c : ciphertext), (c \... | probability / pr / probability, 2 goals, goal 503 chars | accepted commit |  |
| T0.0-7 | +06:10 | [10.6 s](./views/Tree_0_0/thinking/turn_007.md) | 363 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit byequiv UFCMA_genCC => // | probability / pr / probability, 3 goals, goal 673 chars | accepted commit |  |
| T0.0-8 | +07:46 | [94.7 s](./views/Tree_0_0/thinking/turn_008.md) | 263 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit have dec_kindep : forall gs (k1 k2 : key) (c : ciphertext), (dec gs k... | ambient / ambient_logic / relational_program, 3 goals, goal 662 chars | accepted commit |  |
| T0.0-9 | +07:53 | [7.6 s](./views/Tree_0_0/thinking/turn_009.md) | 393 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit move=> gs k1 k2 [n a cph t]; rewrite /dec /genpoly1305 /get /=; smt() | ambient / ambient_logic, 4 goals, goal 487 chars | accepted commit |  |
| T0.0-10 | +08:03 | [9.6 s](./views/Tree_0_0/thinking/turn_010.md) | 1.4 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit move=> &1 &2 [[_ ->] ->]; smt(dec_kindep) | ambient / ambient_logic / relational_program, 3 goals, goal 866 chars | rejected commit: [error] cannot find lemma `dec_kindep' |  |
| T0.0-11 | +08:25 | [20.7 s](./views/Tree_0_0/thinking/turn_011.md) | 341 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit move=> &1 &2 [[_ ->] ->] | ambient / ambient_logic / relational_program, 3 goals, goal 866 chars | accepted commit |  |
| T0.0-12 | +08:40 | [14.3 s](./views/Tree_0_0/thinking/turn_012.md) | 1.7 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit smt(dec_kindep) | ambient / ambient_logic / relational_program, 3 goals, goal 795 chars | rejected commit: [error] cannot find lemma `dec_kindep' |  |
| T0.0-13 | +08:51 | [9.3 s](./views/Tree_0_0/thinking/turn_013.md) | 725 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit smt() | ambient / ambient_logic / relational_program, 3 goals, goal 795 chars | accepted commit |  |
| T0.0-14 | +08:59 | [7.4 s](./views/Tree_0_0/thinking/turn_014.md) | 647 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit rewrite ha | probability / pr / probability, 2 goals, goal 906 chars | accepted commit |  |
| T0.0-15 | +10:07 | [67.7 s](./views/Tree_0_0/thinking/turn_015.md) | 326 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit byequiv (_: ={glob A} ==> (exists (c : ciphertext), (c \in Mem.lc) /\... | probability / pr / probability, 2 goals, goal 956 chars | accepted commit |  |
| T0.0-16 | +11:12 | [64.6 s](./views/Tree_0_0/thinking/turn_016.md) | 403 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 990 chars | accepted commit |  |
| T0.0-17 | +11:25 | [12.5 s](./views/Tree_0_0/thinking/turn_017.md) | 1.5 s | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit inline{2} 1 | pRHL / call_site / relational_program, 2 goals, goal 2649 chars | accepted commit |  |
| T0.0-18 | +15:20 | [233.6 s](./views/Tree_0_0/thinking/turn_018.md) | 403 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit seq 2 2 : (={glob A, Mem.lc, Mem.k, RO.m}) | pRHL / call_site / seq_cut, 2 goals, goal 2898 chars | accepted commit |  |
| T0.0-19 | +15:27 | [6.6 s](./views/Tree_0_0/thinking/turn_019.md) | 378 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit sim | pRHL / call_site / relational_program, 3 goals, goal 1475 chars | accepted commit |  |
| T0.0-20 | +17:46 | [138.6 s](./views/Tree_0_0/thinking/turn_020.md) | 417 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit sp 0 3 | pRHL / call_site / relational_program, 2 goals, goal 2145 chars | accepted commit |  |
| T0.0-21 | +18:00 | [12.7 s](./views/Tree_0_0/thinking/turn_021.md) | 264 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit while{2} (0 <= i{2} <= size ns{2} /\ ns{2} = undup (map (fun (p : cip... | pRHL / call_site / relational_program, 2 goals, goal 1780 chars | accepted commit |  |
| T0.0-22 | +19:01 | [61.4 s](./views/Tree_0_0/thinking/turn_022.md) | 1.6 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit inline * | phoare / procedure_body / procedure_frontier, 3 goals, goal 1677 chars | rejected commit: [error] invalid arguments |  |
| T0.0-23 | +19:10 | [6.7 s](./views/Tree_0_0/thinking/turn_023.md) | 266 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit move=> &m0 z | phoare / procedure_body / procedure_frontier, 3 goals, goal 1677 chars | accepted commit |  |
| T0.0-24 | +19:14 | [4.7 s](./views/Tree_0_0/thinking/turn_024.md) | 325 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit inline FinRO.get | phoare / procedure_body / procedure_frontier, 3 goals, goal 1815 chars | accepted commit |  |
| T0.0-25 | +19:24 | [9.7 s](./views/Tree_0_0/thinking/turn_025.md) | 314 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit wp | phoare / procedure_body / procedure_frontier, 3 goals, goal 1886 chars | accepted commit |  |
| T0.0-26 | +19:31 | [5.8 s](./views/Tree_0_0/thinking/turn_026.md) | 249 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit skip | phoare / procedure_body / procedure_frontier, 3 goals, goal 1747 chars | accepted commit |  |
| T0.0-27 | +20:48 | [77.7 s](./views/Tree_0_0/thinking/turn_027.md) | 328 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit move=> &hr [[[[hge0i hlei] [hns [hlc [hro [hk IH]]]]] hi] hz] /= | ambient / ambient_logic, 3 goals, goal 1723 chars | accepted commit |  |
| T0.0-28 | +22:40 | [110.7 s](./views/Tree_0_0/thinking/turn_028.md) | 295 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit have Hcrux : forall (c : ciphertext), c \in Mem.lc{hr} => dec RO.m{hr... | ambient / ambient_logic, 3 goals, goal 1891 chars | accepted commit |  |
| T0.0-29 | +22:49 | [8.7 s](./views/Tree_0_0/thinking/turn_029.md) | 261 ms | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit move=> c hcmem hdec hcin | ambient / ambient_logic, 4 goals, goal 1670 chars | accepted commit |  |
| T0.0-30 | +23:31 | [42.6 s](./views/Tree_0_0/thinking/turn_030.md) | 358 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit have heq : take (i{hr} + 1) ns{hr} = rcons (take i{hr} ns{hr}) (nth witness<:nonce> ns{hr} i{... | ambient / ambient_logic, 4 goals, goal 1655 chars | accepted commit |  |
| T0.0-31 | +24:18 | [45.7 s](./views/Tree_0_0/thinking/turn_031.md) | 287 ms | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | commit move: hcin; rewrite heq mem_rcons in_cons => -[hc1\|hc1] | ambient / ambient_logic, 4 goals, goal 1752 chars | accepted commit |  |
| T0.0-32 | +24:44 | [26.4 s](./views/Tree_0_0/thinking/turn_032.md) | 1.6 s | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit rewrite -hc1; apply/orP; right | ambient / ambient_logic, 5 goals, goal 1758 chars | rejected commit: [error] unknown lemma `orP' |  |
| T0.0-33 | +24:59 | [12.7 s](./views/Tree_0_0/thinking/turn_033.md) | 261 ms | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | commit rewrite -hc1 | ambient / ambient_logic, 5 goals, goal 1758 chars | accepted commit |  |
| T0.0-34 | +25:06 | [7.5 s](./views/Tree_0_0/thinking/turn_034.md) | 1.5 s | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | commit suff h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofin... | ambient / ambient_logic, 5 goals, goal 1670 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-35 | +25:38 | [30.4 s](./views/Tree_0_0/thinking/turn_035.md) | 1.6 s | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | commit suff h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofin... | ambient / ambient_logic, 5 goals, goal 1670 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-36 | +28:16 | [156.3 s](./views/Tree_0_0/thinking/turn_036.md) | 1.7 s | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit suff h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofin... | ambient / ambient_logic, 5 goals, goal 1670 chars | rejected commit: [error] cannot find lemma `h' |  |
| T0.0-37 | +29:09 | [51.3 s](./views/Tree_0_0/thinking/turn_037.md) | 1.7 s | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | commit have h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`1 (mk_rs (oget... | ambient / ambient_logic, 5 goals, goal 1670 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-38 | +29:25 | [14.6 s](./views/Tree_0_0/thinking/turn_038.md) | 358 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit have h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofin... | ambient / ambient_logic, 5 goals, goal 1670 chars | accepted commit |  |
| T0.0-39 | +29:56 | [29.7 s](./views/Tree_0_0/thinking/turn_039.md) | 299 ms | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | commit rewrite /test_poly /= | ambient / ambient_logic, 6 goals, goal 1656 chars | accepted commit |  |
| T0.0-40 | +30:07 | [11.2 s](./views/Tree_0_0/thinking/turn_040.md) | 1.8 s | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit apply/hasP; exists (topol c.`2 c.`3, c.`4) => /= | ambient / ambient_logic, 6 goals, goal 1834 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-41 | +30:21 | [12.4 s](./views/Tree_0_0/thinking/turn_041.md) | 1.6 s | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | commit apply/hasP | ambient / ambient_logic, 6 goals, goal 1834 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-42 | +30:41 | [17.7 s](./views/Tree_0_0/thinking/turn_042.md) | 264 ms | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit rewrite hasP | ambient / ambient_logic, 6 goals, goal 1834 chars | accepted commit |  |
| T0.0-43 | +30:47 | [5.7 s](./views/Tree_0_0/thinking/turn_043.md) | 252 ms | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | commit exists (topol c.`2 c.`3, c.`4) => /= | ambient / ambient_logic, 6 goals, goal 1878 chars | accepted commit |  |
| T0.0-44 | +31:05 | [18.7 s](./views/Tree_0_0/thinking/turn_044.md) | 314 ms | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | commit split | ambient / ambient_logic, 6 goals, goal 1819 chars | accepted commit |  |
| T0.0-45 | +31:29 | [23.7 s](./views/Tree_0_0/thinking/turn_045.md) | 321 ms | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | commit rewrite mapP; exists c => //=; rewrite mem_filter /=; exact hcmem | ambient / ambient_logic, 7 goals, goal 1684 chars | accepted commit |  |
| T0.0-46 | +31:51 | [21.6 s](./views/Tree_0_0/thinking/turn_046.md) | 387 ms | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | commit move: hdec; rewrite /dec /get /genpoly1305 /=; smt() | ambient / ambient_logic, 6 goals, goal 1664 chars | accepted commit |  |
| T0.0-47 | +31:59 | [7.3 s](./views/Tree_0_0/thinking/turn_047.md) | 1.7 s | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | commit smt(h) | ambient / ambient_logic, 5 goals, goal 1796 chars | rejected commit: [error] cannot find lemma `h' |  |
| T0.0-48 | +32:07 | [6.6 s](./views/Tree_0_0/thinking/turn_048.md) | 355 ms | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | commit smt() | ambient / ambient_logic, 5 goals, goal 1796 chars | accepted commit |  |
| T0.0-49 | +32:25 | [17.6 s](./views/Tree_0_0/thinking/turn_049.md) | 371 ms | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | commit have hf := IH c hcmem hdec hc1; smt() | ambient / ambient_logic, 4 goals, goal 1745 chars | accepted commit |  |
| T0.0-50 | +33:00 | [33.7 s](./views/Tree_0_0/thinking/turn_050.md) | 5.3 s | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | commit smt(Hcrux hge0i hlei hi hz hns hlc hro hk) | ambient / ambient_logic, 3 goals, goal 2362 chars | rejected commit: [error] cannot find lemma `Hcrux' |  |
| T0.0-51 | +33:14 | [8.7 s](./views/Tree_0_0/thinking/turn_051.md) | 1.3 s | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit smt() | ambient / ambient_logic, 3 goals, goal 2362 chars | accepted commit |  |
| T0.0-52 | +34:00 | [45.5 s](./views/Tree_0_0/thinking/turn_052.md) | 5.5 s | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | commit smt(mem_undup map_f take_size take0 size_ge0) | pRHL / procedure_entry / relational_program, 2 goals, goal 2433 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-53 | +35:09 | [63.4 s](./views/Tree_0_0/thinking/turn_053.md) | 618 ms | [turn_052.json](./views/Tree_0_0/turn_052.json) · [inline read](./views/Tree_0_0/followups/turn_052.md) | commit skip | pRHL / procedure_entry / relational_program, 2 goals, goal 2433 chars | accepted commit |  |
| T0.0-54 | +35:52 | [42 s](./views/Tree_0_0/thinking/turn_054.md) | 2 s | [turn_053.json](./views/Tree_0_0/turn_053.json) · [inline read](./views/Tree_0_0/followups/turn_053.md) | commit move=> &1 &2 [hns0 hf0 hi0 hgA hlc0 hk0 hro0]; split | ambient / ambient_logic / relational_program, 2 goals, goal 2289 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-55 | +36:07 | [13.1 s](./views/Tree_0_0/thinking/turn_055.md) | 1.9 s | [turn_054.json](./views/Tree_0_0/turn_054.json) · [inline read](./views/Tree_0_0/followups/turn_054.md) | commit move=> &mL &mR [hns0 hf0 hi0 hgA hlc0 hk0 hro0]; split | ambient / ambient_logic / relational_program, 2 goals, goal 2289 chars | rejected commit: [error] nothing to introduce |  |
| T0.0-56 | +36:41 | [32.2 s](./views/Tree_0_0/thinking/turn_056.md) | 820 ms | [turn_055.json](./views/Tree_0_0/turn_055.json) · [inline read](./views/Tree_0_0/followups/turn_055.md) | commit smt(mem_undup map_f take_size take0 size_ge0) | ambient / ambient_logic / relational_program, 2 goals, goal 2289 chars | accepted commit |  |
| T0.0-57 | +36:59 | [16.7 s](./views/Tree_0_0/thinking/turn_057.md) | 252 ms | [turn_056.json](./views/Tree_0_0/turn_056.json) · [inline read](./views/Tree_0_0/followups/turn_056.md) | commit smt() | probability / pr / probability, 1 goal, goal 882 chars | accepted commit |  |
| T0.0-58 | +37:11 | 12 s |  | [turn_057.json](./views/Tree_0_0/turn_057.json) · [inline read](./views/Tree_0_0/followups/turn_057.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.0-59 | +37:15 | [3.8 s](./views/Tree_0_0/thinking/turn_059.md) | 215 ms | [turn_058.json](./views/Tree_0_0/turn_058.json) · [inline read](./views/Tree_0_0/followups/turn_058.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-60 | +37:27 | 12 s |  | [turn_059.json](./views/Tree_0_0/turn_059.json) · [inline read](./views/Tree_0_0/followups/turn_059.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
