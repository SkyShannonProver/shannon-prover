# Agent-View Timeline — `equ_cc`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-08_1940_equ_cc |
| lemma | `equ_cc` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 62 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 16 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  sp.
  while (={c, i} /\ n{1} = n0 /\ p{2} = map (fun (_:byte) => witness<:byte>) p{1} /\ 1 <= i{1} /\ size c{1} + size p{1} <= max_cipher_size /\ (p{1} <> [] => size c{1} = (i{1} - 1) * block_size) /\ ROin.m{1} = mr0 /\ ROout.m{1} = ms0 /\ (forall (n1:nonce) (c0:C.counter), (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\ (forall (c0:C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1})).
  inline{1}.
  rcondf{1} 5.
  move=> &m; wp; skip; rewrite /SplitD.test /=; smt(C.ofintdK max_cipher_size_ok gt0_block_size size_ge0 size_eq0).
  rcondt{1} 7.
  move=> &m; auto; smt(C.ofintdK max_cipher_size_ok gt0_block_size size_ge0 size_eq0).
  sp; wp.
  rnd (fun r0 => extend p{1} +^ r0) (fun z => extend p{1} +^ z).
  skip.
  move=> &1 &2 />.
  move=> hi hsz hcsz hm1 hm2 hp1 hp2; split=> [zR _|hI r0L hr0L]; first by smt(Block.MB.addmA Block.MB.addmC Block.MB.add0m Block.addK).
  split; [by smt(Block.MB.addmA Block.MB.addmC Block.MB.add0m Block.addK) | move=> _; rewrite !get_set_sameE !oget_some !size_map].
  smt(size_cat size_take size_drop size_map size_eq0 Block.bytes_of_blockP gt0_block_size ge0_block_size size_ge0 mem_set C.ofintdK C.gt0_max_counter max_cipher_size_ok map_drop).
  skip.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc.
  sp 2 3.
  while (c{1} = c{2} /\ i{1} = i{2} /\ n{1} = n0 /\ size p{1} = size p{2} /\ 1 <= i{1} /\ size c{1} + size p{1} <= max_cipher_size /\ (p{1} = [] \/ size c{1} = (i{1} - 1) * block_size) /\ mr0 = ROin.m{1} /\ ms0 = ROout.m{1} /\ (forall (c0 : C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1}) /\ (forall (n1 : nonce) (c0 : C.counter), (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1})).
  inline{1} 1.
  inline{1} 4.
  rcondf{1} 5.
  auto => />; rewrite /SplitD.test /=; smt(C.ofintdK gt0_block_size max_cipher_size_ok C.gt0_max_counter size_eq0 size_ge0).
  inline{1} 5.
  rcondt{1} 7.
  auto => />; smt(C.ofintdK gt0_block_size max_cipher_size_ok C.gt0_max_counter size_eq0 size_ge0).
  sp 5 0.
  wp.
  rnd (fun (w : block) => extend p{1} +^ w) (fun (w : block) => extend p{1} +^ w).
  auto => />.
  move=> &1 &2 hsz hi hbnd hdisj hc1 hc2 hp1 hp2; split.
  move=> zR _; smt(Block.addK Block.MB.addmA Block.MB.add0m Block.MB.addmC).
  move=> hbij r0L hr0L; split; first by smt(Block.addK Block.MB.addmA Block.MB.add0m Block.MB.addmC).
  move=> _; rewrite !get_set_sameE /=.
  split.
  smt(Block.bytes_of_blockP mem_set size_cat size_take size_drop size_ge0 size_eq0 ge0_block_size gt0_block_size max_cipher_size_ok C.ofintdK C.gt0_max_counter).
  smt(size_drop size_eq0 size_ge0 ge0_block_size gt0_block_size).
  auto => />.
  smt(size_map size_eq0).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_1940_equ_cc

Run dir: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1`

t=0: `2026-06-09T02:40:46.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 804 chars | accepted commit |  |
| T0.0-2 | +00:47 | [45.7 s](./views/Tree_0_0/thinking/turn_002.md) | 348 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit sp | pRHL / call_site / relational_program, 1 goal, goal 3771 chars | accepted commit |  |
| T0.0-3 | +02:57 | [129.7 s](./views/Tree_0_0/thinking/turn_003.md) | 344 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit while (={c, i} /\ p{2} = map (fun (_:byte) => witness<:byte>) p{1} /\... | pRHL / call_site / relational_program, 1 goal, goal 2816 chars | accepted commit |  |
| T0.0-4 | +03:21 | [23 s](./views/Tree_0_0/thinking/turn_004.md) |  | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | inspect call_site_options | pRHL / call_site / relational_program, 2 goals, goal 2815 chars | read-only inspect |  |
| T0.0-5 | +03:32 | [11.5 s](./views/Tree_0_0/thinking/turn_005.md) | 1.5 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline{1} | pRHL / call_site / relational_program, 2 goals, goal 2815 chars | accepted commit |  |
| T0.0-6 | +04:18 | [43.8 s](./views/Tree_0_0/thinking/turn_006.md) | 247 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit rcondf{1} 5 | pRHL / procedure_body / relational_program, 2 goals, goal 5812 chars | accepted commit |  |
| T0.0-7 | +06:28 | [129.8 s](./views/Tree_0_0/thinking/turn_007.md) | 1.2 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | lookup C.ofintdK | hoare / procedure_body / procedure_frontier, 3 goals, goal 830 chars | lookup result |  |
| T0.0-8 | +07:17 | [47.8 s](./views/Tree_0_0/thinking/turn_008.md) | 4.2 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit move=> &m; wp; skip; rewrite /SplitD.test /=; smt(C.ofintdK max_cipher_size_ok gt0_block_size... | hoare / procedure_body / procedure_frontier, 3 goals, goal 830 chars | accepted commit |  |
| T0.0-9 | +08:12 | 51 s |  | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | undo_to_checkpoint | pRHL / procedure_body / seq_cut, 2 goals, goal 3260 chars | checkpoint choices requested |  |
| T0.0-10 | +08:25 | [13 s](./views/Tree_0_0/thinking/turn_010.md) |  | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | inspect checkpoints | pRHL / procedure_body / seq_cut, 2 goals, goal 3260 chars | read-only inspect |  |
| T0.0-11 | +09:01 | [36.2 s](./views/Tree_0_0/thinking/turn_011.md) | 3.8 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | undo_to_checkpoint | pRHL / procedure_body / seq_cut, 2 goals, goal 3260 chars | checkpoint rewind selected |  |
| T0.0-12 | +09:11 | 6.5 s | 1.5 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | undo_last_step | pRHL / call_site / relational_program, 2 goals, goal 2815 chars | undo result |  |
| T0.0-13 | +09:27 | [14.4 s](./views/Tree_0_0/thinking/turn_013.md) | 1.6 s | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit while (={c, i} /\ n{1} = n0 /\ p{2} = map (fun (_:byte) => witness<:b... | pRHL / call_site / relational_program, 1 goal, goal 2803 chars | accepted commit |  |
| T0.0-14 | +09:34 | [5.5 s](./views/Tree_0_0/thinking/turn_014.md) | 1.5 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit inline{1} | pRHL / call_site / relational_program, 2 goals, goal 2847 chars | accepted commit |  |
| T0.0-15 | +09:41 | [4.8 s](./views/Tree_0_0/thinking/turn_015.md) | 192 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit rcondf{1} 5 | pRHL / procedure_body / relational_program, 2 goals, goal 5844 chars | accepted commit |  |
| T0.0-16 | +09:46 | [5.7 s](./views/Tree_0_0/thinking/turn_016.md) | 4.3 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit move=> &m; wp; skip; rewrite /SplitD.test /=; smt(C.ofintdK max_cipher_size_ok gt0_block_size... | hoare / procedure_body / procedure_frontier, 3 goals, goal 851 chars | accepted commit |  |
| T0.0-17 | +10:55 | [63.8 s](./views/Tree_0_0/thinking/turn_017.md) | 225 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit rcondt{1} 7 | pRHL / procedure_body / seq_cut, 2 goals, goal 3292 chars | accepted commit |  |
| T0.0-18 | +11:23 | [27.8 s](./views/Tree_0_0/thinking/turn_018.md) | 4.2 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit move=> &m; auto; smt(C.ofintdK max_cipher_size_ok gt0_block_size size_ge0 size_eq0) | hoare / procedure_body / procedure_frontier, 3 goals, goal 856 chars | accepted commit |  |
| T0.0-19 | +11:54 | 26.7 s | 281 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit sp; wp | pRHL / procedure_body / seq_cut, 2 goals, goal 3084 chars | accepted commit |  |
| T0.0-20 | +12:49 | 54.9 s | 83 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | inspect tactic_forms | pRHL / procedure_body / relational_program, 2 goals, goal 2009 chars | read-only inspect |  |
| T0.0-21 | +13:14 | 24.7 s | 283 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit rnd (fun r0 => extend p{1} +^ r0) (fun z => extend p{1} +^ z) | pRHL / procedure_body / relational_program, 2 goals, goal 2009 chars | accepted commit |  |
| T0.0-22 | +14:36 | 82.7 s | 320 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit skip | pRHL / procedure_entry / relational_program, 2 goals, goal 2194 chars | accepted commit |  |
| T0.0-23 | +15:14 | 37.6 s | 391 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit move=> &1 &2 /> | ambient / ambient_logic / relational_program, 2 goals, goal 1843 chars | accepted commit |  |
| T0.0-24 | +17:12 | 117.3 s | 3.7 s | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | lookup Block.addmA | ambient / ambient_logic / relational_program, 2 goals, goal 2896 chars | lookup result |  |
| T0.0-25 | +17:30 | 13.9 s | 3.1 s | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | lookup Block.MB.addmA | ambient / ambient_logic / relational_program, 2 goals, goal 2896 chars | lookup result |  |
| T0.0-26 | +17:52 | 19.6 s | 4.4 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit split=> [zR _\|hI r0L hr0L]; first by smt(Block.MB.addmA Block.MB.addmC Block.MB.add0m Block.a... | ambient / ambient_logic / relational_program, 2 goals, goal 2896 chars | rejected commit: [error] cannot apply `split/None` on that goal |  |
| T0.0-27 | +18:09 | 12.2 s | 842 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit move=> hi hsz hcsz hm1 hm2 hp1 hp2; split=> [zR _\|hI r0L hr0L]; first by smt(Block.MB.addmA B... | ambient / ambient_logic / relational_program, 2 goals, goal 2896 chars | accepted commit |  |
| T0.0-28 | +19:17 | 67.6 s | 417 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit split; [by smt(Block.MB.addmA Block.MB.addmC Block.MB.add0m Block.addK) \| move=> _; rewrite !... | ambient / ambient_logic / relational_program, 2 goals, goal 2737 chars | accepted commit |  |
| T0.0-29 | +20:05 | 47.5 s | 531 ms | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit smt(size_cat size_take size_drop size_map size_eq0 Block.bytes_of_blockP gt0_block_size ge0_block_size size_ge0 mem_set C.ofintdK C.gt0_max_counter max_cipher_size_ok map_drop) | ambient / ambient_logic / relational_program, 2 goals, goal 2078 chars | accepted commit |  |
| T0.0-30 | +20:36 | 30.7 s | 302 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit skip | pRHL / prhl_module / relational_program, 1 goal, goal 2250 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +01:12 |  | 1.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 804 chars | accepted commit |  |
| T0.1-2 | +02:01 | 47 s |  | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | inspect call_site_options | pRHL / call_site / relational_program, 1 goal, goal 3771 chars | read-only inspect |  |
| T0.1-3 | +03:29 | 88.7 s | 317 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit sp 2 3 | pRHL / call_site / relational_program, 1 goal, goal 3771 chars | accepted commit |  |
| T0.1-4 | +04:23 | 53.7 s | 333 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit while (c{1} = c{2} /\ i{1} = i{2} /\ n{1} = n0 /\ size p{1} = size p{... | pRHL / call_site / relational_program, 1 goal, goal 2816 chars | accepted commit |  |
| T0.1-5 | +04:59 | 35 s |  | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | inspect call_site_options | pRHL / call_site / relational_program, 2 goals, goal 2787 chars | read-only inspect |  |
| T0.1-6 | +05:16 | 17.7 s | 342 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit inline{1} 1 | pRHL / call_site / relational_program, 2 goals, goal 2787 chars | accepted commit |  |
| T0.1-7 | +05:36 | 19.7 s | 312 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit inline{1} 4 | pRHL / call_site / relational_program, 2 goals, goal 3200 chars | accepted commit |  |
| T0.1-8 | +06:09 | 31.8 s | 249 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit rcondf{1} 5 | pRHL / call_site / relational_program, 2 goals, goal 3446 chars | accepted commit |  |
| T0.1-9 | +07:08 | 58.7 s | 1.3 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | lookup C.insubdK | hoare / procedure_body / procedure_frontier, 3 goals, goal 830 chars | lookup result |  |
| T0.1-10 | +07:55 | 46.5 s | 1.5 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | lookup C.ofintdK | hoare / procedure_body / procedure_frontier, 3 goals, goal 830 chars | lookup result |  |
| T0.1-11 | +09:05 | 68.6 s | 359 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit auto => />; rewrite /SplitD.test /=; smt(C.ofintdK gt0_block_size max_cipher_size_ok C.gt0_ma... | hoare / procedure_body / procedure_frontier, 3 goals, goal 830 chars | accepted commit |  |
| T0.1-12 | +09:24 | 17.7 s | 4.3 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit inline{1} 5 | pRHL / call_site / relational_program, 2 goals, goal 2575 chars | accepted commit |  |
| T0.1-13 | +09:57 | 28.8 s | 222 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit rcondt{1} 7 | pRHL / procedure_body / seq_cut, 2 goals, goal 3127 chars | accepted commit |  |
| T0.1-14 | +10:13 | 16.6 s | 4.4 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit auto => />; smt(C.ofintdK gt0_block_size max_cipher_size_ok C.gt0_max_counter size_eq0 size_ge0) | hoare / procedure_body / procedure_frontier, 3 goals, goal 835 chars | accepted commit |  |
| T0.1-15 | +11:41 | 83.4 s | 1.6 s | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit sp 5 0 | pRHL / procedure_body / seq_cut, 2 goals, goal 2919 chars | accepted commit |  |
| T0.1-16 | +12:01 | 17.7 s | 287 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit wp | pRHL / procedure_body / seq_cut, 2 goals, goal 2513 chars | accepted commit |  |
| T0.1-17 | +13:11 | 70.7 s | 306 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit rnd (fun (w : block) => extend p{1} +^ w) (fun (w : block) => extend... | pRHL / procedure_body / relational_program, 2 goals, goal 1844 chars | accepted commit |  |
| T0.1-18 | +14:54 | 102.6 s | 399 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit auto => /> | pRHL / procedure_entry / relational_program, 2 goals, goal 2025 chars | accepted commit |  |
| T0.1-19 | +16:07 | 71.9 s | 5.1 s | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit smt(Block.xorK1 Block.addK Block.MB.addmA Block.MB.addmC Block.MB.add0m get_setE get_set_sameE mem_set C.ofintdK C.gt0_max_counter gt0_block_size max_cipher_size_ok size_drop size_take size_cat size_eq0 size_ge0) | ambient / ambient_logic / relational_program, 2 goals, goal 2451 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-20 | +16:51 | 39.4 s | 629 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit move=> &1 &2 hsz hi hbnd hdisj hc1 hc2 hp1 hp2; split | ambient / ambient_logic / relational_program, 2 goals, goal 2451 chars | accepted commit |  |
| T0.1-21 | +17:07 | 15.1 s | 902 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit move=> zR _; smt(Block.addK Block.MB.addmA Block.MB.add0m Block.MB.addmC) | ambient / ambient_logic / relational_program, 3 goals, goal 905 chars | accepted commit |  |
| T0.1-22 | +17:30 | 22.0 s | 977 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit move=> hbij r0L hr0L; split; first by smt(Block.addK Block.MB.addmA Block.MB.add0m Block.MB.a... | ambient / ambient_logic / relational_program, 2 goals, goal 2464 chars | accepted commit |  |
| T0.1-23 | +17:50 | 19.4 s | 623 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit move=> _; rewrite !get_set_sameE /= | ambient / ambient_logic / relational_program, 2 goals, goal 2162 chars | accepted commit |  |
| T0.1-24 | +18:52 | 61.1 s | 4.9 s | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit split; last by smt(size_drop size_eq0 size_ge0) | ambient / ambient_logic / relational_program, 2 goals, goal 1805 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-25 | +19:14 | 17.7 s | 324 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit split | ambient / ambient_logic / relational_program, 2 goals, goal 1805 chars | accepted commit |  |
| T0.1-26 | +19:45 | 30.5 s | 510 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit smt(Block.bytes_of_blockP mem_set size_cat size_take size_drop size_ge0 size_eq0 ge0_block_size gt0_block_size max_cipher_size_ok C.ofintdK C.gt0_max_counter) | ambient / ambient_logic / relational_program, 3 goals, goal 1669 chars | accepted commit |  |
| T0.1-27 | +20:03 | 17.5 s | 462 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit smt(size_drop size_eq0 size_ge0 ge0_block_size gt0_block_size) | ambient / ambient_logic / relational_program, 2 goals, goal 1068 chars | accepted commit |  |
| T0.1-28 | +20:29 | 24.7 s | 296 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit auto => /> | pRHL / prhl_module / relational_program, 1 goal, goal 2193 chars | accepted commit |  |
| T0.1-29 | +20:40 | 10.7 s | 290 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit smt(size_map size_eq0) | ambient / ambient_logic, 1 goal, goal 736 chars | accepted commit |  |
| T0.1-30 | +20:42 | 2 s |  | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.1-31 | +20:47 | 4.8 s | 213 ms | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-32 | +20:51 | 4 s |  | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
