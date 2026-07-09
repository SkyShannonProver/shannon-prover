# Agent-View Timeline — `equ_cc`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-08_1940_equ_cc |
| lemma | `equ_cc` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 74 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 24 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  sp 2 3.
  while (={i} /\ c{1} = c{2} /\ n{1} = n0 /\ n{2} = n0 /\ size p{1} = size p{2} /\ 1 <= i{1} /\ size c{1} + size p{1} <= max_cipher_size /\ (p{1} <> [] => size c{1} = block_size * (i{1} - 1)) /\ (forall (cc : C.counter), (n0, cc) \in ROF.m{1} => C.toint cc < i{1}) /\ (forall (nn : nonce) (cc : C.counter), (nn, cc) \in ROF.m{1} => nn \in n0 :: BNR.lenc{1}) /\ mr0 = ROin.m{1} /\ ms0 = ROout.m{1}).
  inline{1}.
  rcondf{1} 5.
  auto.
  move=> &hr H; have hp1 : 1 <= size p{hr} by smt(size_eq0 size_ge0); have hmul : block_size * (i{hr} - 1) < block_size * C.max_counter by smt(max_cipher_size_ok mulzC); have hb : i{hr} - 1 < C.max_counter by smt(ltr_pmul2l gt0_block_size); rewrite /SplitD.test /= C.ofintdK 1:/# /#.
  have hc : size c{hr} = block_size * (i{hr} - 1) by smt(); have hmul : block_size * (i{hr} - 1) < block_size * C.max_counter by smt(max_cipher_size_ok mulzC); have hb : i{hr} - 1 < C.max_counter by smt(IntOrder.ltr_pmul2l gt0_block_size); rewrite /SplitD.test /= C.ofintdK 1:/# /#.
  have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); have hb : i{hr} - 1 < C.max_counter by smt(IntOrder.ltr_pmul2r mulzC gt0_block_size); rewrite /SplitD.test /= C.ofintdK 1:/# /#.
  move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; rewrite /SplitD.test /=; smt(C.ofintdK).
  rcondt{1} 7.
  auto; move=> &hr H; have hp1 : 1 <= size p{hr} by smt(size_eq0 size_ge0); have hc : size c{hr} = block_size * (i{hr} - 1) by smt(); have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; smt(C.ofintdK).
  have hc : size c{hr} = block_size * (i{hr} - 1) by smt().
  have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; move=> r0_0 _; smt(C.ofintdK).
  move=> r0_0 _; move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; smt(C.ofintdK).
  sp 5 0.
  wp.
  rnd (fun (r:block) => extend p{1} +^ r) (fun (r:block) => extend p{1} +^ r).
  skip.
  move=> &1 &2 H; have inv : forall (b zz:block), b +^ (b +^ zz) = zz by smt(Block.addK Block.MB.addmA Block.MB.add0m Block.MB.addmC).
  split.
  by move=> zR _; rewrite inv.
  move=> _ r0L hr0L; rewrite inv /=.
  rewrite get_set_sameE /=.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc.
  inline *.
  seq 2 3 : (c{1} = c{2} /\ size p{1} = size p{2} /\ size c{1} + size p{1} <= max_cipher_size /\ 1 <= i{1} /\ i{1} - 1 + (size p{1} + block_size - 1) %/ block_size <= C.max_counter /\ n{1} = n0 /\ mr0 = ROin.m{1} /\ ms0 = ROout.m{1} /\ (forall (nn : nonce) (cc : C.counter), (nn, cc) \in ROF.m{1} => nn \in n0 :: BNR.lenc{1}) /\ (forall (cc : C.counter), (n0, cc) \in ROF.m{1} => C.toint cc < i{1})).
  wp; skip => />.
  move=> &1 hsz hnl hdom; split; first by rewrite size_map.
  split.
  apply (lez_trans ((C.max_counter * block_size + block_size - 1) %/ block_size)); first by apply leq_div2r; smt(max_cipher_size_ok gt0_block_size).
  have heq : C.max_counter * block_size + block_size - 1 = C.max_counter * block_size + (block_size - 1) by smt().
  rewrite heq.
  have hbn : block_size <> 0 by smt(gt0_block_size).
  rewrite divzMDl // divz_small; smt(gt0_block_size).
  split; first by move=> nn cc h; right; apply (hdom nn cc h).
  move=> cc h; have := hdom n0 cc h; smt().
  while (c{1} = c{2} /\ size p{1} = size p{2} /\ size c{1} + size p{1} <= max_cipher_size /\ 1 <= i{1} /\ i{1} - 1 + (size p{1} + block_size - 1) %/ block_size <= C.max_counter /\ n{1} = n0 /\ mr0 = ROin.m{1} /\ ms0 = ROout.m{1} /\ (forall (nn : nonce) (cc : C.counter), (nn, cc) \in ROF.m{1} => nn \in n0 :: BNR.lenc{1}) /\ (forall (cc : C.counter), (n0, cc) \in ROF.m{1} => C.toint cc < i{1})).
  rcondf{1} 5.
  move=> &m; auto; smt(C.ofintdK gt0_block_size lez_divRL size_ge0 size_eq0).
  rcondt{1} 7.
  move=> &m; auto; smt(C.ofintdK gt0_block_size lez_divRL size_ge0 size_eq0).
  wp.
  rnd (fun (x : block) => extend p{1} +^ x) (fun (x : block) => extend p{1} +^ x).
  wp; skip => />.
  have hinv : forall (a b : block), a +^ (a +^ b) = b by move=> a b; rewrite Block.MB.addmA Block.addK Block.MB.add0m.
  move=> &1 &2 hsz hc hi1 hcnt hdom1 hdom2 hp1 hp2; split; first by move=> zR _; rewrite hinv.
  move=> _ r0L hr0L; split; first by rewrite hinv.
  move=> _; rewrite !get_set_sameE /=.
  split; last by smt(size_drop size_eq0 gt0_block_size).
  split; first by rewrite hsz.
  split; first by smt(size_drop gt0_block_size).
  split; first by smt(size_cat size_take size_drop Block.bytes_of_blockP gt0_block_size size_ge0).
  split; first by smt().
  split; first by smt(size_drop divzMDl divz_small lez_divRL leq_div2r gt0_block_size size_ge0 size_eq0).
  split; first by smt(mem_set).
  smt(mem_set C.ofintdK lez_divRL leq_div2r divz_small gt0_block_size size_ge0 size_eq0).
  skip.
  smt(size_eq0).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_1940_equ_cc

