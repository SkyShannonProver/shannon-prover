# Agent-View Timeline — `equiv_step4` (resume lineage, 2 chunks)

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-11_1226_equiv_step4 |
| lemma | `equiv_step4` |
| source file | `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/source/ChaChaPoly/chacha_poly.ec` |
| model | `claude-fable-5` |
| surface profile | `l4_checked_action_surface` |
| resume chunks | 2 (c0=fresh → c1=leaf) |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns (all chunks) | 92 |

This run was built across a **resume lineage**: the proof was carried chunk0 → … → leaf via resume capsules. The committed-proof block below is the FULL `proof. … qed.` stitched across all chunks (resume boundaries marked); the timeline below has one `## c<k>` section per chunk, in order.

---

## Agent's committed proof (end-to-end across 2 resume chunks)

Reconstructed from the leaf's EasyCrypt session `history.ec` (196 accepted tactic(s); undos/rewinds already applied), split at each resume boundary. `(* ─── resume k ─── *)` marks each resume boundary.

### `Tree_0_0_r1` — proved

```easycrypt
proof.
  transitivity UFCMA2(ROIN.RO).distinguish (={glob A} ==> ={UFCMA.bad2} /\ res{1} = UF.forged{2}) (={glob A} ==> ={UFCMA.bad2, UF.forged} /\ res{2} = (UF.forged{2} \/ UFCMA.bad2{2})).
  by move=> &1 &2 ->; exists (glob A){2}.
  by smt().
  proc.
  seq 5 5 : (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m}).
  sim.
  transitivity{2} { UF.forged <- false; if (size Mem.lc <= qdec) { ns <- undup (map (fun (p:ciphertext) => p.`1) Mem.lc); Iter(Orcl).iter(ns); } } (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m} ==> ={UFCMA.bad2} /\ forged{1} = UF.forged{2}) (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m} ==> ={UFCMA.bad2, UF.forged}).
  by move=> &1 &2 />; exists UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} ROout.m{2}.
  by smt().
  sp 1 1; if.
  by move=> &1 &2 />.
  inline{2} Iter(Orcl).iter.
  inline{2} Orcl.f.
  while (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m, ns} /\ forged{1} = UF.forged{2} /\ 0 <= i{1} /\ l{2} = drop i{1} ns{2}).
  sp 1 1; if.
  by move=> &1 &2 />; smt(drop_nth).
  by inline *; auto => />; smt(drop_nth drop_drop size_drop size_eq0).
  seq 3 3 : (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m, ns} /\ forged{1} = UF.forged{2} /\ 0 <= i{1} /\ l{2} = drop i{1} ns{2} /\ i{1} < size ns{1}).
  conseq (_ : ={n, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m, ns} /\ forged{1} = UF.forged{2} /\ 0 <= i{1} /\ l{2} = drop i{1} ns{2} /\ i{1} < size ns{1} ==> _).
  by move=> &1 &2 />; smt(drop_nth).
  by inline *; auto => />; smt().
  by auto => />; smt(drop_drop size_drop size_eq0).
  by auto => />; smt(drop0 size_eq0 size_ge0).
  by auto => />.
  sp 1 1; if.
  by move=> &1 &2 />.
  sp 1 3.
  call (iter_perm Orcl _).
  proc.
  case ((t1 = t2){1}).
  by sim />.
  inline *.
  case (((t1, C.ofintd 0) \in ROout.m){1}).
  case (((t2, C.ofintd 0) \in ROout.m){1}).
  rcondt{1} 2; first by auto => />.
  rcondt{2} 2; first by auto => />.
  rcondt{1} 8; first by auto => />.
  rcondt{2} 8; first by auto => />.
  swap{2} 9 -6.
  case (((t1, C.ofintd 0) \in RO.m){1}).
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondf{1} 4; first by auto => />.
  rcondf{2} 5; first by auto => />.
  rcondf{1} 9; first by auto => />.
  rcondf{2} 9; first by auto => />.
  by auto => />; smt().
  rcondf{1} 4; first by auto => />.
  rcondt{2} 5; first by auto => />.
  rcondt{1} 9; first by auto => />.
  rcondf{2} 10; first by auto => />; smt(mem_set).
  auto => />.
  move=> &2 ne h1 h2 h3 h4 r1L _ r3L _; rewrite !get_setE /=.
  by smt().
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondt{1} 4; first by auto => />.
  rcondf{2} 5; first by auto => />.
  rcondf{1} 10; first by auto => />; smt(mem_set).
  rcondt{2} 9; first by auto => />.
  auto => />.
  move=> &2 ne h1 h2 h3 h4 r1L _ r3L _; rewrite !get_setE /=; smt().
  rcondt{1} 4; first by auto => />.
  rcondt{2} 5; first by auto => />.
  rcondt{1} 10; first by auto => />; smt(mem_set).
  rcondt{2} 10; first by auto => />; smt(mem_set).
  auto => />.
  move=> &2 ne h1 h2 h3 h4 r1L _ r3L _; (have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t2{2}, C.ofintd 0 <- r3L] = RO.m{2}.[t2{2}, C.ofintd 0 <- r3L].[t1{2}, C.ofintd 0 <- r1L] by rewrite set_setE /#); rewrite !get_setE /=; smt().
  rcondt{1} 2; first by auto => />.
  rcondf{2} 2; first by auto => />.
  rcondf{1} 8; first by auto => />.
  rcondt{2} 15; first by auto => />; smt(mem_set).
  swap{2} 16 -13.
  case (((t1, C.ofintd 0) \in RO.m){1}).
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondf{1} 4; first by auto => />.
  rcondf{2} 5; first by auto => />.
  rcondf{1} 9; first by auto => />.
  rcondf{2} 16; first by auto => />.
  by auto => />; smt().
  rcondf{1} 4; first by auto => />.
  rcondt{1} 9; first by auto => />.
  rcondt{2} 5; first by auto => />.
  rcondf{2} 17; first by auto => />; smt(mem_set).
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r1L _ r4L _ t4L _; rewrite !get_setE /=; smt().
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondt{1} 4; first by auto => />.
  rcondf{1} 10; first by auto => />; smt(mem_set).
  rcondf{2} 5; first by auto => />.
  rcondt{2} 16; first by auto => />.
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r1L _ r4L _ t4L _; rewrite !get_setE /=; smt().
  rcondt{1} 4; first by auto => />.
  rcondt{1} 10; first by auto => />; smt(mem_set).
  rcondt{2} 5; first by auto => />.
  rcondt{2} 17; first by auto => />; smt(mem_set).
  auto => />.
  move=> &2 ne h1 h2 h3 h4 r1L _ r4L _ t4L _; (have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r1L].[t2{2}, C.ofintd 0 <- r4L] = RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r1L] by rewrite set_setE /#); rewrite !get_setE /=; smt().
  case (((t2, C.ofintd 0) \in ROout.m){1}).
  rcondf{1} 2; first by auto => />.
  rcondt{2} 2; first by auto => />.
  rcondt{1} 15; first by auto => />; smt(mem_set).
  rcondf{2} 8; first by auto => />.
  swap{1} 16 -13.
  case (((t1, C.ofintd 0) \in RO.m){1}).
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondf{1} 5; first by auto => />.
  rcondf{2} 4; first by auto => />.
  rcondf{2} 9; first by auto => />.
  rcondf{1} 16; first by auto => />.
  by auto => />; smt().
  rcondf{1} 5; first by auto => />.
  rcondt{1} 16; first by auto => />.
  rcondt{2} 4; first by auto => />.
  rcondf{2} 10; first by auto => />; smt(mem_set).
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r3L _ r2L _ t3L _; rewrite !get_setE /=; smt().
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondt{1} 5; first by auto => />.
  rcondf{1} 17; first by auto => />; smt(mem_set).
  rcondf{2} 4; first by auto => />.
  rcondt{2} 9; first by auto => />.
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r3L _ r2L _ t3L _; rewrite !get_setE /=; smt().
  rcondt{1} 5; first by auto => />.
  rcondt{2} 4; first by auto => />.
  rcondt{1} 17; first by auto => />; smt(mem_set).
  rcondt{2} 10; first by auto => />; smt(mem_set).
  auto => />.
  move=> &2 ne h1 h2 h3 h4 r3L _ r2L _ t3L _; (have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <- r3L] = RO.m{2}.[t2{2}, C.ofintd 0 <- r3L].[t1{2}, C.ofintd 0 <- r2L] by rewrite set_setE /#); rewrite !get_setE /=; smt().
  rcondf{1} 2; first by auto => />.
  rcondf{2} 2; first by auto => />.
  rcondf{1} 15; first by auto => />; smt(mem_set).
  rcondf{2} 15; first by auto => />; smt(mem_set).
  swap{1} 16 -13.
  swap{1} 20 -16.
  case (((t1, C.ofintd 0) \in RO.m){1}).
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondf{1} 6; first by auto => />.
  rcondf{2} 4; first by auto => />.
  rcondf{1} 17; first by auto => />.
  rcondf{2} 16; first by auto => />.
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; rewrite set_setE /#.
  rcondf{1} 6; first by auto => />.
  rcondt{1} 17; first by auto => />.
  rcondt{2} 4; first by auto => />.
  rcondf{2} 17; first by auto => />; smt(mem_set).
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; rewrite !get_setE set_setE /=; smt().
  case (((t2, C.ofintd 0) \in RO.m){1}).
  rcondt{1} 6; first by auto => />.
  rcondf{1} 18; first by auto => />; smt(mem_set).
  rcondf{2} 4; first by auto => />.
  rcondt{2} 16; first by auto => />.
  auto => />.
  by move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; rewrite !get_setE set_setE /=; smt().
  rcondt{1} 6; first by auto => />.
  rcondt{1} 18; first by auto => />; smt(mem_set).
  rcondt{2} 4; first by auto => />.
  rcondt{2} 17; first by auto => />; smt(mem_set).
  auto => />.
  move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _.
  have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <- r4L] = RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L] by rewrite set_setE /#.
  have ->: SplitC2.I2.RO.m{2}.[t1{2}, C.ofintd 0 <- witness<:poly_out>].[t2{2}, C.ofintd 0 <- witness<:poly_out>] = SplitC2.I2.RO.m{2}.[t2{2}, C.ofintd 0 <- witness<:poly_out>].[t1{2}, C.ofintd 0 <- witness<:poly_out>] by rewrite set_setE /#.
  by rewrite !get_setE /=; smt().
  auto => />.
  by move=> &2 _; rewrite perm_eq_sym; apply (perm_filterC (fun (n : nonce) => (n, C.ofintd 0) \in SplitC2.I2.RO.m{2}) (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}))).
  by auto => />.
  proc.
  seq 5 5 : (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m}).
  sim.
  sp 1 1; if.
  by move=> &1 &2 />.
  sp 3 3.
  transitivity{1} { Iter(Orcl).iters(ns1, ns2); } (={ns1, ns2, UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m} ==> ={UF.forged, UFCMA.bad2}) (={ns1, ns2, UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m} /\ uniq ns2{2} /\ (forall n0, n0 \in ns1{2} => (n0, C.ofintd 0) \in ROout.m{2}) /\ (forall n0, n0 \in ns2{2} => (n0, C.ofintd 0) \notin ROout.m{2}) ==> ={UF.forged, UFCMA.bad2}).
  move=> &1 &2 [#] hns2 hns12 hns22 hns1 hns11 hns21 hf2 hf1 hb hc hl hlc hr ho hsz.
  (have ens: ns{1} = ns{2} by rewrite hns1 hns2 hlc); (have ens1: ns1{1} = ns1{2} by rewrite hns11 hns12 ho ens); (have ens2: ns2{1} = ns2{2} by rewrite hns21 hns22 ho ens); exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} ROout.m{2} ns1{2} ns2{2}; rewrite ens1 ens2 hf1 hf2 hb hc hl hlc hr ho /=; rewrite hns22 hns12 hns2; split; [by apply/filter_uniq/undup_uniq | split; [by move=> n0; rewrite mem_filter /= => -[] | by move=> n0; rewrite mem_filter /= => -[]]].
  by smt().
  by call (iter_cat Orcl); auto => />.
  inline{1} Iter(Orcl).iters Iter(Orcl).iter.
  while (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m} /\ l0{1} = drop i{2} ns2{2} /\ 0 <= i{2} /\ uniq l0{1} /\ (forall n0, n0 \in l0{1} => (n0, C.ofintd 0) \notin ROout.m{1})).
  inline{1} Orcl.f.
  rcondf{1} 2; first by auto => />; smt(head_behead).
  inline *.
  (* ─── resume 1: replayed 184 tactic(s) above, continued below ─── *)
  auto => />.
  move=> &1 &2 hge huniq hout hne hlt; have hhd : head witness<:nonce> (drop i{2} ns2{2}) = nth witness<:nonce> ns2{2} i{2} by smt(drop_nth head_cons); rewrite hhd /=; smt(drop_nth drop_drop drop0 mem_drop mem_set cons_uniq size_drop size_eq0).
  rewrite hhd /=.
  smt(drop_nth drop_drop cons_uniq in_cons mem_set size_drop size_eq0).
  sp 3 1; wp; while (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m, ns1, ns2} /\ l2{1} = ns2{2} /\ l{1} = drop i{2} ns1{2} /\ 0 <= i{2} /\ uniq ns2{2} /\ (forall (n0 : nonce), n0 \in ns1{2} => (n0, C.ofintd 0) \in ROout.m{2}) /\ (forall (n0 : nonce), n0 \in ns2{2} => (n0, C.ofintd 0) \notin ROout.m{2})).
  inline{1} Orcl.f.
  rcondt{1} 2.
  by auto => />; smt(head_behead mem_head mem_drop).
  by inline *; auto => />; smt(drop_nth head_cons drop_drop size_drop size_eq0 get_setE).
  by auto => />; smt(drop0 size_eq0 size_ge0).
  by auto => />.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## c0

