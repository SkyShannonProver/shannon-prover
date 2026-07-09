# Agent-View Timeline — `equiv_step4` (resume lineage, 4 chunks)

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-11_0811_equiv_step4 |
| lemma | `equiv_step4` |
| source file | `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/source/ChaChaPoly/chacha_poly.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| resume chunks | 4 (c0=fresh → c3=leaf) |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns (all chunks) | 223 |

This run was built across a **resume lineage**: the proof was carried chunk0 → … → leaf via resume capsules. The committed-proof block below is the FULL `proof. … qed.` stitched across all chunks (resume boundaries marked); the timeline below has one `## c<k>` section per chunk, in order.

---

## Agent's committed proof (end-to-end across 4 resume chunks)

Reconstructed from the leaf's EasyCrypt session `history.ec` (185 accepted tactic(s); undos/rewinds already applied), split at each resume boundary. `(* ─── resume k ─── *)` marks each resume boundary.

### `Tree_0_0_r2` — proved

```easycrypt
proof.
  have eqRO : equiv [ROIN.RO.get ~ ROIN.RO.get : ={arg} /\ ={ROIN.RO.m} ==> ={res} /\ ={ROIN.RO.m}]; first by proc; auto.
  have eqSB2 : equiv [UFCMA(ROIN.RO).set_bad2 ~ UFCMA(ROIN.RO).set_bad2 : ={arg, UFCMA.bad2, UFCMA.cbad2} ==> ={res, UFCMA.bad2, UFCMA.cbad2}]; first by proc; auto.
  have eqf : equiv [Orcl.f ~ Orcl.f : ={arg} /\ ={glob Orcl} ==> ={glob Orcl}]; first by sim.
  have Hsw : equiv [Iter(Orcl).iter_12 ~ Iter(Orcl).iter_21 : ={glob Orcl, t1, t2} ==> ={glob Orcl}].
  proc.
  case (t1{1} = t2{1}).
  seq 1 1 : (={glob Orcl} /\ t2{1} = t1{2}); first by call eqf; auto => /#.
  by call eqf; auto.
  inline *.
  case ((t1{1}, C.ofintd 0) \in ROout.m{1}).
  case ((t2{1}, C.ofintd 0) \in ROout.m{1}).
  (* ─── resume 1: replayed 11 tactic(s) above, continued below ─── *)
  rcondt{1} 2.
  by auto => /#.
  rcondt{2} 2.
  by auto => /#.
  rcondt{1} 8.
  by auto => /#.
  rcondt{2} 8.
  by auto => /#.
  swap{1} 9 -6.
  by auto; smt(get_setE set_set_neqE mem_set fmap_eqP).
  rcondt{1} 2.
  by auto => /#.
  rcondf{1} 8.
  by auto => /#.
  rcondf{2} 2.
  by auto => /#.
  rcondt{2} 15.
  by auto; smt(mem_set).
  swap{1} 9 -6.
  swap{1} 13 -9.
  case ((t1{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 6.
  by auto => /#.
  rcondf{2} 17.
  by auto; smt(mem_set).
  case ((t2{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 10.
  by auto => /#.
  rcondf{2} 4.
  by auto => /#.
  by auto => /#.
  rcondt{1} 10.
  by auto => /#.
  rcondt{2} 4.
  by auto => /#.
  auto.
  move => />.
  move => &2 hneq _ _ _ _ r4L _ t4L _ r1L _; rewrite get_set_neqE 1:/# //.
  auto.
  move => />.
  move => &2 neq hS1 hS2 h3 r4L _; split.
  move => h4 t4L _ r1L _; split; last by smt(mem_set).
  move => h5; split; last by smt(mem_set).
  by move => h6; rewrite !get_set_sameE set_set_neqE 1:/#.
  move => hB t4L _ r1L _; split; [by smt(mem_set) | by move => h6; rewrite get_set_neqE 1:/#].
  case ((t2{1}, C.ofintd 0) \in ROout.m{1}).
  rcondf{1} 2; first by auto => /#.
  rcondt{2} 2; first by auto => /#.
  rcondt{1} 15; first by auto; smt(mem_set).
  rcondf{2} 8; first by auto => /#.
  swap{1} 16 -13.
  case ((t1{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 5; first by auto => /#.
  rcondf{2} 10; first by auto; smt(mem_set).
  case ((t2{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 16; first by auto => /#.
  rcondf{2} 4; first by auto => /#.
  by auto => /#.
  rcondt{1} 16; first by auto => /#.
  rcondt{2} 4; first by auto => /#.
  auto => />.
  by move => &2 hneq h1 h2 h3 h4 r3L _ r2L _ t3L _; rewrite get_set_neqE 1:/#.
  rcondt{1} 5; first by auto => /#.
  rcondt{2} 10; first by auto; smt(mem_set).
  case ((t2{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 17; first by auto; smt(mem_set).
  rcondf{2} 4; first by auto => /#.
  auto => />.
  by move => &2 hneq _ _ _ _ r3L _ r2L _ t3L _; rewrite get_set_neqE 1:/#.
  rcondt{1} 17; first by auto; smt(mem_set).
  rcondt{2} 4; first by auto => /#.
  auto => />.
  by move => &2 hneq _ _ _ _ r3L _ r2L _ t3L _; rewrite !get_set_sameE set_set_neqE 1:/#.
  rcondf{1} 2; first by auto => /#.
  rcondf{2} 2; first by auto => /#.
  rcondf{1} 15; first by auto; smt(mem_set).
  rcondf{2} 15; first by auto; smt(mem_set).
  swap{2} 16 -13.
  swap{2} 20 -16.
  case ((t1{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 4; first by auto => /#.
  rcondf{2} 18; first by auto; smt(mem_set).
  (* ─── resume 2: replayed 93 tactic(s) above, continued below ─── *)
  case ((t2{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 16; first by auto => /#.
  rcondf{2} 6; first by auto => /#.
  auto => />.
  move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; split.
  by smt().
  by rewrite set_set_neqE 1:/#.
  rcondt{1} 16; first by auto => /#.
  rcondt{2} 6; first by auto => /#.
  auto => />.
  move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE get_set_neqE 1:/#; split; [by smt() | by rewrite set_set_neqE 1:/#].
  rcondt{1} 4; first by auto => /#.
  rcondt{2} 18; first by auto; smt(mem_set).
  case ((t2{1}, C.ofintd 0) \in RO.m{1}).
  rcondf{1} 17; first by auto; smt(mem_set).
  rcondf{2} 6; first by auto => /#.
  auto => />.
  move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE get_set_neqE 1:/#; split; [by smt() | by rewrite set_set_neqE 1:/#].
  rcondt{1} 17; first by auto; smt(mem_set).
  rcondt{2} 6; first by auto => /#.
  auto => />.
  move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE; split; [by smt() | split; by rewrite set_set_neqE 1:/#].
  transitivity UFCMA2(RO).distinguish (={glob A} ==> ={UFCMA.bad2} /\ res{1} = res{2}) (={glob A} ==> ={UFCMA.bad2} /\ res{1} = UF.forged{2} /\ res{2} = (UF.forged{2} \/ UFCMA.bad2{2})) => //.
  by move => &1 &2 h; exists (glob A){2}.
  proc.
  seq 6 6 : (forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m}).
  wp; call (_: ={glob A, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2} ==> ={res, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m}).
  proc; inline *; wp; call (_: ={UFCMA.log, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2, Mem.log, Mem.lc, RO.m, SplitC2.I2.RO.m, BNR.lenc, BNR.ndec}).
  by sim.
  by sim.
  by auto.
  by auto.
  (* ─── resume 3: replayed 125 tactic(s) above, continued below ─── *)
  if.
  by move => />.
  seq 1 1 : (forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m} /\ ={ns}); first by auto.
  transitivity{2} { Iter(Orcl).iter(ns); } (forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m} /\ ={ns} ==> UFCMA.bad2{1} = UFCMA.bad2{2} /\ forged{1} = UF.forged{2}) (={ns, UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m} ==> ={UFCMA.bad2, UF.forged}).
  by move => &1 &2 h; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} SplitC2.I2.RO.m{2} ns{2}; smt().
  by move => &1 &m &2 />.
  have eqSet : equiv [ROout.set ~ ROout.set : ={arg, SplitC2.I2.RO.m} ==> ={SplitC2.I2.RO.m}]; first by proc; auto.
  inline{2} Iter(Orcl).iter; inline{2} Orcl.f.
  while (0 <= i{1} /\ l{2} = drop i{1} ns{1} /\ forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m}).
  sp 1 1; if.
  by smt(drop_nth).
  by wp; call eqRO; auto; smt(drop_nth drop_drop size_drop size_eq0 size_ge0).
  by wp; call eqSet; call eqSB2; call eqRO; auto; smt(drop_nth drop_drop size_drop size_eq0 size_ge0).
  by auto => />; smt(drop0 size_eq0 size_ge0).
  call (iter_perm Orcl Hsw).
  auto => /> &2; rewrite perm_eq_sym; have := perm_filterC (fun (n : nonce) => (n, C.ofintd 0) \in ROout.m{2}) ns{2}; by rewrite /predC /=.
  by auto.
  proc.
  seq 6 6 : (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m}).
  wp; call (_: ={glob A, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2} ==> ={res, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m}).
  proc; inline *; wp; call (_: ={UFCMA.log, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2, Mem.log, Mem.lc, RO.m, SplitC2.I2.RO.m, BNR.lenc, BNR.ndec}).
  by sim.
  by sim.
  by auto.
  by auto.
  if; first by move => />.
  seq 3 3 : (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m, ns, ns1, ns2} /\ uniq ns{2} /\ ns1{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{2}) ns{2} /\ ns2{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m{2}) ns{2}); first by auto => />; smt(undup_uniq).
  transitivity{1} { Iter(Orcl).iters(ns1, ns2); } (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m, ns, ns1, ns2} ==> ={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m}) ((UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /\ UFCMA.cbad2{1} = UFCMA.cbad2{2} /\ UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\ ns{1} = ns{2} /\ ns1{1} = ns1{2} /\ ns2{1} = ns2{2}) /\ uniq ns{2} /\ ns1{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{2}) ns{2} /\ ns2{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m{2}) ns{2} ==> UFCMA.bad2{1} = UFCMA.bad2{2} /\ UF.forged{1} = UF.forged{2}).
  by move => &1 &2 h; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} SplitC2.I2.RO.m{2} ns{2} ns1{2} ns2{2}; smt().
  by move => &1 &m &2 />.
  by call (iter_cat Orcl); auto => />.
  inline {1} Iter(Orcl).iters.
  inline {1} Iter(Orcl).iter.
  seq 4 2 : (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /\ UFCMA.cbad2{1} = UFCMA.cbad2{2} /\ UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\ l2{1} = ns2{2} /\ uniq ns2{2} /\ (forall n0, n0 \in ns2{2} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{2})).
  while (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /\ UFCMA.cbad2{1} = UFCMA.cbad2{2} /\ UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\ l{1} = drop i{2} ns1{2} /\ 0 <= i{2} /\ l2{1} = ns2{2} /\ uniq ns2{2} /\ (forall n0, n0 \in ns1{2} => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{2}) /\ (forall n0, n0 \in ns2{2} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{2})).
  inline {1} Orcl.f.
  sp 1 1.
  rcondt {1} 1.
  move=> &m; skip; smt(drop_nth mem_nth).
  wp; call eqRO; skip; smt(drop_nth drop_drop size_drop size_eq0).
  auto => />.
  move=> &2 Hu; rewrite drop0 /=; do ! split.
  by apply/filter_uniq.
  by move=> n0; rewrite mem_filter => -[h _].
  by move=> n0; rewrite mem_filter => -[h _].
  smt(size_eq0 size_ge0).
  smt(size_eq0 size_ge0).
  while (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /\ UFCMA.cbad2{1} = UFCMA.cbad2{2} /\ UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ l0{1} = drop i{2} ns2{2} /\ 0 <= i{2} /\ uniq l0{1} /\ (forall n0, n0 \in l0{1} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{1})).
  inline {1} Orcl.f.
  sp 1 1.
  rcondf {1} 1.
  move=> &m; skip; smt(drop_nth in_cons head_cons mem_head mem_nth).
  inline {1} ROout.set; wp; call eqSB2; call eqRO; skip.
  move => &1 &2 [#] hn2 hn1 hf hb hcb hlog hlc hro hl0 hi hu hnotin hne hlt.
  have hd : drop i{2} ns2{2} = n{2} :: drop (i{2} + 1) ns2{2} by smt(drop_nth).
  have hn12 : n{1} = n{2} by rewrite hn1 hl0 hd head_cons.
  rewrite hn12 hf hb hcb hlog hlc hro /=; move => resL resR mL mR [-> ->] /=; move => r0L r0R b2L cb2L b2R cb2R [#] _ -> -> /=; smt(drop_drop mem_set in_cons mem_drop size_drop size_eq0 size_ge0).
  auto => />; smt(drop0 size_eq0 size_ge0).
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

Run dir: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1`

