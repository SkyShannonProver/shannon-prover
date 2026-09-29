# Agent-View Timeline — `UFCMA_genCC`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-08_2025_UFCMA_genCC |
| lemma | `UFCMA_genCC` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 60 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  inline{1} 2.
  inline{2} 2.
  wp.
  call (_: ={Mem.k, Mem.log, Mem.lc} /\ StLSke.gs{1} = RO.m{2}).
  proc.
  inline{1} 1.
  inline{1} 2.
  inline{2} 1.
  inline{2} 2.
  wp.
  sp.
  inline{2} 1.
  sp.
  seq 0 1 : ( (n{2}, a{2}, p1{2}) = p{2} /\ p{1} = p{2} /\ Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2} /\ k0{2} = Mem.k{2} /\ n0{2} = n{2} /\ c2{2} = gen_CTR_encrypt_bytes take_xor (get RO.m{2}) k0{2} n0{2} 1 p1{2} ).
  while{2} ( (p{1} = p{2} /\ Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2}) /\ StLSke.gs{1} = RO.m{2} /\ k0{2} = Mem.k{2} /\ n0{2} = n{2} /\ k{2} = Mem.k{2} /\ (n{2}, a{2}, p1{2}) = p{2} /\ c2{2} ++ gen_CTR_encrypt_bytes take_xor (get RO.m{2}) k0{2} n0{2} i{2} p2{2} = gen_CTR_encrypt_bytes take_xor (get RO.m{2}) k0{2} n0{2} 1 p1{2} ) (size p2{2}).
  move=> &m z.
  inline.
  wp.
  skip.
  move=> &hr [[hI hne] hsz].
  have hmerge : forall (str : block), take_xor [] str = [] by move=> str; rewrite /take_xor; smt(take0 size_eq0).
  rewrite gen_CTR_encrypt_bytes_cons in hI.
  move=> str; rewrite /take_xor; smt(take0 size_eq0).
  rewrite catA in hI.
  simplify.
  split.
  exact hI.
  smt(size_drop gt0_block_size size_eq0 size_ge0).
  move=> />.
  move=> &1 &2 hpre hyp; smt(cat0s size_ge0 size_eq0).
  skip.
  move=> &1 &2 hpre c2_R i_R p2_R.
  have hnil : gen_CTR_encrypt_bytes take_xor (get RO.m{2}) Mem.k{2} n{2} i_R [] = [] by apply gen_CTR_encrypt_bytes0; move=> str; rewrite /take_xor; smt(take0 size_eq0).
  split; [ smt(size_ge0 size_eq0) | smt(cats0) ].
  sp.
  inline{2} 1.
  inline{2} 5.
  inline{2} 8.
  sp.
  skip.
  move=> &1 &2 />.
  proc.
  auto=> />; smt().
  conseq (_: _ ==> (glob A){1} = (glob A){2} /\ (Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2}) /\ StLSke.gs{1} = RO.m{2}).
  move=> /> *; smt().
  inline *.
  sim.
  qed.
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc.
  inline{1} 2.
  inline{2} 2.
  wp.
  call (_: ={Mem.k, Mem.log, Mem.lc} /\ StLSke.gs{1} = RO.m{2}).
  proc.
  inline{1} 1.
  inline{1} 2.
  inline{2} 1.
  inline{2} 2.
  wp.
  sp.
  inline{2} 1.
  sp.
  seq 0 1 : ( (n{2}, a{2}, p1{2}) = p{2} /\ p{1} = p{2} /\ Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2} /\ k0{2} = Mem.k{2} /\ n0{2} = n{2} /\ c2{2} = gen_CTR_encrypt_bytes take_xor (get RO.m{2}) k0{2} n0{2} 1 p1{2} ).
  while{2} ( (p{1} = p{2} /\ Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2}) /\ StLSke.gs{1} = RO.m{2} /\ k0{2} = Mem.k{2} /\ n0{2} = n{2} /\ k{2} = Mem.k{2} /\ (n{2}, a{2}, p1{2}) = p{2} /\ c2{2} ++ gen_CTR_encrypt_bytes take_xor (get RO.m{2}) k0{2} n0{2} i{2} p2{2} = gen_CTR_encrypt_bytes take_xor (get RO.m{2}) k0{2} n0{2} 1 p1{2} ) (size p2{2}).
  move=> &m z.
  inline.
  wp.
  skip.
  move=> &hr [[hI hne] hsz].
  have hmerge : forall (str : block), take_xor [] str = [] by move=> str; rewrite /take_xor; smt(take0 size_eq0).
  rewrite gen_CTR_encrypt_bytes_cons in hI.
  move=> str; rewrite /take_xor; smt(take0 size_eq0).
  rewrite catA in hI.
  simplify.
  split.
  exact hI.
  smt(size_drop gt0_block_size size_eq0 size_ge0).
  move=> />.
  move=> &1 &2 hpre hyp; smt(cat0s size_ge0 size_eq0).
  skip.
  move=> &1 &2 hpre c2_R i_R p2_R.
  have hnil : gen_CTR_encrypt_bytes take_xor (get RO.m{2}) Mem.k{2} n{2} i_R [] = [] by apply gen_CTR_encrypt_bytes0; move=> str; rewrite /take_xor; smt(take0 size_eq0).
  split; [ smt(size_ge0 size_eq0) | smt(cats0) ].
  sp.
  inline{2} 1.
  inline{2} 5.
  inline{2} 8.
  sp.
  skip.
  move=> &1 &2 />.
  proc.
  auto=> />; smt().
  conseq (_: _ ==> (glob A){1} = (glob A){2} /\ (Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2}) /\ StLSke.gs{1} = RO.m{2}).
  move=> /> *; smt().
  inline *.
  sim.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_2025_UFCMA_genCC