Run dir: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1`

t=0: `2026-06-11T15:08:25+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/c0/Tree_0_0/thinking/turn_001.md) | 21 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit rcondt{1} 5; first by auto => /> | pRHL / procedure_body / relational_program, 5 goals, goal 5360 chars | accepted commit |  |
| T0.0-2 | +00:28 | [7.1 s](./views/c0/Tree_0_0/thinking/turn_002.md) | 16.9 s | [turn_001.json](./views/c0/Tree_0_0/turn_001.json) · [inline read](./views/c0/Tree_0_0/followups/turn_001.md) | commit rcondt{2} 4; first by auto => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 5198 chars | accepted commit |  |
| T0.0-3 | +00:53 | [8.1 s](./views/c0/Tree_0_0/thinking/turn_003.md) | 21.9 s | [turn_002.json](./views/c0/Tree_0_0/turn_002.json) · [inline read](./views/c0/Tree_0_0/followups/turn_002.md) | commit rcondt{1} 17; first by auto => />; smt(mem_set) | pRHL / procedure_body / relational_program, 5 goals, goal 5036 chars | accepted commit |  |
| T0.0-4 | +01:21 | 6.1 s | 17.9 s | [turn_003.json](./views/c0/Tree_0_0/turn_003.json) · [inline read](./views/c0/Tree_0_0/followups/turn_003.md) | commit rcondt{2} 10; first by auto => />; smt(mem_set) | pRHL / procedure_body / seq_cut, 5 goals, goal 4874 chars | accepted commit |  |
| T0.0-5 | +01:48 | [8.6 s](./views/c0/Tree_0_0/thinking/turn_005.md) | 378 ms | [turn_004.json](./views/c0/Tree_0_0/turn_004.json) · [inline read](./views/c0/Tree_0_0/followups/turn_004.md) | commit auto => /> | pRHL / procedure_body / relational_program, 5 goals, goal 4628 chars | accepted commit |  |
| T0.0-6 | +02:04 | 16.5 s | 5.5 s | [turn_005.json](./views/c0/Tree_0_0/turn_005.json) · [inline read](./views/c0/Tree_0_0/followups/turn_005.md) | commit move=> &2 ne h1 h2 h3 h4 r3L _ r2L _ t3L _; (have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{... | ambient / ambient_logic, 5 goals, goal 1779 chars | accepted commit |  |
| T0.0-7 | +03:06 | 56 s | 10 s | [turn_006.json](./views/c0/Tree_0_0/turn_006.json) · [inline read](./views/c0/Tree_0_0/followups/turn_006.md) | commit rcondf{1} 2; first by auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 8333 chars | accepted commit |  |
| T0.0-8 | +03:22 | 5.7 s | 5.3 s | [turn_007.json](./views/c0/Tree_0_0/turn_007.json) · [inline read](./views/c0/Tree_0_0/followups/turn_007.md) | commit rcondf{2} 2; first by auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 13522 chars | accepted commit |  |
| T0.0-9 | +03:38 | 10.7 s | 5.3 s | [turn_008.json](./views/c0/Tree_0_0/turn_008.json) · [inline read](./views/c0/Tree_0_0/followups/turn_008.md) | commit rcondf{1} 15; first by auto => />; smt(mem_set) | pRHL / procedure_body / relational_program, 4 goals, goal 6912 chars | accepted commit |  |
| T0.0-10 | +03:51 | 8.5 s | 536 ms | [turn_009.json](./views/c0/Tree_0_0/turn_009.json) · [inline read](./views/c0/Tree_0_0/followups/turn_009.md) | commit rcondf{2} 15; first by auto => />; smt(mem_set) | pRHL / procedure_body / relational_program, 4 goals, goal 9028 chars | accepted commit |  |
| T0.0-11 | +04:23 | 30.9 s | 16.1 s | [turn_010.json](./views/c0/Tree_0_0/turn_010.json) · [inline read](./views/c0/Tree_0_0/followups/turn_010.md) | commit swap{1} 16 -13 | pRHL / procedure_body / relational_program, 4 goals, goal 5569 chars | accepted commit |  |
| T0.0-12 | +04:46 | [6.6 s](./views/c0/Tree_0_0/thinking/turn_012.md) | 31.4 s | [turn_011.json](./views/c0/Tree_0_0/turn_011.json) · [inline read](./views/c0/Tree_0_0/followups/turn_011.md) | commit swap{1} 20 -16 | pRHL / procedure_body / relational_program, 4 goals, goal 6548 chars | accepted commit |  |
| T0.0-13 | +05:31 | 14.4 s | 30.6 s | [turn_012.json](./views/c0/Tree_0_0/turn_012.json) · [inline read](./views/c0/Tree_0_0/followups/turn_012.md) | commit case (((t1, C.ofintd 0) \in RO.m){1}) | pRHL / procedure_body / relational_program, 4 goals, goal 7438 chars | accepted commit |  |
| T0.0-14 | +06:09 | 6.9 s | 31.1 s | [turn_013.json](./views/c0/Tree_0_0/turn_013.json) · [inline read](./views/c0/Tree_0_0/followups/turn_013.md) | commit case (((t2, C.ofintd 0) \in RO.m){1}) | pRHL / procedure_body / relational_program, 5 goals, goal 7487 chars | accepted commit |  |
| T0.0-15 | +08:40 | 120.1 s | 34.9 s | [turn_014.json](./views/c0/Tree_0_0/turn_014.json) · [inline read](./views/c0/Tree_0_0/followups/turn_014.md) | commit rcondf{1} 6; first by auto => /> | pRHL / procedure_body / relational_program, 6 goals, goal 7537 chars | accepted commit |  |
| T0.0-16 | +09:24 | 8.9 s | 31.1 s | [turn_015.json](./views/c0/Tree_0_0/turn_015.json) · [inline read](./views/c0/Tree_0_0/followups/turn_015.md) | commit rcondf{2} 4; first by auto => /> | pRHL / procedure_body / seq_cut, 6 goals, goal 6647 chars | accepted commit |  |
| T0.0-17 | +10:06 | 11.4 s | 36.6 s | [turn_016.json](./views/c0/Tree_0_0/turn_016.json) · [inline read](./views/c0/Tree_0_0/followups/turn_016.md) | commit rcondf{1} 17; first by auto => /> | pRHL / procedure_body / relational_program, 6 goals, goal 7092 chars | accepted commit |  |
| T0.0-18 | +10:50 | 7.3 s | 31.7 s | [turn_017.json](./views/c0/Tree_0_0/turn_017.json) · [inline read](./views/c0/Tree_0_0/followups/turn_017.md) | commit rcondf{2} 16; first by auto => /> | pRHL / procedure_body / seq_cut, 6 goals, goal 6380 chars | accepted commit |  |
| T0.0-19 | +11:33 | 10.6 s | 40.4 s | [turn_018.json](./views/c0/Tree_0_0/turn_018.json) · [inline read](./views/c0/Tree_0_0/followups/turn_018.md) | commit by auto => />; smt() | pRHL / procedure_body / relational_program, 6 goals, goal 6527 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-20 | +12:27 | 14.4 s | 617 ms | [turn_019.json](./views/c0/Tree_0_0/turn_019.json) · [inline read](./views/c0/Tree_0_0/followups/turn_019.md) | commit auto => /> | pRHL / procedure_body / relational_program, 6 goals, goal 6527 chars | accepted commit |  |
| T0.0-21 | +12:47 | 19.2 s | 36.8 s | [turn_020.json](./views/c0/Tree_0_0/turn_020.json) · [inline read](./views/c0/Tree_0_0/followups/turn_020.md) | commit by move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; rewrite set_setE /# | ambient / ambient_logic, 6 goals, goal 2018 chars | accepted commit |  |
| T0.0-22 | +13:41 | 16.9 s | 40.1 s | [turn_021.json](./views/c0/Tree_0_0/turn_021.json) · [inline read](./views/c0/Tree_0_0/followups/turn_021.md) | commit rcondf{1} 6; first by auto => /> | pRHL / procedure_body / relational_program, 5 goals, goal 7540 chars | accepted commit |  |
| T0.0-23 | +14:30 | 9 s | 38 s | [turn_022.json](./views/c0/Tree_0_0/turn_022.json) · [inline read](./views/c0/Tree_0_0/followups/turn_022.md) | commit rcondt{1} 17; first by auto => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 6650 chars | accepted commit |  |
| T0.0-24 | +15:15 | 7.2 s | 40.8 s | [turn_023.json](./views/c0/Tree_0_0/turn_023.json) · [inline read](./views/c0/Tree_0_0/followups/turn_023.md) | commit rcondt{2} 4; first by auto => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 6650 chars | accepted commit |  |
| T0.0-25 | +16:03 | 7.2 s | 35.8 s | [turn_024.json](./views/c0/Tree_0_0/turn_024.json) · [inline read](./views/c0/Tree_0_0/followups/turn_024.md) | commit rcondf{2} 17; first by auto => />; smt(mem_set) | pRHL / procedure_body / seq_cut, 5 goals, goal 6472 chars | accepted commit |  |
| T0.0-26 | +16:58 | 18.6 s | 390 ms | [turn_025.json](./views/c0/Tree_0_0/turn_025.json) · [inline read](./views/c0/Tree_0_0/followups/turn_025.md) | commit auto => /> | pRHL / procedure_body / relational_program, 5 goals, goal 6617 chars | accepted commit |  |
| T0.0-27 | +17:15 | 17.3 s | 35.7 s | [turn_026.json](./views/c0/Tree_0_0/turn_026.json) · [inline read](./views/c0/Tree_0_0/followups/turn_026.md) | commit by move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; rewrite !get_setE set_setE /=; smt() | ambient / ambient_logic, 5 goals, goal 2227 chars | accepted commit |  |
| T0.0-28 | +18:03 | 12 s | 36 s | [turn_027.json](./views/c0/Tree_0_0/turn_027.json) · [inline read](./views/c0/Tree_0_0/followups/turn_027.md) | commit case (((t2, C.ofintd 0) \in RO.m){1}) | pRHL / procedure_body / relational_program, 4 goals, goal 7490 chars | accepted commit |  |
| T0.0-29 | +18:49 | 10.1 s | 38.9 s | [turn_028.json](./views/c0/Tree_0_0/turn_028.json) · [inline read](./views/c0/Tree_0_0/followups/turn_028.md) | commit rcondt{1} 6; first by auto => /> | pRHL / procedure_body / relational_program, 5 goals, goal 7540 chars | accepted commit |  |
| T0.0-30 | +19:34 | 6.1 s | 37.9 s | [turn_029.json](./views/c0/Tree_0_0/turn_029.json) · [inline read](./views/c0/Tree_0_0/followups/turn_029.md) | commit rcondf{1} 18; first by auto => />; smt(mem_set) | pRHL / procedure_body / seq_cut, 5 goals, goal 7362 chars | accepted commit |  |
| T0.0-31 | +20:19 | 6.9 s | 37.1 s | [turn_030.json](./views/c0/Tree_0_0/turn_030.json) · [inline read](./views/c0/Tree_0_0/followups/turn_030.md) | commit rcondf{2} 4; first by auto => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 6650 chars | accepted commit |  |
| T0.0-32 | +22:19 | 83.2 s | 41.8 s | [turn_031.json](./views/c0/Tree_0_0/turn_031.json) · [inline read](./views/c0/Tree_0_0/followups/turn_031.md) | commit rcondf{2} 4; first by auto => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 6917 chars | rejected commit: [error] the targetted instruction is not a conditionnal |  |
| T0.0-33 | +23:11 | 10.4 s | 31.6 s | [turn_032.json](./views/c0/Tree_0_0/turn_032.json) · [inline read](./views/c0/Tree_0_0/followups/turn_032.md) | commit rcondt{2} 16; first by auto => /> | pRHL / procedure_body / seq_cut, 5 goals, goal 6917 chars | accepted commit |  |
| T0.0-34 | +23:52 | 8.6 s | 380 ms | [turn_033.json](./views/c0/Tree_0_0/turn_033.json) · [inline read](./views/c0/Tree_0_0/followups/turn_033.md) | commit auto => /> | pRHL / procedure_body / relational_program, 5 goals, goal 6617 chars | accepted commit |  |
| T0.0-35 | +24:08 | 16.3 s | 32.7 s | [turn_034.json](./views/c0/Tree_0_0/turn_034.json) · [inline read](./views/c0/Tree_0_0/followups/turn_034.md) | commit by move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; rewrite !get_setE set_setE /=; smt() | ambient / ambient_logic, 5 goals, goal 2227 chars | accepted commit |  |
| T0.0-36 | +25:04 | 23 s | 40 s | [turn_035.json](./views/c0/Tree_0_0/turn_035.json) · [inline read](./views/c0/Tree_0_0/followups/turn_035.md) | commit rcondt{1} 6; first by auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 7543 chars | accepted commit |  |
| T0.0-37 | +25:52 | 8 s | 41 s | [turn_036.json](./views/c0/Tree_0_0/turn_036.json) · [inline read](./views/c0/Tree_0_0/followups/turn_036.md) | commit rcondt{1} 18; first by auto => />; smt(mem_set) | pRHL / procedure_body / seq_cut, 4 goals, goal 7365 chars | accepted commit |  |
| T0.0-38 | +26:40 | 7.3 s | 39.7 s | [turn_037.json](./views/c0/Tree_0_0/turn_037.json) · [inline read](./views/c0/Tree_0_0/followups/turn_037.md) | commit rcondt{2} 4; first by auto => /> | pRHL / procedure_body / seq_cut, 4 goals, goal 7187 chars | accepted commit |  |
| T0.0-39 | +27:26 | 6.5 s | 34.5 s | [turn_038.json](./views/c0/Tree_0_0/turn_038.json) · [inline read](./views/c0/Tree_0_0/followups/turn_038.md) | commit rcondt{2} 17; first by auto => />; smt(mem_set) | pRHL / procedure_body / seq_cut, 4 goals, goal 7009 chars | accepted commit |  |
| T0.0-40 | +28:11 | 9.6 s | 402 ms | [turn_039.json](./views/c0/Tree_0_0/turn_039.json) · [inline read](./views/c0/Tree_0_0/followups/turn_039.md) | commit auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 6707 chars | accepted commit |  |
| T0.0-41 | +28:29 | 17.7 s | 16.3 s | [turn_040.json](./views/c0/Tree_0_0/turn_040.json) · [inline read](./views/c0/Tree_0_0/followups/turn_040.md) | commit move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; (have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L... | ambient / ambient_logic, 4 goals, goal 2513 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-42 | +29:22 | 36.7 s | 306 ms | [turn_041.json](./views/c0/Tree_0_0/turn_041.json) · [inline read](./views/c0/Tree_0_0/followups/turn_041.md) | commit move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _ | ambient / ambient_logic, 4 goals, goal 2513 chars | accepted commit |  |
| T0.0-43 | +29:32 | 9.7 s | 323 ms | [turn_042.json](./views/c0/Tree_0_0/turn_042.json) · [inline read](./views/c0/Tree_0_0/followups/turn_042.md) | commit have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <- r4L... | ambient / ambient_logic, 4 goals, goal 2020 chars | accepted commit |  |
| T0.0-44 | +29:51 | 18.6 s | 352 ms | [turn_043.json](./views/c0/Tree_0_0/turn_043.json) · [inline read](./views/c0/Tree_0_0/followups/turn_043.md) | commit have ->: SplitC2.I2.RO.m{2}.[t1{2}, C.ofintd 0 <- witness<:poly_out>]... | ambient / ambient_logic, 4 goals, goal 2020 chars | accepted commit |  |
| T0.0-45 | +30:07 | 16.5 s | 533 ms | [turn_044.json](./views/c0/Tree_0_0/turn_044.json) · [inline read](./views/c0/Tree_0_0/followups/turn_044.md) | commit by rewrite !get_setE /=; smt() | ambient / ambient_logic, 4 goals, goal 2020 chars | accepted commit |  |
| T0.0-46 | +30:28 | 19.7 s | 342 ms | [turn_045.json](./views/c0/Tree_0_0/turn_045.json) · [inline read](./views/c0/Tree_0_0/followups/turn_045.md) | commit auto => /> | pRHL / verification_residue / relational_program, 3 goals, goal 1557 chars | accepted commit |  |
| T0.0-47 | +30:43 | 14.7 s | 1.3 s | [turn_046.json](./views/c0/Tree_0_0/turn_046.json) · [inline read](./views/c0/Tree_0_0/followups/turn_046.md) | lookup perm_filterC | ambient / ambient_logic, 3 goals, goal 517 chars | lookup result |  |
| T0.0-48 | +31:04 | 20.2 s | 795 ms | [turn_047.json](./views/c0/Tree_0_0/turn_047.json) · [inline read](./views/c0/Tree_0_0/followups/turn_047.md) | commit by move=> &2 _; rewrite perm_eq_sym; apply (perm_filterC (fun (n : nonce) => (n, C.ofintd 0)... | ambient / ambient_logic, 3 goals, goal 517 chars | accepted commit |  |

### Tree-0.0.r2

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0.r2-1 | +1:01:07 | [think](./views/c0/Tree_0_0_r2/thinking/turn_001.md) | 358 ms | [manager_bootstrap_0_0_r2.json](./views/_bootstrap/manager_bootstrap_0_0_r2.json) | commit by auto => /> | pRHL / verification_residue / relational_program, 2 goals, goal 606 chars | accepted commit |  |
| T0.0.r2-2 | +1:01:19 | [12 s](./views/c0/Tree_0_0_r2/thinking/turn_002.md) | 7 s | [turn_001.json](./views/c0/Tree_0_0_r2/turn_001.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 328 chars | accepted commit |  |
| T0.0.r2-3 | +1:01:36 | [9.6 s](./views/c0/Tree_0_0_r2/thinking/turn_003.md) | 365 ms | [turn_002.json](./views/c0/Tree_0_0_r2/turn_002.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_002.md) | commit seq 5 5 : (={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m}) | pRHL / call_site / seq_cut, 1 goal, goal 5920 chars | accepted commit |  |
| T0.0.r2-4 | +1:01:42 | 5.6 s | 413 ms | [turn_003.json](./views/c0/Tree_0_0_r2/turn_003.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_003.md) | commit sim | pRHL / call_site / relational_program, 2 goals, goal 1065 chars | accepted commit |  |
| T0.0.r2-5 | +1:02:38 | 55.7 s | 1.3 s | [turn_004.json](./views/c0/Tree_0_0_r2/turn_004.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_004.md) | lookup iter_cat | pRHL / call_site / relational_program, 1 goal, goal 5322 chars | lookup result |  |
| T0.0.r2-6 | +1:04:37 | 117.6 s | 378 ms | [turn_005.json](./views/c0/Tree_0_0_r2/turn_005.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_005.md) | commit sp 1 1; if | pRHL / call_site / relational_program, 1 goal, goal 5322 chars | accepted commit |  |
| T0.0.r2-7 | +1:04:45 | 7.6 s | 400 ms | [turn_006.json](./views/c0/Tree_0_0_r2/turn_006.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_006.md) | commit by move=> &1 &2 /> | ambient / ambient_logic / relational_program, 3 goals, goal 436 chars | accepted commit |  |
| T0.0.r2-8 | +1:04:56 | [10.6 s](./views/c0/Tree_0_0_r2/thinking/turn_008.md) | 390 ms | [turn_007.json](./views/c0/Tree_0_0_r2/turn_007.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_007.md) | commit sp 3 3 | pRHL / call_site / relational_program, 2 goals, goal 4857 chars | accepted commit |  |
| T0.0.r2-9 | +1:05:27 | 31 s |  | [turn_008.json](./views/c0/Tree_0_0_r2/turn_008.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_008.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 3674 chars | repair / unhealthy |  |
| T0.0.r2-10 | +1:05:38 | [10.6 s](./views/c0/Tree_0_0_r2/thinking/turn_010.md) | 352 ms | [turn_009.json](./views/c0/Tree_0_0_r2/turn_009.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_009.md) | commit transitivity{1} { Iter(Orcl).iters(ns1, ns2); } (={ns1, ns2, UF.forged, UFCMA.bad2, UFCMA.cba... | pRHL / call_site / relational_program, 2 goals, goal 3674 chars | accepted commit |  |
| T0.0.r2-11 | +1:05:56 | [17.9 s](./views/c0/Tree_0_0_r2/thinking/turn_011.md) | 6.1 s | [turn_010.json](./views/c0/Tree_0_0_r2/turn_010.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_010.md) | commit by move=> &1 &2 />; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem... | ambient / ambient_logic / relational_program, 5 goals, goal 1735 chars | rejected commit: [error] not an existential |  |
| T0.0.r2-12 | +1:06:18 | [15.8 s](./views/c0/Tree_0_0_r2/thinking/turn_012.md) | 9.2 s | [turn_011.json](./views/c0/Tree_0_0_r2/turn_011.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_011.md) | commit by move=> &1 &2 H; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.... | ambient / ambient_logic / relational_program, 5 goals, goal 1735 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-13 | +1:07:54 | [86.7 s](./views/c0/Tree_0_0_r2/thinking/turn_013.md) | 344 ms | [turn_012.json](./views/c0/Tree_0_0_r2/turn_012.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_012.md) | commit move=> &1 &2 [#] hns2 hns12 hns22 hns1 hns11 hns21 hf2 hf1 hb hc hl h... | ambient / ambient_logic / relational_program, 5 goals, goal 1735 chars | accepted commit |  |
| T0.0.r2-14 | +1:08:37 | [42.7 s](./views/c0/Tree_0_0_r2/thinking/turn_014.md) | 329 ms | [turn_013.json](./views/c0/Tree_0_0_r2/turn_013.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_013.md) | commit (have ens: ns{1} = ns{2} by rewrite hns1 hns2 hlc); (have ens1: ns1{1} = ns1{2} by rewrite hn... | ambient / ambient_logic / relational_program, 5 goals, goal 1844 chars | accepted commit |  |
| T0.0.r2-15 | +1:08:44 | [6.6 s](./views/c0/Tree_0_0_r2/thinking/turn_015.md) | 358 ms | [turn_014.json](./views/c0/Tree_0_0_r2/turn_014.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_014.md) | commit by smt() | ambient / ambient_logic / relational_program, 4 goals, goal 423 chars | accepted commit |  |
| T0.0.r2-16 | +1:09:01 | [16.6 s](./views/c0/Tree_0_0_r2/thinking/turn_016.md) | 394 ms | [turn_015.json](./views/c0/Tree_0_0_r2/turn_015.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_015.md) | commit by call (iter_cat Orcl); auto => /> | pRHL / procedure_body / relational_program, 3 goals, goal 630 chars | accepted commit |  |
| T0.0.r2-17 | +1:10:12 | 70.6 s | 387 ms | [turn_016.json](./views/c0/Tree_0_0_r2/turn_016.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_016.md) | commit inline{1} Iter(Orcl).iters Iter(Orcl).iter | pRHL / call_site / relational_program, 2 goals, goal 3273 chars | accepted commit |  |
| T0.0.r2-18 | +1:10:31 | 19 s |  | [turn_017.json](./views/c0/Tree_0_0_r2/turn_017.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_017.md) | inspect call_site_options | pRHL / call_site / relational_program, 2 goals, goal 3959 chars | read-only inspect |  |
| T0.0.r2-19 | +1:10:42 | 10.8 s | 1.2 s | [turn_018.json](./views/c0/Tree_0_0_r2/turn_018.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_018.md) | lookup Orcl | pRHL / call_site / relational_program, 2 goals, goal 3959 chars | lookup result |  |
| T0.0.r2-20 | +1:12:22 | 98.6 s | 386 ms | [turn_019.json](./views/c0/Tree_0_0_r2/turn_019.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_019.md) | commit while (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m}... | pRHL / call_site / relational_program, 2 goals, goal 3959 chars | accepted commit |  |
| T0.0.r2-21 | +1:12:29 | 6.9 s | 6.1 s | [turn_020.json](./views/c0/Tree_0_0_r2/turn_020.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_020.md) | commit inline{1} Orcl.f | pRHL / call_site / relational_program, 3 goals, goal 2413 chars | accepted commit |  |
| T0.0.r2-22 | +1:12:47 | 11.8 s | 12.2 s | [turn_021.json](./views/c0/Tree_0_0_r2/turn_021.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_021.md) | commit rcondf{1} 2; first by auto => />; smt(head_mem) | pRHL / call_site / relational_program, 3 goals, goal 5273 chars | rejected commit: [error] cannot find lemma `head_mem' |  |
| T0.0.r2-23 | +1:13:10 | 11.3 s | 6.7 s | [turn_022.json](./views/c0/Tree_0_0_r2/turn_022.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_022.md) | commit rcondf{1} 2; first by auto => />; smt(head_behead) | pRHL / call_site / relational_program, 3 goals, goal 5273 chars | accepted commit |  |
| T0.0.r2-24 | +1:13:58 | 40.7 s | 1.3 s | [turn_023.json](./views/c0/Tree_0_0_r2/turn_023.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_023.md) | lookup UFCMA.set_bad2 | pRHL / call_site / seq_cut, 3 goals, goal 2965 chars | lookup result |  |
| T0.0.r2-25 | +1:15:04 | 64.8 s | 6.2 s | [turn_024.json](./views/c0/Tree_0_0_r2/turn_024.json) · [inline read](./views/c0/Tree_0_0_r2/followups/turn_024.md) | commit inline * | pRHL / call_site / seq_cut, 3 goals, goal 2965 chars | accepted commit |  |

## c1

Run dir: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1`

t=0: `2026-06-11T19:55:51.700000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 |  | 15.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit by auto => />; smt(drop_nth drop_drop size_drop size_eq0 mem_set head_behead) | pRHL / procedure_body / seq_cut, 3 goals, goal 3479 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-2 | +00:51 | 35.5 s | 539 ms | [turn_001.json](./views/c1/Tree_0_0/turn_001.json) · [inline read](./views/c1/Tree_0_0/followups/turn_001.md) | commit auto => /> | pRHL / procedure_body / seq_cut, 3 goals, goal 3479 chars | accepted commit |  |
| T0.0-3 | +01:19 | 27.5 s | 9.5 s | [turn_002.json](./views/c1/Tree_0_0/turn_002.json) · [inline read](./views/c1/Tree_0_0/followups/turn_002.md) | commit move=> &1 &2 hge huniq hout hne hlt; rewrite (drop_nth witness) 1:/# /=; smt(mem_set get_setE... | ambient / ambient_logic / relational_program, 3 goals, goal 7456 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-4 | +02:37 | 68.6 s | 429 ms | [turn_003.json](./views/c1/Tree_0_0/turn_003.json) · [inline read](./views/c1/Tree_0_0/followups/turn_003.md) | commit move=> &1 &2 hge huniq hout hne hlt; have hhd : head witness<:nonce> (drop i{2} ns2{2}) = nth... | ambient / ambient_logic / relational_program, 3 goals, goal 7456 chars | accepted commit |  |
| T0.0-5 | +03:03 | 25.6 s | 384 ms | [turn_004.json](./views/c1/Tree_0_0/turn_004.json) · [inline read](./views/c1/Tree_0_0/followups/turn_004.md) | commit rewrite hhd /= | ambient / ambient_logic / relational_program, 3 goals, goal 7452 chars | accepted commit |  |
| T0.0-6 | +03:31 | 27.5 s | 546 ms | [turn_005.json](./views/c1/Tree_0_0/turn_005.json) · [inline read](./views/c1/Tree_0_0/followups/turn_005.md) | commit smt(drop_nth drop_drop cons_uniq in_cons mem_set size_drop size_eq0) | ambient / ambient_logic / relational_program, 3 goals, goal 5268 chars | accepted commit |  |
| T0.0-7 | +05:00 | 88.6 s | 377 ms | [turn_006.json](./views/c1/Tree_0_0/turn_006.json) · [inline read](./views/c1/Tree_0_0/followups/turn_006.md) | commit sp 3 1; wp; while (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, ROout.m, ns... | pRHL / call_site / relational_program, 2 goals, goal 2987 chars | accepted commit |  |
| T0.0-8 | +05:13 | 12.5 s | 9.5 s | [turn_007.json](./views/c1/Tree_0_0/turn_007.json) · [inline read](./views/c1/Tree_0_0/followups/turn_007.md) | commit inline{1} Orcl.f; rcondt{1} 2; first by auto => />; smt(drop_nth mem_nth head_cons) | pRHL / call_site / relational_program, 3 goals, goal 1906 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-9 | +05:58 | 35.6 s | 6.4 s | [turn_008.json](./views/c1/Tree_0_0/turn_008.json) · [inline read](./views/c1/Tree_0_0/followups/turn_008.md) | commit inline{1} Orcl.f | pRHL / call_site / relational_program, 3 goals, goal 1906 chars | accepted commit |  |
| T0.0-10 | +06:19 | 14.3 s | 15.7 s | [turn_009.json](./views/c1/Tree_0_0/turn_009.json) · [inline read](./views/c1/Tree_0_0/followups/turn_009.md) | commit rcondt{1} 2; first by auto => />; smt(head_behead in_cons mem_drop drop_nth mem_nth head_cons) | pRHL / call_site / relational_program, 3 goals, goal 4149 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-11 | +07:02 | 27.7 s | 273 ms | [turn_010.json](./views/c1/Tree_0_0/turn_010.json) · [inline read](./views/c1/Tree_0_0/followups/turn_010.md) | commit rcondt{1} 2 | pRHL / call_site / relational_program, 3 goals, goal 4149 chars | accepted commit |  |
| T0.0-12 | +07:27 | 24.6 s | 9.4 s | [turn_011.json](./views/c1/Tree_0_0/turn_011.json) · [inline read](./views/c1/Tree_0_0/followups/turn_011.md) | commit by auto => />; smt(drop_nth head_cons mem_nth) | hoare / procedure_body / procedure_frontier, 4 goals, goal 874 chars | rejected commit: [error] cannot prove goal (strict) |  |

### Tree-0.0.r1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0.r1-1 | +36:57 | [think](./views/c1/Tree_0_0_r1/thinking/turn_001.md) | 9.9 s | [manager_bootstrap_0_0_r1.json](./views/_bootstrap/manager_bootstrap_0_0_r1.json) | commit by auto => />; smt(drop_nth head_cons mem_nth) | hoare / procedure_body / procedure_frontier, 4 goals, goal 874 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r1-2 | +37:39 | 31.6 s | 393 ms | [turn_001.json](./views/c1/Tree_0_0_r1/turn_001.json) · [inline read](./views/c1/Tree_0_0_r1/followups/turn_001.md) | commit by auto => />; smt(head_behead mem_head mem_drop) | hoare / procedure_body / procedure_frontier, 4 goals, goal 874 chars | accepted commit |  |
| T0.0.r1-3 | +37:56 | 16.3 s | 671 ms | [turn_002.json](./views/c1/Tree_0_0_r1/turn_002.json) · [inline read](./views/c1/Tree_0_0_r1/followups/turn_002.md) | commit by inline *; auto => />; smt(drop_nth head_cons drop_drop size_drop size_eq0 get_setE) | pRHL / call_site / relational_program, 3 goals, goal 1936 chars | accepted commit |  |
| T0.0.r1-4 | +38:14 | 17.6 s | 447 ms | [turn_003.json](./views/c1/Tree_0_0_r1/turn_003.json) · [inline read](./views/c1/Tree_0_0_r1/followups/turn_003.md) | commit by auto => />; smt(drop0 size_eq0 size_ge0) | pRHL / procedure_body / relational_program, 2 goals, goal 3227 chars | accepted commit |  |
| T0.0.r1-5 | +38:22 | 7.8 s | 241 ms | [turn_004.json](./views/c1/Tree_0_0_r1/turn_004.json) · [inline read](./views/c1/Tree_0_0_r1/followups/turn_004.md) | commit by auto => /> | pRHL / procedure_body / relational_program, 1 goal, goal 703 chars | accepted commit |  |
| T0.0.r1-6 | +38:28 | [5.7 s](./views/c1/Tree_0_0_r1/thinking/turn_006.md) | 265 ms | [turn_005.json](./views/c1/Tree_0_0_r1/turn_005.json) · [inline read](./views/c1/Tree_0_0_r1/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0.r1-7 | +38:34 | 6 s |  | [turn_006.json](./views/c1/Tree_0_0_r1/turn_006.json) · [inline read](./views/c1/Tree_0_0_r1/followups/turn_006.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