t=0: `2026-06-11T07:10:07.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:24 | [think](./views/c0/Tree_0_0/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit have eqRO : equiv [ROIN.RO.get ~ ROIN.RO.get : ={arg} /\ ={ROIN.RO.m} ==> ={res} /\ ={ROIN.RO... | equiv / prhl_module / relational_program, 1 goal, goal 306 chars | accepted commit |  |
| T0.0-2 | +00:35 | [8.7 s](./views/c0/Tree_0_0/thinking/turn_002.md) | 280 ms | [turn_001.json](./views/c0/Tree_0_0/turn_001.json) · [inline read](./views/c0/Tree_0_0/followups/turn_001.md) | commit have eqSB2 : equiv [UFCMA(ROIN.RO).set_bad2 ~ UFCMA(ROIN.RO).set_bad2 : ={arg, UFCMA.bad2, UF... | equiv / prhl_module / relational_program, 1 goal, goal 458 chars | accepted commit |  |
| T0.0-3 | +00:43 | 7.7 s | 280 ms | [turn_002.json](./views/c0/Tree_0_0/turn_002.json) · [inline read](./views/c0/Tree_0_0/followups/turn_002.md) | commit have eqf : equiv [Orcl.f ~ Orcl.f : ={arg} /\ ={glob Orcl} ==> ={glob Orcl}]; first by sim | equiv / prhl_module / relational_program, 1 goal, goal 778 chars | accepted commit |  |
| T0.0-4 | +00:53 | 9.7 s | 270 ms | [turn_003.json](./views/c0/Tree_0_0/turn_003.json) · [inline read](./views/c0/Tree_0_0/followups/turn_003.md) | commit have Hsw : equiv [Iter(Orcl).iter_12 ~ Iter(Orcl).iter_21 : ={glob Or... | equiv / prhl_module / relational_program, 1 goal, goal 1358 chars | accepted commit |  |
| T0.0-5 | +01:01 | 7.7 s | 280 ms | [turn_004.json](./views/c0/Tree_0_0/turn_004.json) · [inline read](./views/c0/Tree_0_0/followups/turn_004.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 1697 chars | accepted commit |  |
| T0.0-6 | +01:12 | 10.7 s | 284 ms | [turn_005.json](./views/c0/Tree_0_0/turn_005.json) · [inline read](./views/c0/Tree_0_0/followups/turn_005.md) | commit case (t1{1} = t2{1}) | pRHL / procedure_body / relational_program, 2 goals, goal 1879 chars | accepted commit |  |
| T0.0-7 | +01:31 | 18.7 s | 290 ms | [turn_006.json](./views/c0/Tree_0_0/turn_006.json) · [inline read](./views/c0/Tree_0_0/followups/turn_006.md) | commit seq 1 1 : (={glob Orcl} /\ t2{1} = t1{2}); first by call eqf; auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 1905 chars | accepted commit |  |
| T0.0-8 | +01:38 | 6.7 s | 283 ms | [turn_007.json](./views/c0/Tree_0_0/turn_007.json) · [inline read](./views/c0/Tree_0_0/followups/turn_007.md) | commit by call eqf; auto | pRHL / procedure_body / relational_program, 3 goals, goal 1754 chars | accepted commit |  |
| T0.0-9 | +01:45 | [7.4 s](./views/c0/Tree_0_0/thinking/turn_009.md) | 1.6 s | [turn_008.json](./views/c0/Tree_0_0/turn_008.json) · [inline read](./views/c0/Tree_0_0/followups/turn_008.md) | commit inline * | pRHL / procedure_body / relational_program, 2 goals, goal 1906 chars | accepted commit |  |
| T0.0-10 | +02:21 | 34.4 s | 1.6 s | [turn_009.json](./views/c0/Tree_0_0/turn_009.json) · [inline read](./views/c0/Tree_0_0/followups/turn_009.md) | commit case ((t1{1}, C.ofintd 0) \in ROout.m{1}) | pRHL / procedure_body / relational_program, 2 goals, goal 9265 chars | accepted commit |  |
| T0.0-11 | +02:32 | 9.1 s | 1.9 s | [turn_010.json](./views/c0/Tree_0_0/turn_010.json) · [inline read](./views/c0/Tree_0_0/followups/turn_010.md) | commit case ((t2{1}, C.ofintd 0) \in ROout.m{1}) | pRHL / procedure_body / relational_program, 3 goals, goal 9315 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/c0/Tree_0_1/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit have hff : equiv [Orcl.f ~ Orcl.f : ={arg, glob Orcl} ==> ={glob Orcl}] | equiv / prhl_module / relational_program, 1 goal, goal 306 chars | accepted commit |  |
| T0.1-2 | +00:10 | [8.7 s](./views/c0/Tree_0_1/thinking/turn_002.md) | 347 ms | [turn_001.json](./views/c0/Tree_0_1/turn_001.json) · [inline read](./views/c0/Tree_0_1/followups/turn_001.md) | commit by sim | equiv / prhl_module / relational_program, 2 goals, goal 619 chars | accepted commit |  |
| T0.1-3 | +00:19 | [7.7 s](./views/c0/Tree_0_1/thinking/turn_003.md) | 277 ms | [turn_002.json](./views/c0/Tree_0_1/turn_002.json) · [inline read](./views/c0/Tree_0_1/followups/turn_002.md) | commit have hsw : equiv [Iter(Orcl).iter_12 ~ Iter(Orcl).iter_21 : ={glob Or... | equiv / prhl_module / relational_program, 1 goal, goal 899 chars | accepted commit |  |
| T0.1-4 | +00:25 | 5.7 s | 272 ms | [turn_003.json](./views/c0/Tree_0_1/turn_003.json) · [inline read](./views/c0/Tree_0_1/followups/turn_003.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 1238 chars | accepted commit |  |
| T0.1-5 | +00:33 | 7.7 s | 284 ms | [turn_004.json](./views/c0/Tree_0_1/turn_004.json) · [inline read](./views/c0/Tree_0_1/followups/turn_004.md) | commit case (t1{1} = t2{1}) | pRHL / procedure_body / relational_program, 2 goals, goal 1420 chars | accepted commit |  |
| T0.1-6 | +00:44 | [10.7 s](./views/c0/Tree_0_1/thinking/turn_006.md) | 287 ms | [turn_005.json](./views/c0/Tree_0_1/turn_005.json) · [inline read](./views/c0/Tree_0_1/followups/turn_005.md) | commit by call hff; call hff; auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 1446 chars | accepted commit |  |
| T0.1-7 | +00:53 | [9.5 s](./views/c0/Tree_0_1/thinking/turn_007.md) | 1.5 s | [turn_006.json](./views/c0/Tree_0_1/turn_006.json) · [inline read](./views/c0/Tree_0_1/followups/turn_006.md) | commit inline Orcl.f | pRHL / procedure_body / relational_program, 2 goals, goal 1447 chars | accepted commit |  |
| T0.1-8 | +01:27 | [32.5 s](./views/c0/Tree_0_1/thinking/turn_008.md) | 1.5 s | [turn_007.json](./views/c0/Tree_0_1/turn_007.json) · [inline read](./views/c0/Tree_0_1/followups/turn_007.md) | commit case ((t1{1}, C.ofintd 0) \in SplitC2.I2.RO.m{1}) | pRHL / call_site / relational_program, 2 goals, goal 6887 chars | accepted commit |  |
| T0.1-9 | +01:36 | 7.5 s | 1.5 s | [turn_008.json](./views/c0/Tree_0_1/turn_008.json) · [inline read](./views/c0/Tree_0_1/followups/turn_008.md) | commit case ((t2{1}, C.ofintd 0) \in SplitC2.I2.RO.m{1}) | pRHL / call_site / relational_program, 3 goals, goal 6945 chars | accepted commit |  |
| T0.1-10 | +01:52 | [14.4 s](./views/c0/Tree_0_1/thinking/turn_010.md) | 1.6 s | [turn_009.json](./views/c0/Tree_0_1/turn_009.json) · [inline read](./views/c0/Tree_0_1/followups/turn_009.md) | commit rcondt{1} 2; first by auto => /# | pRHL / call_site / relational_program, 4 goals, goal 7004 chars | accepted commit |  |
| T0.1-11 | +02:04 | 10.5 s | 1.5 s | [turn_010.json](./views/c0/Tree_0_1/turn_010.json) · [inline read](./views/c0/Tree_0_1/followups/turn_010.md) | commit rcondt{2} 2; first by auto => /# | pRHL / call_site / relational_program, 4 goals, goal 9968 chars | accepted commit |  |
| T0.1-12 | +02:15 | 9.3 s | 2.7 s | [turn_011.json](./views/c0/Tree_0_1/turn_011.json) · [inline read](./views/c0/Tree_0_1/followups/turn_011.md) | commit rcondt{1} 5; first by inline *; auto => /# | pRHL / call_site / relational_program, 4 goals, goal 4952 chars | rejected commit: [error] invalid arguments |  |
| T0.1-13 | +02:31 | 13.2 s | 1.8 s | [turn_012.json](./views/c0/Tree_0_1/turn_012.json) · [inline read](./views/c0/Tree_0_1/followups/turn_012.md) | commit rcondt{1} 5; first by move=> &m; inline *; auto => /# | pRHL / call_site / relational_program, 4 goals, goal 4952 chars | accepted commit |  |
| T0.1-14 | +02:40 | 7.7 s | 323 ms | [turn_013.json](./views/c0/Tree_0_1/turn_013.json) · [inline read](./views/c0/Tree_0_1/followups/turn_013.md) | commit rcondt{2} 5; first by move=> &m; inline *; auto => /# | pRHL / call_site / seq_cut, 4 goals, goal 4592 chars | accepted commit |  |

## c1

Run dir: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1`