Run dir: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/UFCMA_genCC/r01/2026-06-08_2025_UFCMA_genCC/iteration_1`

t=0: `2026-06-09T03:29:10.400000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 |  | 1.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 340 chars | accepted commit |  |
| T0.1-2 | +00:15 | 13.6 s | 369 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline{1} 2 | pRHL / call_site / relational_program, 1 goal, goal 768 chars | accepted commit |  |
| T0.1-3 | +00:19 | 3.7 s | 271 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit inline{2} 2 | pRHL / call_site / relational_program, 1 goal, goal 1232 chars | accepted commit |  |
| T0.1-4 | +00:35 | 15.7 s | 303 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit wp | pRHL / call_site / relational_program, 1 goal, goal 1168 chars | accepted commit |  |
| T0.1-5 | +00:41 | 5 s |  | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | unknown | pRHL / call_site / relational_program, 1 goal, goal 1072 chars | repair / unhealthy |  |
| T0.1-6 | +00:45 | 4.7 s | 268 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit call (_: ={Mem.k, Mem.log, Mem.lc} /\ StLSke.gs{1} = RO.m{2}) | pRHL / call_site / relational_program, 1 goal, goal 1072 chars | accepted commit |  |
| T0.1-7 | +00:56 | 10.6 s | 356 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 610 chars | accepted commit |  |
| T0.1-8 | +03:08 | 131.7 s | 326 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit inline{1} 1 | pRHL / call_site / relational_program, 3 goals, goal 747 chars | accepted commit |  |
| T0.1-9 | +03:14 | 5.7 s | 274 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit inline{1} 2 | pRHL / call_site / relational_program, 3 goals, goal 919 chars | accepted commit |  |
| T0.1-10 | +03:19 | 4.7 s | 279 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit inline{2} 1 | pRHL / call_site / relational_program, 3 goals, goal 1074 chars | accepted commit |  |
| T0.1-11 | +03:23 | 3.7 s | 305 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit inline{2} 2 | pRHL / call_site / relational_program, 3 goals, goal 1107 chars | accepted commit |  |
| T0.1-12 | +04:20 | 56.7 s | 320 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit wp | pRHL / call_site / relational_program, 3 goals, goal 1324 chars | accepted commit |  |
| T0.1-13 | +04:27 | 6.7 s | 298 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit sp | pRHL / call_site / relational_program, 3 goals, goal 1209 chars | accepted commit |  |
| T0.1-14 | +04:42 | 14.7 s | 296 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit inline{2} 1 | pRHL / call_site / relational_program, 3 goals, goal 1014 chars | accepted commit |  |
| T0.1-15 | +05:45 | 62.7 s | 307 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit sp | pRHL / call_site / relational_program, 3 goals, goal 2147 chars | accepted commit |  |
| T0.1-16 | +06:39 | 53.6 s | 1.4 s | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit while{2} ( (p{1} = p{2} /\ Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.lo... | pRHL / call_site / relational_program, 3 goals, goal 1852 chars | rejected commit: [error] invalid last instruction |  |
| T0.1-17 | +07:13 | 32.7 s | 292 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit seq 0 1 : ( (n{2}, a{2}, p1{2}) = p{2} /\ p{1} = p{2} /\ Mem.k{1} = M... | pRHL / call_site / failure_diagnostic, 3 goals, goal 1852 chars | accepted commit |  |
| T0.1-18 | +07:30 | 16.8 s | 243 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit while{2} ( (p{1} = p{2} /\ Mem.k{1} = Mem.k{2} /\ Mem.log{1} = Mem.lo... | pRHL / call_site / relational_program, 4 goals, goal 1733 chars | accepted commit |  |
| T0.1-19 | +08:09 | 38.7 s | 258 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit move=> &m z | phoare / procedure_body / procedure_frontier, 5 goals, goal 1090 chars | accepted commit |  |
| T0.1-20 | +08:14 | 4.8 s | 213 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit inline | phoare / procedure_body / procedure_frontier, 5 goals, goal 1442 chars | accepted commit |  |
| T0.1-21 | +08:21 | 6.8 s | 207 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit wp | phoare / procedure_body / procedure_frontier, 5 goals, goal 1866 chars | accepted commit |  |
| T0.1-22 | +08:41 | 19.8 s | 211 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit skip | phoare / procedure_body / procedure_frontier, 5 goals, goal 1355 chars | accepted commit |  |
| T0.1-23 | +10:10 | 88.7 s | 320 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit move=> &hr [[hI hne] hsz] | ambient / ambient_logic, 5 goals, goal 1265 chars | accepted commit |  |
| T0.1-24 | +15:50 | 339.7 s | 335 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit have hmerge : forall (str : block), take_xor [] str = [] by move=> str; rewrite /take_xor; sm... | ambient / ambient_logic, 5 goals, goal 1487 chars | accepted commit |  |
| T0.1-25 | +15:56 | 5.5 s | 1.5 s | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit rewrite (gen_CTR_encrypt_bytes_cons take_xor (get RO.m{hr}) k0{hr} n0... | ambient / ambient_logic, 5 goals, goal 1538 chars | rejected commit: [error] expecting a `proof-term', not a `formula' |  |
| T0.1-26 | +16:30 | 32.6 s | 1.4 s | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit rewrite (gen_CTR_encrypt_bytes_cons _ _ _ _ _ _ hmerge) in hI | ambient / ambient_logic, 5 goals, goal 1538 chars | rejected commit: [error] expecting a `proof-term', not a `formula' |  |
| T0.1-27 | +17:15 | 43.8 s | 218 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit rewrite gen_CTR_encrypt_bytes_cons in hI | ambient / ambient_logic, 5 goals, goal 1538 chars | accepted commit |  |
| T0.1-28 | +17:23 | 7.5 s | 1.5 s | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit exact hmerge | ambient / ambient_logic, 6 goals, goal 530 chars | rejected commit: [error] unknown lemma `hmerge' |  |
| T0.1-29 | +17:38 | 13.7 s | 296 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit move=> str; rewrite /take_xor; smt(take0 size_eq0) | ambient / ambient_logic, 6 goals, goal 530 chars | accepted commit |  |
| T0.1-30 | +19:09 | 90.8 s | 228 ms | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit rewrite catA in hI | ambient / ambient_logic, 5 goals, goal 1641 chars | accepted commit |  |
| T0.1-31 | +19:15 | 5.8 s | 203 ms | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit simplify | ambient / ambient_logic, 5 goals, goal 1633 chars | accepted commit |  |
| T0.1-32 | +19:23 | 7.8 s | 208 ms | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit split | ambient / ambient_logic, 5 goals, goal 1639 chars | accepted commit |  |
| T0.1-33 | +19:34 | 10.8 s | 217 ms | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | commit exact hI | ambient / ambient_logic, 6 goals, goal 1588 chars | accepted commit |  |
| T0.1-34 | +19:43 | 8.6 s | 391 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit smt(size_drop gt0_block_size size_eq0 size_ge0) | ambient / ambient_logic, 5 goals, goal 1124 chars | accepted commit |  |
| T0.1-35 | +21:15 | 91.7 s | 319 ms | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit move=> /> | pRHL / prhl_module / relational_program, 4 goals, goal 2367 chars | accepted commit |  |
| T0.1-36 | +22:00 | 44.6 s | 411 ms | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | commit move=> &1 &2 hpre hyp; smt(cat0s size_ge0 size_eq0) | ambient / ambient_logic / relational_program, 5 goals, goal 2563 chars | accepted commit |  |
| T0.1-37 | +22:43 | 42.4 s | 1.6 s | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | commit move=> &1 &2 hpre c2_R i_R p2_R | pRHL / prhl_module / relational_program, 4 goals, goal 1280 chars | rejected commit: [error] nothing to introduce |  |
| T0.1-38 | +23:30 | 45.7 s | 299 ms | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | commit skip | pRHL / prhl_module / relational_program, 4 goals, goal 1280 chars | accepted commit |  |
| T0.1-39 | +23:38 | 7.7 s | 294 ms | [turn_038.json](./views/Tree_0_1/turn_038.json) · [inline read](./views/Tree_0_1/followups/turn_038.md) | commit move=> &1 &2 hpre c2_R i_R p2_R | ambient / ambient_logic / relational_program, 4 goals, goal 958 chars | accepted commit |  |
| T0.1-40 | +23:46 | 7.6 s | 353 ms | [turn_039.json](./views/Tree_0_1/turn_039.json) · [inline read](./views/Tree_0_1/followups/turn_039.md) | commit have hnil : gen_CTR_encrypt_bytes take_xor (get RO.m{2}) Mem.k{2} n{2} i_R [] = [] by apply g... | ambient / ambient_logic / relational_program, 4 goals, goal 1216 chars | accepted commit |  |
| T0.1-41 | +23:53 | 6.1 s | 1.9 s | [turn_040.json](./views/Tree_0_1/turn_040.json) · [inline read](./views/Tree_0_1/followups/turn_040.md) | commit split; [ smt(size_ge0 size_eq0) \| smt(hnil cats0) ] | ambient / ambient_logic / relational_program, 4 goals, goal 1293 chars | rejected commit: [error] cannot find lemma `hnil' |  |
| T0.1-42 | +24:07 | 12.5 s | 475 ms | [turn_041.json](./views/Tree_0_1/turn_041.json) · [inline read](./views/Tree_0_1/followups/turn_041.md) | commit split; [ smt(size_ge0 size_eq0) \| smt(cats0) ] | ambient / ambient_logic / relational_program, 4 goals, goal 1293 chars | accepted commit |  |
| T0.1-43 | +29:39 | 331.8 s | 2.2 s | [turn_042.json](./views/Tree_0_1/turn_042.json) · [inline read](./views/Tree_0_1/followups/turn_042.md) | commit sp | pRHL / call_site / relational_program, 3 goals, goal 1134 chars | accepted commit |  |
| T0.1-44 | +29:49 | 7.7 s | 290 ms | [turn_043.json](./views/Tree_0_1/turn_043.json) · [inline read](./views/Tree_0_1/followups/turn_043.md) | commit inline{2} 1 | pRHL / call_site / relational_program, 3 goals, goal 1081 chars | accepted commit |  |
| T0.1-45 | +29:55 | 5.7 s | 319 ms | [turn_044.json](./views/Tree_0_1/turn_044.json) · [inline read](./views/Tree_0_1/followups/turn_044.md) | commit inline{2} 5 | pRHL / call_site / relational_program, 3 goals, goal 1572 chars | accepted commit |  |
| T0.1-46 | +30:52 | 56.7 s | 327 ms | [turn_045.json](./views/Tree_0_1/turn_045.json) · [inline read](./views/Tree_0_1/followups/turn_045.md) | commit inline{2} 8 | pRHL / call_site / relational_program, 3 goals, goal 1815 chars | accepted commit |  |
| T0.1-47 | +31:07 | 14.7 s | 319 ms | [turn_046.json](./views/Tree_0_1/turn_046.json) · [inline read](./views/Tree_0_1/followups/turn_046.md) | commit sp | pRHL / procedure_body / relational_program, 3 goals, goal 1916 chars | accepted commit |  |
| T0.1-48 | +31:32 | 24.7 s | 299 ms | [turn_047.json](./views/Tree_0_1/turn_047.json) · [inline read](./views/Tree_0_1/followups/turn_047.md) | commit skip | pRHL / procedure_entry / relational_program, 3 goals, goal 1439 chars | accepted commit |  |
| T0.1-49 | +32:03 | 30.8 s | 248 ms | [turn_048.json](./views/Tree_0_1/turn_048.json) · [inline read](./views/Tree_0_1/followups/turn_048.md) | commit move=> &1 &2 /> | ambient / ambient_logic / relational_program, 3 goals, goal 990 chars | accepted commit |  |
| T0.1-50 | +32:46 | 42.7 s | 310 ms | [turn_049.json](./views/Tree_0_1/turn_049.json) · [inline read](./views/Tree_0_1/followups/turn_049.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 610 chars | accepted commit |  |
| T0.1-51 | +33:17 | 30.6 s | 393 ms | [turn_050.json](./views/Tree_0_1/turn_050.json) · [inline read](./views/Tree_0_1/followups/turn_050.md) | commit auto=> />; smt() | pRHL / verification_residue / relational_program, 2 goals, goal 566 chars | accepted commit |  |
| T0.1-52 | +36:46 | 208 s |  | [turn_051.json](./views/Tree_0_1/turn_051.json) · [inline read](./views/Tree_0_1/followups/turn_051.md) | unknown | pRHL / procedure_body / relational_program, 1 goal, goal 1077 chars | repair / unhealthy |  |
| T0.1-53 | +36:53 | 7 s |  | [turn_052.json](./views/Tree_0_1/turn_052.json) · [inline read](./views/Tree_0_1/followups/turn_052.md) | unknown | pRHL / procedure_body / relational_program, 1 goal, goal 1077 chars | repair / unhealthy |  |
| T0.1-54 | +36:59 | 6.6 s | 388 ms | [turn_053.json](./views/Tree_0_1/turn_053.json) · [inline read](./views/Tree_0_1/followups/turn_053.md) | commit conseq (_: _ ==> (glob A){1} = (glob A){2} /\ (Mem.k{1} = Mem.k{2} /\... | pRHL / procedure_body / relational_program, 1 goal, goal 1077 chars | accepted commit |  |
| T0.1-55 | +37:17 | 17.7 s | 321 ms | [turn_054.json](./views/Tree_0_1/turn_054.json) · [inline read](./views/Tree_0_1/followups/turn_054.md) | commit move=> /> *; smt() | ambient / ambient_logic / relational_program, 2 goals, goal 1025 chars | accepted commit |  |
| T0.1-56 | +37:45 | 27.2 s | 5.8 s | [turn_055.json](./views/Tree_0_1/turn_055.json) · [inline read](./views/Tree_0_1/followups/turn_055.md) | commit inline * | pRHL / procedure_body / relational_program, 1 goal, goal 650 chars | accepted commit |  |
| T0.1-57 | +38:22 | 31.7 s | 253 ms | [turn_056.json](./views/Tree_0_1/turn_056.json) · [inline read](./views/Tree_0_1/followups/turn_056.md) | commit sim | pRHL / procedure_body / seq_cut, 1 goal, goal 2118 chars | accepted commit |  |
| T0.1-58 | +38:27 | 4 s |  | [turn_057.json](./views/Tree_0_1/turn_057.json) · [inline read](./views/Tree_0_1/followups/turn_057.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.1-59 | +38:30 | 3.8 s | 216 ms | [turn_058.json](./views/Tree_0_1/turn_058.json) · [inline read](./views/Tree_0_1/followups/turn_058.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-60 | +38:35 | 4 s |  | [turn_059.json](./views/Tree_0_1/turn_059.json) · [inline read](./views/Tree_0_1/followups/turn_059.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