Run dir: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1`

t=0: `2026-06-09T02:44:27.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 804 chars | accepted commit |  |
| T0.0-2 | +02:40 | [158.7 s](./views/Tree_0_0/thinking/turn_002.md) | 314 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit sp 2 3 | pRHL / call_site / relational_program, 1 goal, goal 3771 chars | accepted commit |  |
| T0.0-3 | +03:07 | [25.7 s](./views/Tree_0_0/thinking/turn_003.md) | 291 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit while (={i} /\ c{1} = c{2} /\ n{1} = n0 /\ n{2} = n0 /\ size p{1} = s... | pRHL / call_site / relational_program, 1 goal, goal 2816 chars | accepted commit |  |
| T0.0-4 | +03:45 | [38.4 s](./views/Tree_0_0/thinking/turn_004.md) | 1.6 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit inline{1} | pRHL / call_site / relational_program, 2 goals, goal 2821 chars | accepted commit |  |
| T0.0-5 | +04:47 | [59.7 s](./views/Tree_0_0/thinking/turn_005.md) | 254 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit rcondf{1} 5 | pRHL / procedure_body / relational_program, 2 goals, goal 5798 chars | accepted commit |  |
| T0.0-6 | +05:29 | [42.4 s](./views/Tree_0_0/thinking/turn_006.md) | 4.6 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit auto; smt(C.ofintdK gt0_block_size max_cipher_size_ok C.gt0_max_counter size_eq0 size_ge0) | hoare / procedure_body / procedure_frontier, 3 goals, goal 823 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-7 | +06:00 | [25.8 s](./views/Tree_0_0/thinking/turn_007.md) | 218 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit auto | hoare / procedure_body / procedure_frontier, 3 goals, goal 823 chars | accepted commit |  |
| T0.0-8 | +07:19 | [78.8 s](./views/Tree_0_0/thinking/turn_008.md) | 237 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit move=> &hr H; have hp1 : 1 <= size p{hr} by smt(size_eq0 size_ge0); have hmul : block_size *... | ambient / ambient_logic, 3 goals, goal 876 chars | accepted commit |  |
| T0.0-9 | +08:52 | [92.8 s](./views/Tree_0_0/thinking/turn_009.md) | 246 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit have hc : size c{hr} = block_size * (i{hr} - 1) by smt(); have hmul : block_size * (i{hr} - 1... | ambient / ambient_logic, 3 goals, goal 1143 chars | accepted commit |  |
| T0.0-10 | +09:29 | [37.7 s](./views/Tree_0_0/thinking/turn_010.md) | 302 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); h... | ambient / ambient_logic, 3 goals, goal 1185 chars | accepted commit |  |
| T0.0-11 | +11:09 | [99.5 s](./views/Tree_0_0/thinking/turn_011.md) | 4.5 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_si... | ambient / ambient_logic, 3 goals, goal 1243 chars | accepted commit |  |
| T0.0-12 | +11:55 | [40.7 s](./views/Tree_0_0/thinking/turn_012.md) | 255 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit rcondt{1} 7 | pRHL / procedure_body / seq_cut, 2 goals, goal 3246 chars | accepted commit |  |
| T0.0-13 | +12:35 | [39.7 s](./views/Tree_0_0/thinking/turn_013.md) | 287 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit auto; move=> &hr H; have hp1 : 1 <= size p{hr} by smt(size_eq0 size_ge0); have hc : size c{hr... | hoare / procedure_body / procedure_frontier, 3 goals, goal 828 chars | accepted commit |  |
| T0.0-14 | +13:21 | [46.4 s](./views/Tree_0_0/thinking/turn_014.md) | 639 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit have hc : size c{hr} = block_size * (i{hr} - 1) by smt() | ambient / ambient_logic, 3 goals, goal 1200 chars | accepted commit |  |
| T0.0-15 | +13:38 | [16.3 s](./views/Tree_0_0/thinking/turn_015.md) | 686 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); m... | ambient / ambient_logic, 3 goals, goal 1242 chars | accepted commit |  |
| T0.0-16 | +18:11 | 272.1 s | 6.9 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit move=> r0_0 _; move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_si... | ambient / ambient_logic, 3 goals, goal 1300 chars | accepted commit |  |
| T0.0-17 | +19:23 | 64.8 s | 2.2 s | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit sp 5 0 | pRHL / procedure_body / seq_cut, 2 goals, goal 3038 chars | accepted commit |  |
| T0.0-18 | +19:36 | 11.6 s | 412 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit wp | pRHL / procedure_body / seq_cut, 2 goals, goal 2632 chars | accepted commit |  |
| T0.0-19 | +21:15 | 97.7 s | 297 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit rnd (fun (r:block) => extend p{1} +^ r) (fun (r:block) => extend p{1}... | pRHL / procedure_body / relational_program, 2 goals, goal 1963 chars | accepted commit |  |
| T0.0-20 | +22:09 | 53.7 s | 275 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit skip | pRHL / procedure_entry / relational_program, 2 goals, goal 2144 chars | accepted commit |  |
| T0.0-21 | +23:33 | 84.6 s | 364 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit move=> &1 &2 H; have inv : forall (b zz:block), b +^ (b +^ zz) = zz by smt(Block.addK Block.M... | ambient / ambient_logic / relational_program, 2 goals, goal 1793 chars | accepted commit |  |
| T0.0-22 | +23:43 | 9 s | 2 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit split; 1: by move=> zR _; rewrite inv. move=> r0L hr0L; split; 1: by rewrite inv | ambient / ambient_logic / relational_program, 2 goals, goal 2099 chars | rejected commit: [error] cannot apply `split/None` on that goal |  |
| T0.0-23 | +26:00 | 134.7 s | 269 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit split | ambient / ambient_logic / relational_program, 2 goals, goal 2099 chars | accepted commit |  |
| T0.0-24 | +26:14 | 13.7 s | 283 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit by move=> zR _; rewrite inv | ambient / ambient_logic / relational_program, 3 goals, goal 1253 chars | accepted commit |  |
| T0.0-25 | +27:00 | 45.7 s | 274 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit move=> _ r0L hr0L; rewrite inv /= | ambient / ambient_logic / relational_program, 2 goals, goal 2099 chars | accepted commit |  |
| T0.0-26 | +28:04 | 63.7 s | 265 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit rewrite get_set_sameE /= | ambient / ambient_logic / relational_program, 2 goals, goal 2270 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +01:13 |  | 1.5 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 804 chars | accepted commit |  |
| T0.1-2 | +01:39 | 24.7 s | 331 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 3771 chars | accepted commit |  |
| T0.1-3 | +02:17 | 36.7 s | 280 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit seq 2 3 : (c{1} = c{2} /\ size p{1} = size p{2} /\ size c{1} + size p... | pRHL / procedure_body / relational_program, 1 goal, goal 6867 chars | accepted commit |  |
| T0.1-4 | +02:48 | 31.6 s | 1.4 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit auto => /> *; smt(size_map max_cipher_size_ok gt0_block_size mem_cons) | pRHL / procedure_body / relational_program, 2 goals, goal 1734 chars | rejected commit: [error] cannot find lemma `mem_cons' |  |
| T0.1-5 | +02:57 | 7.3 s | 4.7 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit auto => /> *; smt(size_map max_cipher_size_ok gt0_block_size in_cons) | pRHL / procedure_body / relational_program, 2 goals, goal 1734 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-6 | +03:37 | 35.4 s | 1.6 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp; skip => /> &1 &2 hpre1 hpre2 hsz hnlenc hdom hr hs | pRHL / procedure_body / relational_program, 2 goals, goal 1734 chars | rejected commit: [error] nothing to introduce |  |
| T0.1-7 | +03:46 | 6.8 s | 231 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit wp; skip => /> | pRHL / procedure_body / relational_program, 2 goals, goal 1734 chars | accepted commit |  |
| T0.1-8 | +04:53 | 66.8 s | 213 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit move=> &1 hsz hnl hdom; split; first by rewrite size_map | ambient / ambient_logic, 2 goals, goal 731 chars | accepted commit |  |
| T0.1-9 | +05:03 | 10.5 s | 4.5 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit split; first by smt(max_cipher_size_ok gt0_block_size) | ambient / ambient_logic, 2 goals, goal 889 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-10 | +06:21 | 72.8 s | 215 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit split | ambient / ambient_logic, 2 goals, goal 889 chars | accepted commit |  |
| T0.1-11 | +06:40 | 18.7 s | 296 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit apply (lez_trans ((C.max_counter * block_size + block_size - 1) %/ block_size)); first by app... | ambient / ambient_logic, 3 goals, goal 698 chars | accepted commit |  |
| T0.1-12 | +07:14 | 34.6 s | 372 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit have heq : C.max_counter * block_size + block_size - 1 = C.max_counte... | ambient / ambient_logic, 3 goals, goal 715 chars | accepted commit |  |
| T0.1-13 | +07:37 | 22.4 s | 1.6 s | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit rewrite heq divzMDl 1:gtr_eqF 1:gt0_block_size divz_small 1:ltr_subl_addr; smt(gt0_block_size) | ambient / ambient_logic, 3 goals, goal 817 chars | rejected commit: [error] nothing to rewrite |  |
| T0.1-14 | +07:58 | 19.4 s | 1.6 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit rewrite heq divzMDl 1:gtr_eqF // divz_small; smt(gt0_block_size) | ambient / ambient_logic, 3 goals, goal 817 chars | rejected commit: [error] nothing to rewrite |  |
| T0.1-15 | +08:19 | 18.8 s | 203 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit rewrite heq | ambient / ambient_logic, 3 goals, goal 817 chars | accepted commit |  |
| T0.1-16 | +08:31 | 11.7 s | 257 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit have hbn : block_size <> 0 by smt(gt0_block_size) | ambient / ambient_logic, 3 goals, goal 819 chars | accepted commit |  |
| T0.1-17 | +08:41 | 9.7 s | 287 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit rewrite divzMDl // divz_small; smt(gt0_block_size) | ambient / ambient_logic, 3 goals, goal 840 chars | accepted commit |  |
| T0.1-18 | +08:54 | 12.8 s | 178 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit split; first by move=> nn cc h; right; apply (hdom nn cc h) | ambient / ambient_logic, 2 goals, goal 826 chars | accepted commit |  |
| T0.1-19 | +08:58 | 4.6 s | 363 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit move=> cc h; have := hdom n0 cc h; smt() | ambient / ambient_logic, 2 goals, goal 713 chars | accepted commit |  |
| T0.1-20 | +09:36 | 37.3 s | 1.7 s | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit while (c{1} = c{2} /\ size p{1} = size p{2} /\ size c{1} + size p{1}... | pRHL / procedure_body / relational_program, 1 goal, goal 5927 chars | accepted commit |  |
| T0.1-21 | +10:04 | 25.8 s | 231 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit rcondf{1} 5 | pRHL / procedure_body / relational_program, 2 goals, goal 5770 chars | accepted commit |  |
| T0.1-22 | +10:37 | 33.1 s | 4.9 s | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit move=> &m; auto; smt(C.ofintdK gt0_block_size lez_divRL size_ge0 size_eq0) | hoare / procedure_body / procedure_frontier, 3 goals, goal 807 chars | accepted commit |  |
| T0.1-23 | +11:01 | 18.8 s | 244 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit rcondt{1} 7 | pRHL / procedure_body / seq_cut, 2 goals, goal 3218 chars | accepted commit |  |
| T0.1-24 | +11:13 | 11.8 s | 5.2 s | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit move=> &m; auto; smt(C.ofintdK gt0_block_size lez_divRL size_ge0 size_eq0) | hoare / procedure_body / procedure_frontier, 3 goals, goal 812 chars | accepted commit |  |
| T0.1-25 | +13:26 | 128.5 s | 14.5 s | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit wp | pRHL / procedure_body / seq_cut, 2 goals, goal 3010 chars | accepted commit |  |
| T0.1-26 | +14:08 | 27.3 s | 668 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit rnd (fun (x : block) => extend p{1} +^ x) (fun (x : block) => extend... | pRHL / procedure_body / seq_cut, 2 goals, goal 2113 chars | accepted commit |  |
| T0.1-27 | +14:45 | 36.3 s | 701 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit wp; skip => /> | pRHL / procedure_body / relational_program, 2 goals, goal 2292 chars | accepted commit |  |
| T0.1-28 | +20:15 | 329 s | 2 s | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit have hinv : forall (a b : block), a +^ (a +^ b) = b by move=> a b; rewrite Block.MB.addmA Blo... | ambient / ambient_logic / relational_program, 2 goals, goal 2240 chars | accepted commit |  |
| T0.1-29 | +21:11 | 54.7 s | 305 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit move=> &1 &2 hsz hc hi1 hcnt hdom1 hdom2 hp1 hp2; split; first by move=> zR _; rewrite hinv | ambient / ambient_logic / relational_program, 2 goals, goal 2286 chars | accepted commit |  |
| T0.1-30 | +21:19 | 6.7 s | 267 ms | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit move=> _ r0L hr0L; split; first by rewrite hinv | ambient / ambient_logic / relational_program, 2 goals, goal 2378 chars | accepted commit |  |
| T0.1-31 | +21:49 | 29.7 s | 290 ms | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit move=> _; rewrite !get_set_sameE /= | ambient / ambient_logic / relational_program, 2 goals, goal 2073 chars | accepted commit |  |
| T0.1-32 | +22:51 | 61.8 s | 5.2 s | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit smt(size_cat size_take size_drop size_ge0 size_eq0 Block.bytes_of_blockP mem_set C.ofintdK gt0_block_size divzMDl divz_small) | ambient / ambient_logic / relational_program, 2 goals, goal 1833 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-33 | +23:52 | 56 s | 2 s | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | commit split; first by rewrite hsz | ambient / ambient_logic / relational_program, 2 goals, goal 1833 chars | rejected commit: [by]: cannot close goals |  |
| T0.1-34 | +24:15 | 21.6 s | 417 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit split; last by smt(size_drop size_eq0 gt0_block_size) | ambient / ambient_logic / relational_program, 2 goals, goal 1833 chars | accepted commit |  |
| T0.1-35 | +25:04 | 48.7 s | 304 ms | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit split; first by rewrite hsz | ambient / ambient_logic / relational_program, 2 goals, goal 1698 chars | accepted commit |  |
| T0.1-36 | +25:08 | 3.6 s | 377 ms | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | commit split; first by smt(size_drop gt0_block_size) | ambient / ambient_logic / relational_program, 2 goals, goal 1567 chars | accepted commit |  |
| T0.1-37 | +25:15 | 6.6 s | 391 ms | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | commit split; first by smt(size_cat size_take size_drop Block.bytes_of_blockP gt0_block_size size_ge0) | ambient / ambient_logic / relational_program, 2 goals, goal 1506 chars | accepted commit |  |
| T0.1-38 | +25:20 | 4.7 s | 342 ms | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | commit split; first by smt() | ambient / ambient_logic / relational_program, 2 goals, goal 1384 chars | accepted commit |  |
| T0.1-39 | +25:54 | 33.4 s | 620 ms | [turn_038.json](./views/Tree_0_1/turn_038.json) · [inline read](./views/Tree_0_1/followups/turn_038.md) | commit split; first by smt(size_drop divzMDl divz_small lez_divRL leq_div2r gt0_block_size size_ge0... | ambient / ambient_logic / relational_program, 2 goals, goal 1367 chars | accepted commit |  |
| T0.1-40 | +26:18 | 23.5 s | 2.5 s | [turn_039.json](./views/Tree_0_1/turn_039.json) · [inline read](./views/Tree_0_1/followups/turn_039.md) | commit split; first by smt(mem_set hdom1) | ambient / ambient_logic / relational_program, 2 goals, goal 1279 chars | rejected commit: [error] cannot find lemma `hdom1' |  |
| T0.1-41 | +26:24 | 3.7 s | 334 ms | [turn_040.json](./views/Tree_0_1/turn_040.json) · [inline read](./views/Tree_0_1/followups/turn_040.md) | commit split; first by smt(mem_set) | ambient / ambient_logic / relational_program, 2 goals, goal 1279 chars | accepted commit |  |
| T0.1-42 | +26:58 | 33.6 s | 429 ms | [turn_041.json](./views/Tree_0_1/turn_041.json) · [inline read](./views/Tree_0_1/followups/turn_041.md) | commit smt(mem_set C.ofintdK lez_divRL leq_div2r divz_small gt0_block_size size_ge0 size_eq0) | ambient / ambient_logic / relational_program, 2 goals, goal 1136 chars | accepted commit |  |
| T0.1-43 | +27:46 | 46.7 s | 291 ms | [turn_042.json](./views/Tree_0_1/turn_042.json) · [inline read](./views/Tree_0_1/followups/turn_042.md) | commit skip | pRHL / procedure_body / relational_program, 1 goal, goal 2315 chars | accepted commit |  |
| T0.1-44 | +27:57 | 11.7 s | 315 ms | [turn_043.json](./views/Tree_0_1/turn_043.json) · [inline read](./views/Tree_0_1/followups/turn_043.md) | commit smt(size_eq0) | ambient / ambient_logic / relational_program, 1 goal, goal 1976 chars | accepted commit |  |
| T0.1-45 | +28:02 | 4 s |  | [turn_044.json](./views/Tree_0_1/turn_044.json) · [inline read](./views/Tree_0_1/followups/turn_044.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.1-46 | +28:07 | 4.8 s | 187 ms | [turn_045.json](./views/Tree_0_1/turn_045.json) · [inline read](./views/Tree_0_1/followups/turn_045.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-47 | +28:10 | 3 s |  | [turn_046.json](./views/Tree_0_1/turn_046.json) · [inline read](./views/Tree_0_1/followups/turn_046.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
| T0.1-48 | +28:24 | 14 s |  | [turn_047.json](./views/Tree_0_1/turn_047.json) · [inline read](./views/Tree_0_1/followups/turn_047.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