t=0: `2026-06-11T07:58:16.631000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 |  | 369 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit rcondt{1} 2 | pRHL / procedure_body / relational_program, 4 goals, goal 9366 chars | accepted commit |  |
| T0.0-2 | +00:09 | 8.3 s | 1.7 s | [turn_001.json](./views/c1/Tree_0_0/turn_001.json) · [inline read](./views/c1/Tree_0_0/followups/turn_001.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1689 chars | accepted commit |  |
| T0.0-3 | +00:17 | 6.7 s | 286 ms | [turn_002.json](./views/c1/Tree_0_0/turn_002.json) · [inline read](./views/c1/Tree_0_0/followups/turn_002.md) | commit rcondt{2} 2 | pRHL / procedure_body / relational_program, 4 goals, goal 12743 chars | accepted commit |  |
| T0.0-4 | +00:23 | 5.3 s | 1.7 s | [turn_003.json](./views/c1/Tree_0_0/turn_003.json) · [inline read](./views/c1/Tree_0_0/followups/turn_003.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1717 chars | accepted commit |  |
| T0.0-5 | +00:31 | 6.7 s | 291 ms | [turn_004.json](./views/c1/Tree_0_0/turn_004.json) · [inline read](./views/c1/Tree_0_0/followups/turn_004.md) | commit rcondt{1} 8 | pRHL / procedure_body / relational_program, 4 goals, goal 6308 chars | accepted commit |  |
| T0.0-6 | +00:40 | 8.3 s | 1.7 s | [turn_005.json](./views/c1/Tree_0_0/turn_005.json) · [inline read](./views/c1/Tree_0_0/followups/turn_005.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1705 chars | accepted commit |  |
| T0.0-7 | +00:47 | 5.7 s | 299 ms | [turn_006.json](./views/c1/Tree_0_0/turn_006.json) · [inline read](./views/c1/Tree_0_0/followups/turn_006.md) | commit rcondt{2} 8 | pRHL / procedure_body / relational_program, 4 goals, goal 6649 chars | accepted commit |  |
| T0.0-8 | +00:53 | 5.7 s | 334 ms | [turn_007.json](./views/c1/Tree_0_0/turn_007.json) · [inline read](./views/c1/Tree_0_0/followups/turn_007.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1733 chars | accepted commit |  |
| T0.0-9 | +01:17 | 23.3 s | 1.7 s | [turn_008.json](./views/c1/Tree_0_0/turn_008.json) · [inline read](./views/c1/Tree_0_0/followups/turn_008.md) | commit swap{1} 9 -6 | pRHL / procedure_body / relational_program, 4 goals, goal 3671 chars | accepted commit |  |
| T0.0-10 | +01:31 | 12.4 s | 6.6 s | [turn_009.json](./views/c1/Tree_0_0/turn_009.json) · [inline read](./views/c1/Tree_0_0/followups/turn_009.md) | commit auto => /# | pRHL / procedure_body / relational_program, 4 goals, goal 3996 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-11 | +02:39 | 61.3 s | 2.7 s | [turn_010.json](./views/c1/Tree_0_0/turn_010.json) · [inline read](./views/c1/Tree_0_0/followups/turn_010.md) | commit by auto; smt(get_setE set_set_neqE mem_set fmap_eqP) | pRHL / procedure_body / relational_program, 4 goals, goal 3996 chars | accepted commit |  |
| T0.0-12 | +03:41 | 59.7 s | 317 ms | [turn_011.json](./views/c1/Tree_0_0/turn_011.json) · [inline read](./views/c1/Tree_0_0/followups/turn_011.md) | commit rcondt{1} 2 | pRHL / procedure_body / relational_program, 3 goals, goal 9369 chars | accepted commit |  |
| T0.0-13 | +03:47 | 5.7 s | 2.3 s | [turn_012.json](./views/c1/Tree_0_0/turn_012.json) · [inline read](./views/c1/Tree_0_0/followups/turn_012.md) | commit by auto => /# | hoare / procedure_body / relational_program, 4 goals, goal 1692 chars | accepted commit |  |
| T0.0-14 | +03:54 | 4.7 s | 275 ms | [turn_013.json](./views/c1/Tree_0_0/turn_013.json) · [inline read](./views/c1/Tree_0_0/followups/turn_013.md) | commit rcondf{1} 8 | pRHL / procedure_body / relational_program, 3 goals, goal 12746 chars | accepted commit |  |
| T0.0-15 | +03:59 | 4.9 s | 2.1 s | [turn_014.json](./views/c1/Tree_0_0/turn_014.json) · [inline read](./views/c1/Tree_0_0/followups/turn_014.md) | commit by auto => /# | hoare / procedure_body / relational_program, 4 goals, goal 1721 chars | accepted commit |  |
| T0.0-16 | +04:08 | 6.7 s | 284 ms | [turn_015.json](./views/c1/Tree_0_0/turn_015.json) · [inline read](./views/c1/Tree_0_0/followups/turn_015.md) | commit rcondf{2} 2 | pRHL / procedure_body / relational_program, 3 goals, goal 11274 chars | accepted commit |  |
| T0.0-17 | +04:13 | 4.2 s | 5.8 s | [turn_016.json](./views/c1/Tree_0_0/turn_016.json) · [inline read](./views/c1/Tree_0_0/followups/turn_016.md) | commit by auto => /# | hoare / procedure_body / relational_program, 4 goals, goal 1723 chars | accepted commit |  |
| T0.0-18 | +04:26 | 7.7 s | 281 ms | [turn_017.json](./views/c1/Tree_0_0/turn_017.json) · [inline read](./views/c1/Tree_0_0/followups/turn_017.md) | commit rcondt{2} 15 | pRHL / procedure_body / seq_cut, 3 goals, goal 8796 chars | accepted commit |  |
| T0.0-19 | +04:33 | 6.8 s | 6.2 s | [turn_018.json](./views/c1/Tree_0_0/turn_018.json) · [inline read](./views/c1/Tree_0_0/followups/turn_018.md) | commit by auto; smt(mem_set) | hoare / procedure_body / relational_program, 4 goals, goal 1736 chars | accepted commit |  |
| T0.0-20 | +04:57 | 17.4 s | 6.6 s | [turn_019.json](./views/c1/Tree_0_0/turn_019.json) · [inline read](./views/c1/Tree_0_0/followups/turn_019.md) | commit swap{1} 9 -6 | pRHL / procedure_body / relational_program, 3 goals, goal 5970 chars | accepted commit |  |
| T0.0-21 | +05:14 | 10.5 s | 6.5 s | [turn_020.json](./views/c1/Tree_0_0/turn_020.json) · [inline read](./views/c1/Tree_0_0/followups/turn_020.md) | commit swap{1} 13 -9 | pRHL / procedure_body / relational_program, 3 goals, goal 6375 chars | accepted commit |  |
| T0.0-22 | +06:50 | 89.6 s | 11.4 s | [turn_021.json](./views/c1/Tree_0_0/turn_021.json) · [inline read](./views/c1/Tree_0_0/followups/turn_021.md) | commit by auto; smt(get_setE set_set_neqE mem_set fmap_eqP) | pRHL / procedure_body / relational_program, 3 goals, goal 6294 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-23 | +08:38 | 97 s | 6 s | [turn_022.json](./views/c1/Tree_0_0/turn_022.json) · [inline read](./views/c1/Tree_0_0/followups/turn_022.md) | commit case ((t1{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 3 goals, goal 6294 chars | accepted commit |  |
| T0.0-24 | +08:58 | 13.7 s | 288 ms | [turn_023.json](./views/c1/Tree_0_0/turn_023.json) · [inline read](./views/c1/Tree_0_0/followups/turn_023.md) | commit rcondf{1} 6 | pRHL / procedure_body / relational_program, 4 goals, goal 6343 chars | accepted commit |  |
| T0.0-25 | +09:06 | 8 s | 6 s | [turn_024.json](./views/c1/Tree_0_0/turn_024.json) · [inline read](./views/c1/Tree_0_0/followups/turn_024.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1755 chars | accepted commit |  |
| T0.0-26 | +09:42 | 29.7 s | 8.3 s | [turn_025.json](./views/c1/Tree_0_0/turn_025.json) · [inline read](./views/c1/Tree_0_0/followups/turn_025.md) | commit rcondf{2} 18 | pRHL / procedure_body / seq_cut, 4 goals, goal 6262 chars | rejected commit: [error] the targetted instruction is not a conditionnal |  |
| T0.0-27 | +09:59 | 8.7 s | 280 ms | [turn_026.json](./views/c1/Tree_0_0/turn_026.json) · [inline read](./views/c1/Tree_0_0/followups/turn_026.md) | commit rcondf{2} 17 | pRHL / procedure_body / seq_cut, 4 goals, goal 6262 chars | accepted commit |  |
| T0.0-28 | +10:09 | 9.7 s | 6.3 s | [turn_027.json](./views/c1/Tree_0_0/turn_027.json) · [inline read](./views/c1/Tree_0_0/followups/turn_027.md) | commit by auto; smt(mem_set) | hoare / procedure_body / relational_program, 5 goals, goal 1780 chars | accepted commit |  |
| T0.0-29 | +10:28 | 12.5 s | 11.5 s | [turn_028.json](./views/c1/Tree_0_0/turn_028.json) · [inline read](./views/c1/Tree_0_0/followups/turn_028.md) | commit by auto; smt(get_setE set_set_neqE mem_set fmap_eqP) | pRHL / procedure_body / relational_program, 4 goals, goal 5938 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-30 | +11:41 | 61.8 s | 6.2 s | [turn_029.json](./views/c1/Tree_0_0/turn_029.json) · [inline read](./views/c1/Tree_0_0/followups/turn_029.md) | commit case ((t2{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 4 goals, goal 5938 chars | accepted commit |  |
| T0.0-31 | +11:56 | 8.7 s | 293 ms | [turn_030.json](./views/c1/Tree_0_0/turn_030.json) · [inline read](./views/c1/Tree_0_0/followups/turn_030.md) | commit rcondf{1} 10 | pRHL / procedure_body / relational_program, 5 goals, goal 5988 chars | accepted commit |  |
| T0.0-32 | +12:04 | 7.8 s | 6.2 s | [turn_031.json](./views/c1/Tree_0_0/turn_031.json) · [inline read](./views/c1/Tree_0_0/followups/turn_031.md) | commit by auto => /# | hoare / procedure_body / relational_program, 6 goals, goal 1815 chars | accepted commit |  |
| T0.0-33 | +12:18 | 7.7 s | 296 ms | [turn_032.json](./views/c1/Tree_0_0/turn_032.json) · [inline read](./views/c1/Tree_0_0/followups/turn_032.md) | commit rcondf{2} 4 | pRHL / procedure_body / seq_cut, 5 goals, goal 5988 chars | accepted commit |  |
| T0.0-34 | +12:25 | 6.7 s | 6.3 s | [turn_033.json](./views/c1/Tree_0_0/turn_033.json) · [inline read](./views/c1/Tree_0_0/followups/turn_033.md) | commit by auto => /# | hoare / procedure_body / relational_program, 6 goals, goal 1838 chars | accepted commit |  |
| T0.0-35 | +12:43 | 11.5 s | 6.5 s | [turn_034.json](./views/c1/Tree_0_0/turn_034.json) · [inline read](./views/c1/Tree_0_0/followups/turn_034.md) | commit by auto => /# | pRHL / procedure_body / relational_program, 5 goals, goal 5503 chars | accepted commit |  |
| T0.0-36 | +12:59 | 9.7 s | 281 ms | [turn_035.json](./views/c1/Tree_0_0/turn_035.json) · [inline read](./views/c1/Tree_0_0/followups/turn_035.md) | commit rcondt{1} 10 | pRHL / procedure_body / relational_program, 4 goals, goal 5991 chars | accepted commit |  |
| T0.0-37 | +13:07 | 7.6 s | 6.4 s | [turn_036.json](./views/c1/Tree_0_0/turn_036.json) · [inline read](./views/c1/Tree_0_0/followups/turn_036.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1814 chars | accepted commit |  |
| T0.0-38 | +13:21 | 7.7 s | 303 ms | [turn_037.json](./views/c1/Tree_0_0/turn_037.json) · [inline read](./views/c1/Tree_0_0/followups/turn_037.md) | commit rcondt{2} 4 | pRHL / procedure_body / seq_cut, 4 goals, goal 5829 chars | accepted commit |  |
| T0.0-39 | +13:30 | 8.5 s | 6.5 s | [turn_038.json](./views/c1/Tree_0_0/turn_038.json) · [inline read](./views/c1/Tree_0_0/followups/turn_038.md) | commit by auto => /# | hoare / procedure_body / relational_program, 5 goals, goal 1837 chars | accepted commit |  |
| T0.0-40 | +13:52 | 15.2 s | 11.8 s | [turn_039.json](./views/c1/Tree_0_0/turn_039.json) · [inline read](./views/c1/Tree_0_0/followups/turn_039.md) | commit by auto; smt(get_setE) | pRHL / procedure_body / relational_program, 4 goals, goal 5585 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-41 | +14:29 | 25.7 s | 348 ms | [turn_040.json](./views/c1/Tree_0_0/turn_040.json) · [inline read](./views/c1/Tree_0_0/followups/turn_040.md) | commit auto | pRHL / procedure_body / relational_program, 4 goals, goal 5585 chars | accepted commit |  |
| T0.0-42 | +14:55 | 25.5 s | 5.5 s | [turn_041.json](./views/c1/Tree_0_0/turn_041.json) · [inline read](./views/c1/Tree_0_0/followups/turn_041.md) | commit by move => />; smt(get_setE get_set_sameE) | ambient / ambient_logic / relational_program, 4 goals, goal 3337 chars | rejected commit: [error] cannot prove goal (strict) |  |

### Tree-0.0.r2

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0.r2-1 | +20:27 | [think](./views/c1/Tree_0_0_r2/thinking/turn_001.md) | 5.6 s | [manager_bootstrap_0_0_r2.json](./views/_bootstrap/manager_bootstrap_0_0_r2.json) | commit move => />; smt(get_setE get_set_sameE get_set_neqE) | ambient / ambient_logic / relational_program, 4 goals, goal 3337 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-2 | +21:10 | [37.7 s](./views/c1/Tree_0_0_r2/thinking/turn_002.md) | 299 ms | [turn_001.json](./views/c1/Tree_0_0_r2/turn_001.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_001.md) | commit move => /> | ambient / ambient_logic / relational_program, 4 goals, goal 3337 chars | accepted commit |  |
| T0.0.r2-3 | +21:20 | 9.2 s | 5.8 s | [turn_002.json](./views/c1/Tree_0_0_r2/turn_002.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_002.md) | commit smt(get_set_neqE) | ambient / ambient_logic / relational_program, 4 goals, goal 1864 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-4 | +22:11 | 45.3 s | 6.7 s | [turn_003.json](./views/c1/Tree_0_0_r2/turn_003.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_003.md) | commit move => &2 hneq _ _ _ _ r4L _ t4L _ r1L _; rewrite get_set_neqE 1:/# // | ambient / ambient_logic / relational_program, 4 goals, goal 1864 chars | accepted commit |  |
| T0.0.r2-5 | +22:51 | 33.4 s | 558 ms | [turn_004.json](./views/c1/Tree_0_0_r2/turn_004.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_004.md) | commit auto | pRHL / procedure_body / relational_program, 3 goals, goal 6346 chars | accepted commit |  |
| T0.0.r2-6 | +23:49 | 57.5 s | 486 ms | [turn_005.json](./views/c1/Tree_0_0_r2/turn_005.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_005.md) | commit move => /> | ambient / ambient_logic / relational_program, 3 goals, goal 17712 chars | accepted commit |  |
| T0.0.r2-7 | +24:14 | 25.1 s | 5.9 s | [turn_006.json](./views/c1/Tree_0_0_r2/turn_006.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_006.md) | commit smt(get_set_sameE get_set_neqE mem_set set_set_neqE) | ambient / ambient_logic / relational_program, 3 goals, goal 9101 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-8 | +26:46 | 145.6 s | 356 ms | [turn_007.json](./views/c1/Tree_0_0_r2/turn_007.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_007.md) | commit move => &2 neq hS1 hS2 h3 r4L _; split | ambient / ambient_logic / relational_program, 3 goals, goal 9101 chars | accepted commit |  |
| T0.0.r2-9 | +26:59 | 12.6 s | 378 ms | [turn_008.json](./views/c1/Tree_0_0_r2/turn_008.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_008.md) | commit move => h4 t4L _ r1L _; split; last by smt(mem_set) | ambient / ambient_logic / relational_program, 4 goals, goal 6607 chars | accepted commit |  |
| T0.0.r2-10 | +27:13 | [13.7 s](./views/c1/Tree_0_0_r2/thinking/turn_010.md) | 350 ms | [turn_009.json](./views/c1/Tree_0_0_r2/turn_009.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_009.md) | commit move => h5; split; last by smt(mem_set) | ambient / ambient_logic / relational_program, 4 goals, goal 3819 chars | accepted commit |  |
| T0.0.r2-11 | +27:30 | [16.7 s](./views/c1/Tree_0_0_r2/thinking/turn_011.md) | 343 ms | [turn_010.json](./views/c1/Tree_0_0_r2/turn_010.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_010.md) | commit by move => h6; rewrite !get_set_sameE set_set_neqE 1:/# | ambient / ambient_logic / relational_program, 4 goals, goal 2736 chars | accepted commit |  |
| T0.0.r2-12 | +27:41 | 10.8 s | 3.2 s | [turn_011.json](./views/c1/Tree_0_0_r2/turn_011.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_011.md) | commit move => hB t4L _ r1L _; split; [by smt(mem_set) \| by move => h6; rewrite get_set_neqE 1:/#] | ambient / ambient_logic / relational_program, 3 goals, goal 3095 chars | accepted commit |  |
| T0.0.r2-13 | +29:28 | 103.9 s | 3.1 s | [turn_012.json](./views/c1/Tree_0_0_r2/turn_012.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_012.md) | commit case ((t2{1}, C.ofintd 0) \in ROout.m{1}) | pRHL / procedure_body / relational_program, 2 goals, goal 9318 chars | accepted commit |  |
| T0.0.r2-14 | +29:53 | 21.7 s | 3.3 s | [turn_013.json](./views/c1/Tree_0_0_r2/turn_013.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_013.md) | commit rcondf{1} 2; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 9369 chars | accepted commit |  |
| T0.0.r2-15 | +30:11 | [14.8 s](./views/c1/Tree_0_0_r2/thinking/turn_015.md) | 3.2 s | [turn_014.json](./views/c1/Tree_0_0_r2/turn_014.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_014.md) | commit rcondt{2} 2; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 14558 chars | accepted commit |  |
| T0.0.r2-16 | +32:04 | 109.6 s | 3.4 s | [turn_015.json](./views/c1/Tree_0_0_r2/turn_015.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_015.md) | commit rcondt{1} 15; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 3 goals, goal 10868 chars | accepted commit |  |
| T0.0.r2-17 | +32:18 | 10.8 s | 12.2 s | [turn_016.json](./views/c1/Tree_0_0_r2/turn_016.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_016.md) | commit rcondf{2} 8; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 8492 chars | accepted commit |  |
| T0.0.r2-18 | +34:18 | 108.1 s | 5.9 s | [turn_017.json](./views/c1/Tree_0_0_r2/turn_017.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_017.md) | commit swap{1} 16 -13 | pRHL / procedure_body / relational_program, 3 goals, goal 5970 chars | accepted commit |  |
| T0.0.r2-19 | +34:37 | 12.3 s | 9.7 s | [turn_018.json](./views/c1/Tree_0_0_r2/turn_018.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_018.md) | commit by auto; smt(get_setE get_set_sameE get_set_neqE set_set_neqE mem_set fmap_eqP) | pRHL / procedure_body / relational_program, 3 goals, goal 6294 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-20 | +34:56 | 9.9 s | 6.1 s | [turn_019.json](./views/c1/Tree_0_0_r2/turn_019.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_019.md) | commit case ((t1{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 3 goals, goal 6294 chars | accepted commit |  |
| T0.0.r2-21 | +35:11 | 8.4 s | 14.6 s | [turn_020.json](./views/c1/Tree_0_0_r2/turn_020.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_020.md) | commit rcondf{1} 5; first by auto => /# | pRHL / procedure_body / relational_program, 4 goals, goal 6343 chars | accepted commit |  |
| T0.0.r2-22 | +35:34 | 9 s | 12 s | [turn_021.json](./views/c1/Tree_0_0_r2/turn_021.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_021.md) | commit rcondf{2} 10; first by auto; smt(mem_set) | pRHL / procedure_body / seq_cut, 4 goals, goal 6100 chars | accepted commit |  |
| T0.0.r2-23 | +35:57 | 10.5 s | 12.5 s | [turn_022.json](./views/c1/Tree_0_0_r2/turn_022.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_022.md) | commit case ((t2{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 4 goals, goal 5695 chars | accepted commit |  |
| T0.0.r2-24 | +36:16 | 7 s | 15 s | [turn_023.json](./views/c1/Tree_0_0_r2/turn_023.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_023.md) | commit rcondf{1} 16; first by auto => /# | pRHL / procedure_body / relational_program, 5 goals, goal 5745 chars | accepted commit |  |
| T0.0.r2-25 | +36:37 | 5.8 s | 9.2 s | [turn_024.json](./views/c1/Tree_0_0_r2/turn_024.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_024.md) | commit rcondf{2} 4; first by auto => /# | pRHL / procedure_body / seq_cut, 5 goals, goal 5664 chars | accepted commit |  |
| T0.0.r2-26 | +36:56 | 9.4 s | 12.6 s | [turn_025.json](./views/c1/Tree_0_0_r2/turn_025.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_025.md) | commit by auto => /# | pRHL / procedure_body / relational_program, 5 goals, goal 5582 chars | accepted commit |  |
| T0.0.r2-27 | +37:18 | 9.6 s | 15.4 s | [turn_026.json](./views/c1/Tree_0_0_r2/turn_026.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_026.md) | commit rcondt{1} 16; first by auto => /# | pRHL / procedure_body / relational_program, 4 goals, goal 5748 chars | accepted commit |  |
| T0.0.r2-28 | +37:39 | 5.5 s | 12.5 s | [turn_027.json](./views/c1/Tree_0_0_r2/turn_027.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_027.md) | commit rcondt{2} 4; first by auto => /# | pRHL / procedure_body / seq_cut, 4 goals, goal 5586 chars | accepted commit |  |
| T0.0.r2-29 | +38:10 | 19 s | 19 s | [turn_028.json](./views/c1/Tree_0_0_r2/turn_028.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_028.md) | commit by auto; smt(get_setE get_set_sameE get_set_neqE mem_set) | pRHL / procedure_body / relational_program, 4 goals, goal 5348 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-30 | +38:44 | 14.6 s | 365 ms | [turn_029.json](./views/c1/Tree_0_0_r2/turn_029.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_029.md) | commit auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 5348 chars | accepted commit |  |
| T0.0.r2-31 | +39:03 | 18.5 s | 3.5 s | [turn_030.json](./views/c1/Tree_0_0_r2/turn_030.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_030.md) | commit by move => &2 hneq h1 h2 h3 h4 r3L _ r2L _ t3L _; rewrite get_set_neqE 1:/# | ambient / ambient_logic / relational_program, 4 goals, goal 2172 chars | accepted commit |  |
| T0.0.r2-32 | +39:17 | 11.1 s | 15.9 s | [turn_031.json](./views/c1/Tree_0_0_r2/turn_031.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_031.md) | commit rcondt{1} 5; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 6346 chars | accepted commit |  |
| T0.0.r2-33 | +39:40 | 6.6 s | 13.4 s | [turn_032.json](./views/c1/Tree_0_0_r2/turn_032.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_032.md) | commit rcondt{2} 10; first by auto; smt(mem_set) | pRHL / procedure_body / seq_cut, 3 goals, goal 6184 chars | accepted commit |  |
| T0.0.r2-34 | +41:21 | 87.8 s | 13.2 s | [turn_033.json](./views/c1/Tree_0_0_r2/turn_033.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_033.md) | commit case ((t2{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 3 goals, goal 6022 chars | accepted commit |  |
| T0.0.r2-35 | +41:48 | 14.1 s | 16.9 s | [turn_034.json](./views/c1/Tree_0_0_r2/turn_034.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_034.md) | commit rcondf{1} 17; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 4 goals, goal 6072 chars | accepted commit |  |
| T0.0.r2-36 | +42:13 | 7.5 s | 13.5 s | [turn_035.json](./views/c1/Tree_0_0_r2/turn_035.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_035.md) | commit rcondf{2} 4; first by auto => /# | pRHL / procedure_body / seq_cut, 4 goals, goal 5991 chars | accepted commit |  |
| T0.0.r2-37 | +43:15 | 48.6 s | 386 ms | [turn_036.json](./views/c1/Tree_0_0_r2/turn_036.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_036.md) | commit auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 5664 chars | accepted commit |  |
| T0.0.r2-38 | +43:27 | 11.2 s | 13.8 s | [turn_037.json](./views/c1/Tree_0_0_r2/turn_037.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_037.md) | commit by move => &2 hneq _ _ _ _ r3L _ r2L _ t3L _; rewrite get_set_neqE 1:/# | ambient / ambient_logic / relational_program, 4 goals, goal 1864 chars | accepted commit |  |
| T0.0.r2-39 | +43:50 | 9.3 s | 17.7 s | [turn_038.json](./views/c1/Tree_0_0_r2/turn_038.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_038.md) | commit rcondt{1} 17; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 3 goals, goal 6075 chars | accepted commit |  |
| T0.0.r2-40 | +44:14 | 6.8 s | 14.2 s | [turn_039.json](./views/c1/Tree_0_0_r2/turn_039.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_039.md) | commit rcondt{2} 4; first by auto => /# | pRHL / procedure_body / seq_cut, 3 goals, goal 5913 chars | accepted commit |  |
| T0.0.r2-41 | +44:55 | 26.6 s | 408 ms | [turn_040.json](./views/c1/Tree_0_0_r2/turn_040.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_040.md) | commit auto => /> | pRHL / procedure_body / relational_program, 3 goals, goal 5667 chars | accepted commit |  |
| T0.0.r2-42 | +45:27 | 32.1 s | 3.9 s | [turn_041.json](./views/c1/Tree_0_0_r2/turn_041.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_041.md) | commit by move => &2 hneq _ _ _ _ r3L _ r2L _ t3L _; rewrite !get_set_sameE set_set_neqE 1:/# | ambient / ambient_logic / relational_program, 3 goals, goal 2818 chars | accepted commit |  |
| T0.0.r2-43 | +45:54 | 22.9 s | 4.1 s | [turn_042.json](./views/c1/Tree_0_0_r2/turn_042.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_042.md) | commit rcondf{1} 2; first by auto => /# | pRHL / procedure_body / relational_program, 2 goals, goal 9372 chars | accepted commit |  |
| T0.0.r2-44 | +46:05 | 6.8 s | 4.2 s | [turn_043.json](./views/c1/Tree_0_0_r2/turn_043.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_043.md) | commit rcondf{2} 2; first by auto => /# | pRHL / procedure_body / relational_program, 2 goals, goal 14561 chars | accepted commit |  |
| T0.0.r2-45 | +46:21 | 11.8 s | 4.2 s | [turn_044.json](./views/c1/Tree_0_0_r2/turn_044.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_044.md) | commit rcondf{1} 15; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 2 goals, goal 7951 chars | accepted commit |  |
| T0.0.r2-46 | +46:33 | 7.5 s | 489 ms | [turn_045.json](./views/c1/Tree_0_0_r2/turn_045.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_045.md) | commit rcondf{2} 15; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 2 goals, goal 10067 chars | accepted commit |  |
| T0.0.r2-47 | +47:34 | 60.2 s | 7.8 s | [turn_046.json](./views/c1/Tree_0_0_r2/turn_046.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_046.md) | commit swap{2} 16 -13 | pRHL / procedure_body / relational_program, 2 goals, goal 6608 chars | accepted commit |  |
| T0.0.r2-48 | +47:51 | 10 s | 23 s | [turn_047.json](./views/c1/Tree_0_0_r2/turn_047.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_047.md) | commit swap{2} 20 -16 | pRHL / procedure_body / relational_program, 2 goals, goal 7587 chars | accepted commit |  |
| T0.0.r2-49 | +48:24 | 10.1 s | 12.9 s | [turn_048.json](./views/c1/Tree_0_0_r2/turn_048.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_048.md) | commit case ((t1{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 2 goals, goal 8477 chars | accepted commit |  |
| T0.0.r2-50 | +48:46 | 9.1 s | 30.9 s | [turn_049.json](./views/c1/Tree_0_0_r2/turn_049.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_049.md) | commit rcondf{1} 4; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 8526 chars | accepted commit |  |
| T0.0.r2-51 | +49:25 | 7.3 s | 23.7 s | [turn_050.json](./views/c1/Tree_0_0_r2/turn_050.json) · [inline read](./views/c1/Tree_0_0_r2/followups/turn_050.md) | commit rcondf{2} 18; first by auto; smt(mem_set) | pRHL / procedure_body / seq_cut, 3 goals, goal 8437 chars | accepted commit |  |

## c2

Run dir: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1`

t=0: `2026-06-11T14:04:44.500000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/c2/Tree_0_0/thinking/turn_001.md) | 28.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit case ((t2{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 3 goals, goal 8081 chars | accepted commit |  |
| T0.0-2 | +00:40 | [11.4 s](./views/c2/Tree_0_0/thinking/turn_002.md) | 28.6 s | [turn_001.json](./views/c2/Tree_0_0/turn_001.json) · [inline read](./views/c2/Tree_0_0/followups/turn_001.md) | commit rcondf{1} 16; first by auto => /# | pRHL / procedure_body / relational_program, 4 goals, goal 8131 chars | accepted commit |  |
| T0.0-3 | +01:17 | [8.4 s](./views/c2/Tree_0_0/thinking/turn_003.md) | 24.6 s | [turn_002.json](./views/c2/Tree_0_0/turn_002.json) · [inline read](./views/c2/Tree_0_0/followups/turn_002.md) | commit rcondf{2} 6; first by auto => /# | pRHL / procedure_body / seq_cut, 4 goals, goal 8042 chars | accepted commit |  |
| T0.0-4 | +01:55 | 13.6 s | 31.4 s | [turn_003.json](./views/c2/Tree_0_0/turn_003.json) · [inline read](./views/c2/Tree_0_0/followups/turn_003.md) | commit by auto => /# | pRHL / procedure_body / relational_program, 4 goals, goal 7566 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-5 | +02:41 | [14.6 s](./views/c2/Tree_0_0/thinking/turn_005.md) | 406 ms | [turn_004.json](./views/c2/Tree_0_0/turn_004.json) · [inline read](./views/c2/Tree_0_0/followups/turn_004.md) | commit auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 7566 chars | accepted commit |  |
| T0.0-6 | +02:55 | [13.1 s](./views/c2/Tree_0_0/thinking/turn_006.md) | 7.9 s | [turn_005.json](./views/c2/Tree_0_0/turn_005.json) · [inline read](./views/c2/Tree_0_0/followups/turn_005.md) | commit by smt(set_set_neqE) | ambient / ambient_logic / relational_program, 4 goals, goal 3057 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-7 | +03:38 | [35.6 s](./views/c2/Tree_0_0/thinking/turn_007.md) | 4.4 s | [turn_006.json](./views/c2/Tree_0_0/turn_006.json) · [inline read](./views/c2/Tree_0_0/followups/turn_006.md) | commit move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; split | ambient / ambient_logic / relational_program, 4 goals, goal 3057 chars | accepted commit |  |
| T0.0-8 | +03:54 | [11.6 s](./views/c2/Tree_0_0/thinking/turn_008.md) | 373 ms | [turn_007.json](./views/c2/Tree_0_0/turn_007.json) · [inline read](./views/c2/Tree_0_0/followups/turn_007.md) | commit by smt() | ambient / ambient_logic / relational_program, 5 goals, goal 2443 chars | accepted commit |  |
| T0.0-9 | +04:02 | [7.2 s](./views/c2/Tree_0_0/thinking/turn_009.md) | 25.8 s | [turn_008.json](./views/c2/Tree_0_0/turn_008.json) · [inline read](./views/c2/Tree_0_0/followups/turn_008.md) | commit by rewrite set_set_neqE 1:/# | ambient / ambient_logic / relational_program, 4 goals, goal 1807 chars | accepted commit |  |
| T0.0-10 | +04:39 | [11.9 s](./views/c2/Tree_0_0/thinking/turn_010.md) | 30.1 s | [turn_009.json](./views/c2/Tree_0_0/turn_009.json) · [inline read](./views/c2/Tree_0_0/followups/turn_009.md) | commit rcondt{1} 16; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 8134 chars | accepted commit |  |
| T0.0-11 | +05:18 | 8.4 s | 31.6 s | [turn_010.json](./views/c2/Tree_0_0/turn_010.json) · [inline read](./views/c2/Tree_0_0/followups/turn_010.md) | commit rcondt{2} 6; first by auto => /# | pRHL / procedure_body / seq_cut, 3 goals, goal 7956 chars | accepted commit |  |
| T0.0-12 | +06:04 | [14.5 s](./views/c2/Tree_0_0/thinking/turn_012.md) | 460 ms | [turn_011.json](./views/c2/Tree_0_0/turn_011.json) · [inline read](./views/c2/Tree_0_0/followups/turn_011.md) | commit auto => /> | pRHL / procedure_body / relational_program, 3 goals, goal 7656 chars | accepted commit |  |
| T0.0-13 | +06:26 | [21.3 s](./views/c2/Tree_0_0/thinking/turn_013.md) | 26.7 s | [turn_012.json](./views/c2/Tree_0_0/turn_012.json) · [inline read](./views/c2/Tree_0_0/followups/turn_012.md) | commit move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE get_set_neqE... | ambient / ambient_logic / relational_program, 3 goals, goal 3266 chars | accepted commit |  |
| T0.0-14 | +07:12 | 19 s | 7 s | [turn_013.json](./views/c2/Tree_0_0/turn_013.json) · [inline read](./views/c2/Tree_0_0/followups/turn_013.md) | commit rcondt{1} 4; first by auto => /# | pRHL / procedure_body / relational_program, 2 goals, goal 8529 chars | accepted commit |  |
| T0.0-15 | +07:30 | [11.5 s](./views/c2/Tree_0_0/thinking/turn_015.md) | 33.5 s | [turn_014.json](./views/c2/Tree_0_0/turn_014.json) · [inline read](./views/c2/Tree_0_0/followups/turn_014.md) | commit rcondt{2} 18; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 2 goals, goal 8351 chars | accepted commit |  |
| T0.0-16 | +08:12 | [8.2 s](./views/c2/Tree_0_0/thinking/turn_016.md) | 27.8 s | [turn_015.json](./views/c2/Tree_0_0/turn_015.json) · [inline read](./views/c2/Tree_0_0/followups/turn_015.md) | commit case ((t2{1}, C.ofintd 0) \in RO.m{1}) | pRHL / procedure_body / relational_program, 2 goals, goal 8173 chars | accepted commit |  |
| T0.0-17 | +08:50 | 10.3 s | 13.7 s | [turn_016.json](./views/c2/Tree_0_0/turn_016.json) · [inline read](./views/c2/Tree_0_0/followups/turn_016.md) | commit rcondf{1} 17; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 3 goals, goal 8223 chars | accepted commit |  |
| T0.0-18 | +09:10 | 6.2 s | 32.8 s | [turn_017.json](./views/c2/Tree_0_0/turn_017.json) · [inline read](./views/c2/Tree_0_0/followups/turn_017.md) | commit rcondf{2} 6; first by auto => /# | pRHL / procedure_body / relational_program, 3 goals, goal 8134 chars | accepted commit |  |
| T0.0-19 | +10:02 | [19.5 s](./views/c2/Tree_0_0/thinking/turn_019.md) | 468 ms | [turn_018.json](./views/c2/Tree_0_0/turn_018.json) · [inline read](./views/c2/Tree_0_0/followups/turn_018.md) | commit auto => /> | pRHL / procedure_body / relational_program, 3 goals, goal 7656 chars | accepted commit |  |
| T0.0-20 | +10:16 | [13.3 s](./views/c2/Tree_0_0/thinking/turn_020.md) | 28.7 s | [turn_019.json](./views/c2/Tree_0_0/turn_019.json) · [inline read](./views/c2/Tree_0_0/followups/turn_019.md) | commit move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE get_set_neqE... | ambient / ambient_logic / relational_program, 3 goals, goal 3266 chars | accepted commit |  |
| T0.0-21 | +10:55 | 10.1 s | 25.9 s | [turn_020.json](./views/c2/Tree_0_0/turn_020.json) · [inline read](./views/c2/Tree_0_0/followups/turn_020.md) | commit rcondt{1} 17; first by auto; smt(mem_set) | pRHL / procedure_body / relational_program, 2 goals, goal 8226 chars | accepted commit |  |
| T0.0-22 | +11:27 | 6.5 s | 29.5 s | [turn_021.json](./views/c2/Tree_0_0/turn_021.json) · [inline read](./views/c2/Tree_0_0/followups/turn_021.md) | commit rcondt{2} 6; first by auto => /# | pRHL / procedure_body / seq_cut, 2 goals, goal 8048 chars | accepted commit |  |
| T0.0-23 | +13:15 | 78.5 s | 471 ms | [turn_022.json](./views/c2/Tree_0_0/turn_022.json) · [inline read](./views/c2/Tree_0_0/followups/turn_022.md) | commit auto => /> | pRHL / procedure_body / relational_program, 2 goals, goal 7746 chars | accepted commit |  |
| T0.0-24 | +14:03 | 47.5 s | 493 ms | [turn_023.json](./views/c2/Tree_0_0/turn_023.json) · [inline read](./views/c2/Tree_0_0/followups/turn_023.md) | commit move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE; split; [by s... | ambient / ambient_logic / relational_program, 2 goals, goal 3552 chars | accepted commit |  |
| T0.0-25 | +17:28 | 204.6 s | 405 ms | [turn_024.json](./views/c2/Tree_0_0/turn_024.json) · [inline read](./views/c2/Tree_0_0/followups/turn_024.md) | commit transitivity UFCMA2(RO).distinguish (={glob A} ==> ={UFCMA.bad2} /\ r... | equiv / prhl_module / relational_program, 1 goal, goal 1977 chars | accepted commit |  |
| T0.0-26 | +17:39 | 10.6 s | 353 ms | [turn_025.json](./views/c2/Tree_0_0/turn_025.json) · [inline read](./views/c2/Tree_0_0/followups/turn_025.md) | commit by move => &1 &2 h; exists (glob A){2} | ambient / ambient_logic / relational_program, 3 goals, goal 1904 chars | accepted commit |  |
| T0.0-27 | +20:16 | 156.3 s | 5.7 s | [turn_026.json](./views/c2/Tree_0_0/turn_026.json) · [inline read](./views/c2/Tree_0_0/followups/turn_026.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 1938 chars | accepted commit |  |
| T0.0-28 | +22:54 | 152.3 s | 5.7 s | [turn_027.json](./views/c2/Tree_0_0/turn_027.json) · [inline read](./views/c2/Tree_0_0/followups/turn_027.md) | commit seq 6 6 : (forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cbad2, UFC... | pRHL / call_site / seq_cut, 2 goals, goal 7606 chars | accepted commit |  |
| T0.0-29 | +23:16 | 16.6 s | 354 ms | [turn_028.json](./views/c2/Tree_0_0/turn_028.json) · [inline read](./views/c2/Tree_0_0/followups/turn_028.md) | commit wp; call (_: ={glob A, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2} ==> ={res, UFCMA.bad... | pRHL / call_site / relational_program, 3 goals, goal 2847 chars | accepted commit |  |
| T0.0-30 | +23:48 | 31.6 s | 368 ms | [turn_029.json](./views/c2/Tree_0_0/turn_029.json) · [inline read](./views/c2/Tree_0_0/followups/turn_029.md) | commit proc; inline *; wp; call (_: ={UFCMA.log, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2, M... | equiv / prhl_module / relational_program, 4 goals, goal 2493 chars | accepted commit |  |
| T0.0-31 | +23:58 | 9.3 s | 5.7 s | [turn_030.json](./views/c2/Tree_0_0/turn_030.json) · [inline read](./views/c2/Tree_0_0/followups/turn_030.md) | commit by sim | equiv / prhl_module / relational_program, 6 goals, goal 2648 chars | accepted commit |  |
| T0.0-32 | +24:12 | 8.6 s | 367 ms | [turn_031.json](./views/c2/Tree_0_0/turn_031.json) · [inline read](./views/c2/Tree_0_0/followups/turn_031.md) | commit by sim | equiv / prhl_module / relational_program, 5 goals, goal 2648 chars | accepted commit |  |
| T0.0-33 | +24:22 | 9.6 s | 368 ms | [turn_032.json](./views/c2/Tree_0_0/turn_032.json) · [inline read](./views/c2/Tree_0_0/followups/turn_032.md) | commit by auto | pRHL / verification_residue / relational_program, 4 goals, goal 4128 chars | accepted commit |  |
| T0.0-34 | +24:32 | 9.6 s | 395 ms | [turn_033.json](./views/c2/Tree_0_0/turn_033.json) · [inline read](./views/c2/Tree_0_0/followups/turn_033.md) | commit by auto | pRHL / procedure_body / relational_program, 3 goals, goal 3124 chars | accepted commit |  |

## c3

Run dir: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1`

t=0: `2026-06-11T15:39:33.900000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 |  | 6.1 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit if | pRHL / call_site / relational_program, 2 goals, goal 6917 chars | accepted commit |  |
| T0.0-2 | +00:15 | 8.6 s | 401 ms | [turn_001.json](./views/c3/Tree_0_0/turn_001.json) · [inline read](./views/c3/Tree_0_0/followups/turn_001.md) | commit by move => /> | ambient / ambient_logic / relational_program, 4 goals, goal 2090 chars | accepted commit |  |
| T0.0-3 | +00:23 | 7.5 s | 465 ms | [turn_002.json](./views/c3/Tree_0_0/turn_002.json) · [inline read](./views/c3/Tree_0_0/followups/turn_002.md) | commit seq 1 1 : (forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, Sp... | pRHL / call_site / relational_program, 3 goals, goal 6490 chars | accepted commit |  |
| T0.0-4 | +00:35 | 11.6 s | 357 ms | [turn_003.json](./views/c3/Tree_0_0/turn_003.json) · [inline read](./views/c3/Tree_0_0/followups/turn_003.md) | commit transitivity{2} { Iter(Orcl).iter(ns); } (forged{1} = UF.forged{2} /\ ={UFCMA.bad2, UFCMA.cba... | pRHL / call_site / relational_program, 3 goals, goal 6060 chars | accepted commit |  |
| T0.0-5 | +00:53 | 17.6 s | 402 ms | [turn_004.json](./views/c3/Tree_0_0/turn_004.json) · [inline read](./views/c3/Tree_0_0/followups/turn_004.md) | commit by move => &1 &2 h; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem... | ambient / ambient_logic / relational_program, 6 goals, goal 2699 chars | accepted commit |  |
| T0.0-6 | +01:03 | 9.6 s | 389 ms | [turn_005.json](./views/c3/Tree_0_0/turn_005.json) · [inline read](./views/c3/Tree_0_0/followups/turn_005.md) | commit by move => &1 &m &2 /> | ambient / ambient_logic / relational_program, 5 goals, goal 2002 chars | accepted commit |  |
| T0.0-7 | +01:15 | 11.5 s | 477 ms | [turn_006.json](./views/c3/Tree_0_0/turn_006.json) · [inline read](./views/c3/Tree_0_0/followups/turn_006.md) | commit have eqSet : equiv [ROout.set ~ ROout.set : ={arg, SplitC2.I2.RO.m} ==> ={SplitC2.I2.RO.m}];... | pRHL / call_site / relational_program, 4 goals, goal 4828 chars | accepted commit |  |
| T0.0-8 | +01:22 | 6.6 s | 395 ms | [turn_007.json](./views/c3/Tree_0_0/turn_007.json) · [inline read](./views/c3/Tree_0_0/followups/turn_007.md) | commit inline{2} Iter(Orcl).iter; inline{2} Orcl.f | pRHL / call_site / relational_program, 4 goals, goal 5001 chars | accepted commit |  |
| T0.0-9 | +01:32 | 10.2 s | 5.8 s | [turn_008.json](./views/c3/Tree_0_0/turn_008.json) · [inline read](./views/c3/Tree_0_0/followups/turn_008.md) | commit while (0 <= i{1} /\ l{2} = drop i{1} ns{1} /\ forged{1} = UF.forged{2... | pRHL / call_site / relational_program, 4 goals, goal 5867 chars | accepted commit |  |
| T0.0-10 | +01:49 | 10.6 s | 423 ms | [turn_009.json](./views/c3/Tree_0_0/turn_009.json) · [inline read](./views/c3/Tree_0_0/followups/turn_009.md) | commit sp 1 1; if | pRHL / call_site / relational_program, 5 goals, goal 5680 chars | accepted commit |  |
| T0.0-11 | +01:56 | 6.5 s | 492 ms | [turn_010.json](./views/c3/Tree_0_0/turn_010.json) · [inline read](./views/c3/Tree_0_0/followups/turn_010.md) | commit by smt(drop_nth) | ambient / ambient_logic / relational_program, 7 goals, goal 2455 chars | accepted commit |  |
| T0.0-12 | +02:06 | 9.5 s | 524 ms | [turn_011.json](./views/c3/Tree_0_0/turn_011.json) · [inline read](./views/c3/Tree_0_0/followups/turn_011.md) | commit by wp; call eqRO; auto; smt(drop_nth drop_drop size_drop size_eq0 size_ge0) | pRHL / call_site / relational_program, 6 goals, goal 3324 chars | accepted commit |  |
| T0.0-13 | +02:17 | 10.5 s | 1.5 s | [turn_012.json](./views/c3/Tree_0_0/turn_012.json) · [inline read](./views/c3/Tree_0_0/followups/turn_012.md) | commit by wp; call eqSet; call eqSB2; call eqRO; auto; smt(drop_nth drop_drop size_drop size_eq0 siz... | pRHL / call_site / relational_program, 5 goals, goal 4695 chars | accepted commit |  |
| T0.0-14 | +02:53 | 34.6 s | 448 ms | [turn_013.json](./views/c3/Tree_0_0/turn_013.json) · [inline read](./views/c3/Tree_0_0/followups/turn_013.md) | commit by auto => />; smt(drop0 size_eq0 size_ge0) | pRHL / procedure_body / relational_program, 4 goals, goal 3453 chars | accepted commit |  |
| T0.0-15 | +03:34 | 41 s | 10 s | [turn_014.json](./views/c3/Tree_0_0/turn_014.json) · [inline read](./views/c3/Tree_0_0/followups/turn_014.md) | commit call (iter_perm Orcl Hsw); auto => />; smt(perm_filterC) | pRHL / procedure_body / relational_program, 3 goals, goal 2932 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-16 | +04:06 | 21.6 s | 375 ms | [turn_015.json](./views/c3/Tree_0_0/turn_015.json) · [inline read](./views/c3/Tree_0_0/followups/turn_015.md) | commit call (iter_perm Orcl Hsw) | pRHL / procedure_body / relational_program, 3 goals, goal 2932 chars | accepted commit |  |
| T0.0-17 | +04:53 | 46.6 s | 437 ms | [turn_016.json](./views/c3/Tree_0_0/turn_016.json) · [inline read](./views/c3/Tree_0_0/followups/turn_016.md) | commit auto => /> &2; rewrite perm_eq_sym; have := perm_filterC (fun (n : nonce) => (n, C.ofintd 0)... | pRHL / procedure_body / relational_program, 3 goals, goal 3519 chars | accepted commit |  |
| T0.0-18 | +05:02 | 8.6 s | 380 ms | [turn_017.json](./views/c3/Tree_0_0/turn_017.json) · [inline read](./views/c3/Tree_0_0/followups/turn_017.md) | commit by auto | pRHL / procedure_body / relational_program, 2 goals, goal 2292 chars | accepted commit |  |
| T0.0-19 | +09:33 | 270.8 s | 7.2 s | [turn_018.json](./views/c3/Tree_0_0/turn_018.json) · [inline read](./views/c3/Tree_0_0/followups/turn_018.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 1978 chars | accepted commit |  |
| T0.0-20 | +09:56 | 15.6 s | 389 ms | [turn_019.json](./views/c3/Tree_0_0/turn_019.json) · [inline read](./views/c3/Tree_0_0/followups/turn_019.md) | commit seq 6 6 : (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, R... | pRHL / call_site / seq_cut, 1 goal, goal 7578 chars | accepted commit |  |
| T0.0-21 | +10:04 | 7.6 s | 370 ms | [turn_020.json](./views/c3/Tree_0_0/turn_020.json) · [inline read](./views/c3/Tree_0_0/followups/turn_020.md) | commit wp; call (_: ={glob A, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2} ==> ={res, UFCMA.bad... | pRHL / call_site / relational_program, 2 goals, goal 2852 chars | accepted commit |  |
| T0.0-22 | +10:09 | 4.6 s | 369 ms | [turn_021.json](./views/c3/Tree_0_0/turn_021.json) · [inline read](./views/c3/Tree_0_0/followups/turn_021.md) | commit proc; inline *; wp; call (_: ={UFCMA.log, UFCMA.bad1, UFCMA.cbad1, UFCMA.bad2, UFCMA.cbad2, M... | equiv / prhl_module / relational_program, 3 goals, goal 2497 chars | accepted commit |  |
| T0.0-23 | +10:14 | 4.6 s | 381 ms | [turn_022.json](./views/c3/Tree_0_0/turn_022.json) · [inline read](./views/c3/Tree_0_0/followups/turn_022.md) | commit by sim | equiv / prhl_module / relational_program, 5 goals, goal 2648 chars | accepted commit |  |
| T0.0-24 | +10:19 | 4.4 s | 559 ms | [turn_023.json](./views/c3/Tree_0_0/turn_023.json) · [inline read](./views/c3/Tree_0_0/followups/turn_023.md) | commit by sim | equiv / prhl_module / relational_program, 4 goals, goal 2648 chars | accepted commit |  |
| T0.0-25 | +10:24 | 4.5 s | 515 ms | [turn_024.json](./views/c3/Tree_0_0/turn_024.json) · [inline read](./views/c3/Tree_0_0/followups/turn_024.md) | commit by auto | pRHL / verification_residue / relational_program, 3 goals, goal 4128 chars | accepted commit |  |
| T0.0-26 | +10:29 | 4.6 s | 423 ms | [turn_025.json](./views/c3/Tree_0_0/turn_025.json) · [inline read](./views/c3/Tree_0_0/followups/turn_025.md) | commit by auto | pRHL / procedure_body / relational_program, 2 goals, goal 3126 chars | accepted commit |  |
| T0.0-27 | +10:40 | 10.5 s | 454 ms | [turn_026.json](./views/c3/Tree_0_0/turn_026.json) · [inline read](./views/c3/Tree_0_0/followups/turn_026.md) | commit if; first by move => /> | pRHL / call_site / relational_program, 1 goal, goal 6924 chars | accepted commit |  |
| T0.0-28 | +10:54 | 13.5 s | 512 ms | [turn_027.json](./views/c3/Tree_0_0/turn_027.json) · [inline read](./views/c3/Tree_0_0/followups/turn_027.md) | commit seq 3 3 : (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.m, SplitC2.I2.RO.m, ns... | pRHL / call_site / relational_program, 2 goals, goal 6514 chars | accepted commit |  |
| T0.0-29 | +11:36 | 41.6 s | 405 ms | [turn_028.json](./views/c3/Tree_0_0/turn_028.json) · [inline read](./views/c3/Tree_0_0/followups/turn_028.md) | commit transitivity{1} { Iter(Orcl).iters(ns1, ns2); } (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.... | pRHL / call_site / relational_program, 2 goals, goal 5081 chars | accepted commit |  |
| T0.0-30 | +11:50 | 13.6 s | 389 ms | [turn_029.json](./views/c3/Tree_0_0/turn_029.json) · [inline read](./views/c3/Tree_0_0/followups/turn_029.md) | commit by move => &1 &2 h; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem... | ambient / ambient_logic / relational_program, 5 goals, goal 3229 chars | accepted commit |  |
| T0.0-31 | +11:55 | 4.6 s | 403 ms | [turn_030.json](./views/c3/Tree_0_0/turn_030.json) · [inline read](./views/c3/Tree_0_0/followups/turn_030.md) | commit by move => &1 &m &2 /> | ambient / ambient_logic / relational_program, 4 goals, goal 2246 chars | accepted commit |  |
| T0.0-32 | +12:03 | 7.5 s | 497 ms | [turn_031.json](./views/c3/Tree_0_0/turn_031.json) · [inline read](./views/c3/Tree_0_0/followups/turn_031.md) | commit by call (iter_cat Orcl); auto => /> | pRHL / procedure_body / relational_program, 3 goals, goal 2490 chars | accepted commit |  |

### Tree-0.0.r2

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0.r2-1 | +39:33 |  | 435 ms | [manager_bootstrap_0_0_r2.json](./views/_bootstrap/manager_bootstrap_0_0_r2.json) | commit inline {1} Iter(Orcl).iters | pRHL / call_site / relational_program, 2 goals, goal 4978 chars | accepted commit |  |
| T0.0.r2-2 | +39:41 | 7.6 s | 385 ms | [turn_001.json](./views/c3/Tree_0_0_r2/turn_001.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_001.md) | commit inline {1} Iter(Orcl).iter | pRHL / call_site / relational_program, 2 goals, goal 4958 chars | accepted commit |  |
| T0.0.r2-3 | +40:49 | 67.6 s | 386 ms | [turn_002.json](./views/c3/Tree_0_0_r2/turn_002.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_002.md) | commit seq 4 2 : (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{... | pRHL / call_site / relational_program, 2 goals, goal 5664 chars | accepted commit |  |
| T0.0.r2-4 | +41:04 | 14.6 s | 388 ms | [turn_003.json](./views/c3/Tree_0_0_r2/turn_003.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_003.md) | commit while (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /... | pRHL / call_site / relational_program, 3 goals, goal 3935 chars | accepted commit |  |
| T0.0.r2-5 | +41:10 | 6.4 s | 6.6 s | [turn_004.json](./views/c3/Tree_0_0_r2/turn_004.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_004.md) | commit inline {1} Orcl.f | pRHL / call_site / relational_program, 4 goals, goal 3558 chars | accepted commit |  |
| T0.0.r2-6 | +41:27 | 10.3 s | 6.7 s | [turn_005.json](./views/c3/Tree_0_0_r2/turn_005.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_005.md) | commit sp 1 1 | pRHL / call_site / relational_program, 4 goals, goal 5801 chars | accepted commit |  |
| T0.0.r2-7 | +41:46 | 11.6 s | 385 ms | [turn_006.json](./views/c3/Tree_0_0_r2/turn_006.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_006.md) | commit rcondt {1} 1 | pRHL / call_site / relational_program, 4 goals, goal 5679 chars | accepted commit |  |
| T0.0.r2-8 | +42:01 | 14.8 s | 7.2 s | [turn_007.json](./views/c3/Tree_0_0_r2/turn_007.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_007.md) | commit skip; smt(drop_nth mem_nth) | hoare / procedure_body / relational_program, 5 goals, goal 2594 chars | rejected commit: [error] expecting a goal of the form: hoare[S], ehoare[S], phoare[S], equiv[S] |  |
| T0.0.r2-9 | +42:17 | 8.6 s | 440 ms | [turn_008.json](./views/c3/Tree_0_0_r2/turn_008.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_008.md) | commit move=> &m; skip; smt(drop_nth mem_nth) | hoare / procedure_body / relational_program, 5 goals, goal 2594 chars | accepted commit |  |
| T0.0.r2-10 | +42:29 | 11.5 s | 474 ms | [turn_009.json](./views/c3/Tree_0_0_r2/turn_009.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_009.md) | commit wp; call eqRO; skip; smt(drop_nth drop_drop size_drop size_eq0) | pRHL / call_site / relational_program, 4 goals, goal 3575 chars | accepted commit |  |
| T0.0.r2-11 | +42:43 | 13.8 s | 10.2 s | [turn_010.json](./views/c3/Tree_0_0_r2/turn_010.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_010.md) | commit auto; smt(drop0 mem_filter filter_uniq size_eq0 size_ge0) | pRHL / procedure_body / relational_program, 3 goals, goal 4321 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-12 | +43:18 | 24.9 s | 10.1 s | [turn_011.json](./views/c3/Tree_0_0_r2/turn_011.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_011.md) | commit auto => />; smt(drop0 size_eq0 size_ge0 mem_filter filter_uniq) | pRHL / procedure_body / relational_program, 3 goals, goal 4321 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-13 | +43:49 | 20.5 s | 463 ms | [turn_012.json](./views/c3/Tree_0_0_r2/turn_012.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_012.md) | commit auto => /> | pRHL / procedure_body / relational_program, 3 goals, goal 4321 chars | accepted commit |  |
| T0.0.r2-14 | +44:04 | 15.1 s | 9.9 s | [turn_013.json](./views/c3/Tree_0_0_r2/turn_013.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_013.md) | commit smt(drop0 mem_filter filter_uniq size_eq0 size_ge0) | ambient / ambient_logic / relational_program, 3 goals, goal 2889 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-15 | +44:43 | 28.6 s | 375 ms | [turn_014.json](./views/c3/Tree_0_0_r2/turn_014.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_014.md) | commit move=> &2 Hu; rewrite drop0 /=; do ! split | ambient / ambient_logic / relational_program, 3 goals, goal 2889 chars | accepted commit |  |
| T0.0.r2-16 | +44:55 | 11.6 s | 364 ms | [turn_015.json](./views/c3/Tree_0_0_r2/turn_015.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_015.md) | commit by apply/filter_uniq | ambient / ambient_logic / relational_program, 7 goals, goal 1996 chars | accepted commit |  |
| T0.0.r2-17 | +45:06 | 11.4 s | 6.6 s | [turn_016.json](./views/c3/Tree_0_0_r2/turn_016.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_016.md) | commit by move=> n0 /mem_filter [h _]; exact h | ambient / ambient_logic / relational_program, 6 goals, goal 2064 chars | rejected commit: [error] cannot apply view |  |
| T0.0.r2-18 | +45:27 | 13.6 s | 357 ms | [turn_017.json](./views/c3/Tree_0_0_r2/turn_017.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_017.md) | commit by move=> n0; rewrite mem_filter => -[h _] | ambient / ambient_logic / relational_program, 6 goals, goal 2064 chars | accepted commit |  |
| T0.0.r2-19 | +45:36 | 8.6 s | 445 ms | [turn_018.json](./views/c3/Tree_0_0_r2/turn_018.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_018.md) | commit by move=> n0; rewrite mem_filter => -[h _] | ambient / ambient_logic / relational_program, 5 goals, goal 2070 chars | accepted commit |  |
| T0.0.r2-20 | +45:46 | 9.5 s | 465 ms | [turn_019.json](./views/c3/Tree_0_0_r2/turn_019.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_019.md) | commit smt(size_eq0 size_ge0) | ambient / ambient_logic / relational_program, 4 goals, goal 2076 chars | accepted commit |  |
| T0.0.r2-21 | +45:53 | 6.6 s | 442 ms | [turn_020.json](./views/c3/Tree_0_0_r2/turn_020.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_020.md) | commit smt(size_eq0 size_ge0) | ambient / ambient_logic / relational_program, 3 goals, goal 2076 chars | accepted commit |  |
| T0.0.r2-22 | +49:22 | 208.5 s | 516 ms | [turn_021.json](./views/c3/Tree_0_0_r2/turn_021.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_021.md) | commit while (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /... | pRHL / call_site / relational_program, 2 goals, goal 4117 chars | accepted commit |  |
| T0.0.r2-23 | +49:29 | 6.6 s | 7.4 s | [turn_022.json](./views/c3/Tree_0_0_r2/turn_022.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_022.md) | commit inline {1} Orcl.f | pRHL / call_site / relational_program, 3 goals, goal 4099 chars | accepted commit |  |
| T0.0.r2-24 | +49:45 | 9.3 s | 7.7 s | [turn_023.json](./views/c3/Tree_0_0_r2/turn_023.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_023.md) | commit sp 1 1 | pRHL / call_site / relational_program, 3 goals, goal 6959 chars | accepted commit |  |
| T0.0.r2-25 | +50:03 | 9.6 s | 423 ms | [turn_024.json](./views/c3/Tree_0_0_r2/turn_024.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_024.md) | commit rcondf {1} 1 | pRHL / call_site / relational_program, 3 goals, goal 6930 chars | accepted commit |  |
| T0.0.r2-26 | +50:18 | 14.7 s | 7.3 s | [turn_025.json](./views/c3/Tree_0_0_r2/turn_025.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_025.md) | commit move=> &m; skip; smt(drop_nth in_cons head_cons mem_head mem_nth) | hoare / procedure_body / relational_program, 4 goals, goal 2404 chars | accepted commit |  |
| T0.0.r2-27 | +50:43 | 18.2 s | 17.8 s | [turn_026.json](./views/c3/Tree_0_0_r2/turn_026.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_026.md) | commit inline {1} ROout.set; wp; call eqSB2; call eqRO; skip; smt(drop_nth drop_drop in_cons head_co... | pRHL / call_site / seq_cut, 3 goals, goal 4626 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-28 | +51:14 | 12.6 s | 444 ms | [turn_027.json](./views/c3/Tree_0_0_r2/turn_027.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_027.md) | commit inline {1} ROout.set; wp; call eqSB2; call eqRO; skip | pRHL / call_site / seq_cut, 3 goals, goal 4626 chars | accepted commit |  |
| T0.0.r2-29 | +52:04 | 49.5 s | 457 ms | [turn_028.json](./views/c3/Tree_0_0_r2/turn_028.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_028.md) | commit move => &1 &2 [#] hn2 hn1 hf hb hcb hlog hlc hro hl0 hi hu hnotin hne... | ambient / ambient_logic / relational_program, 3 goals, goal 3587 chars | accepted commit |  |
| T0.0.r2-30 | +52:19 | 15.4 s | 617 ms | [turn_029.json](./views/c3/Tree_0_0_r2/turn_029.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_029.md) | commit have hd : drop i{2} ns2{2} = n{2} :: drop (i{2} + 1) ns2{2} by smt(dr... | ambient / ambient_logic / relational_program, 3 goals, goal 3707 chars | accepted commit |  |
| T0.0.r2-31 | +52:31 | 10.6 s | 405 ms | [turn_030.json](./views/c3/Tree_0_0_r2/turn_030.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_030.md) | commit have hn12 : n{1} = n{2} by rewrite hn1 hl0 hd head_cons | ambient / ambient_logic / relational_program, 3 goals, goal 3761 chars | accepted commit |  |
| T0.0.r2-32 | +52:50 | 18.9 s | 11.1 s | [turn_031.json](./views/c3/Tree_0_0_r2/turn_031.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_031.md) | commit smt(drop_drop mem_set cons_uniq mem_drop size_drop size_eq0 size_ge0 in_cons get_setE) | ambient / ambient_logic / relational_program, 3 goals, goal 3779 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0.r2-33 | +53:39 | 37.9 s | 8.1 s | [turn_032.json](./views/c3/Tree_0_0_r2/turn_032.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_032.md) | commit rewrite hn12 hf hb hcb hlog hlc hro /=; move => resL resR mL mR [-> ->] /=; move => r0L r0R b... | ambient / ambient_logic / relational_program, 3 goals, goal 3779 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0.r2-34 | +54:15 | 28.2 s | 809 ms | [turn_033.json](./views/c3/Tree_0_0_r2/turn_033.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_033.md) | commit rewrite hn12 hf hb hcb hlog hlc hro /=; move => resL resR mL mR [-> ->] /=; move => r0L r0R b... | ambient / ambient_logic / relational_program, 3 goals, goal 3779 chars | accepted commit |  |
| T0.0.r2-35 | +54:27 | 10.4 s | 592 ms | [turn_034.json](./views/c3/Tree_0_0_r2/turn_034.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_034.md) | commit auto => />; smt(drop0 size_eq0 size_ge0) | pRHL / procedure_body / relational_program, 2 goals, goal 3461 chars | accepted commit |  |
| T0.0.r2-36 | +54:40 | 12.6 s | 352 ms | [turn_035.json](./views/c3/Tree_0_0_r2/turn_035.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_035.md) | commit by auto => /> | pRHL / procedure_body / relational_program, 1 goal, goal 2360 chars | accepted commit |  |
| T0.0.r2-37 | +54:46 | 6 s |  | [turn_036.json](./views/c3/Tree_0_0_r2/turn_036.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_036.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.0.r2-38 | +54:50 | 3.7 s | 290 ms | [turn_037.json](./views/c3/Tree_0_0_r2/turn_037.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_037.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0.r2-39 | +54:58 | 8 s |  | [turn_038.json](./views/c3/Tree_0_0_r2/turn_038.json) · [inline read](./views/c3/Tree_0_0_r2/followups/turn_038.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
