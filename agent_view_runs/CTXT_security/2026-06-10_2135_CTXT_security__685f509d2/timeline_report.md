# Agent-View Timeline — `CTXT_security`

| field | value |
|---|---|
| commit | `685f509d2` |
| branch | `HEAD` |
| run time | 2026-06-10_2135_CTXT_security |
| lemma | `CTXT_security` |
| source file | `eval/examples/MEE-CBC/RCPA_CMA.ec` |
| model | `claude-fable-5` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 59 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 21 tactic(s) committed, not closed

```easycrypt
proof.
  have [dec [dec_sem E_corr]]:= dec_op.
  byequiv (_: ={glob A, glob E, glob M} ==> res{1} => res{2}) => //.
  proc.
  inline *.
  swap{2} 4 -3.
  call (_: MACa.SUF_CMA.SUF_Wrap.win, ={glob E, glob M} /\ CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\ CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\ CTXT_Wrap.win{1} = MACa.SUF_CMA.SUF_Wrap.win{2} /\ (forall ct, mem MACa.SUF_CMA.SUF_Wrap.s{2} ct => dec CMAa.ek{2} ct.`1 <> None)).
  exact A_forge_ll.
  have enc_corr_eq: forall _k _p, equiv [E.enc ~ E.enc : ={glob E, k, p} /\ k{1} = _k /\ p{1} = _p ==> ={glob E, res} /\ dec _k res{1} = Some _p].
  by move=> _k _p; conseq (_: ={glob E, k, p} ==> ={glob E, res}) (E_corr _k _p) _ => //; proc true.
  proc; inline *.
  exists* CTXT_Wrap.k{1}, p{1}; elim* => kk pp; sp; wp; call (_: true); wp; call (enc_corr_eq kk.`1 pp).
  by skip; smt(in_fsetU in_fset1).
  by move=> &2 _; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.
  by move=> &2; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.
  have dec_ph: forall (ge : (glob E)) _k _c, phoare [E.dec : (glob E) = ge /\ k = _k /\ c = _c ==> (glob E) = ge /\ res = dec _k _c] = 1%r.
  by move=> ge _k _c; conseq E_dec_ll (dec_sem ge _k _c).
  proc; inline *.
  sp; seq 1 1: (!MACa.SUF_CMA.SUF_Wrap.win{2} /\ b{1} = b0{2} /\ c0{1} = m{2} /\ c{1} = (m{2}, t0{2}) /\ ek{1} = CMAa.ek{2} /\ p0{1} = None /\ (glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2} /\ CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\ CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\ CTXT_Wrap.win{1} = MACa.SUF_CMA.SUF_Wrap.win{2} /\ (forall ct0, ct0 \in MACa.SUF_CMA.SUF_Wrap.s{2} => dec CMAa.ek{2} ct0.`1 <> None)).
  by call (_: true); skip; smt().
  if{1}; [exists* (glob E){1}, ek{1}, c0{1}; elim* => ge kk cc; wp; call{1} (dec_ph ge kk cc); skip; smt() | by wp; skip; smt()].
  by move=> &2 _; proc; wp; call (EtM_dec_ll E M E_dec_ll M_verify_ll); auto.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  have [dec [dec_sem enc_corr]] := dec_op.
  have dec_ph: forall ge k0 c0, phoare [E.dec: (glob E) = ge /\ k = k0 /\ c = c0 ==> (glob E) = ge /\ res = dec k0 c0] = 1%r by move=> ge k0 c0; conseq E_dec_ll (dec_sem ge k0 c0).
  have enc_eq: forall k0 p0, equiv [E.enc ~ E.enc: ={glob E, k, p} /\ k{1} = k0 /\ p{1} = p0 ==> ={glob E, res} /\ dec k0 res{1} = Some p0].
  move=> k0 p0; conseq (_: ={glob E, k, p} ==> ={glob E, res}) (enc_corr k0 p0) _ => //.
  by proc true.
  byequiv (_: ={glob A, glob E, glob M} ==> res{1} => res{2}) => //.
  proc; inline *.
  swap{2} 4 -3.
  call (_: MACa.SUF_CMA.SUF_Wrap.win, ={glob E, glob M} /\ CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\ CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\ !CTXT_Wrap.win{1} /\ (forall c t, (c, t) \in MACa.SUF_CMA.SUF_Wrap.s{2} => dec CMAa.ek{2} c <> None)).
  exact A_forge_ll.
  proc; inline *.
  sp 3 0; exlim ek{1}, p0{1} => ek0 pp0; wp; call (_: true); wp; call (enc_eq ek0 pp0); skip; smt(in_fsetU in_fset1).
  move=> &2 _; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.
  move=> &1; proc; conseq (_: _ ==> true: =1%r) (_: MACa.SUF_CMA.SUF_Wrap.win ==> MACa.SUF_CMA.SUF_Wrap.win) => //.
  inline *; wp; call (_: MACa.SUF_CMA.SUF_Wrap.win); wp; call (_: MACa.SUF_CMA.SUF_Wrap.win); auto.
  inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.
  proc; inline *.
  sp 5 3.
  seq 1 1: (b{1} = b0{2} /\ c0{1} = m{2} /\ t{1} = t0{2} /\ c{1} = (m{2}, t0{2}) /\ ek{1} = CMAa.ek{2} /\ p0{1} = None /\ ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\ CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\ CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\ !CTXT_Wrap.win{1} /\ !MACa.SUF_CMA.SUF_Wrap.win{2} /\ (forall (c1 : ctxt) (t1 : tag), (c1, t1) \in MACa.SUF_CMA.SUF_Wrap.s{2} => dec CMAa.ek{2} c1 <> None)).
  call (_: true); skip; smt().
  case (b{1}).
  rcondt{1} 1; first by auto. exlim (glob E){1}, ek{1}, c0{1} => ge ek0 cc0; wp; call{1} (dec_ph ge ek0 cc0); skip; smt().
  rcondf{1} 1; first by auto. by wp; skip; smt().
  move=> &2 _; proc; inline *; sp; seq 1: true => //; first by call M_verify_ll.
  by if; [wp; call E_dec_ll; auto | auto].
  move=> &1; proc; conseq (_: _ ==> true: =1%r) (_: MACa.SUF_CMA.SUF_Wrap.win ==> MACa.SUF_CMA.SUF_Wrap.win) => //.
  inline *; wp; call (_: MACa.SUF_CMA.SUF_Wrap.win); auto.
  by smt().
  by inline *; wp; call M_verify_ll; auto.
  by wp; call (_: true); call (_: true); skip; smt(in_fset0).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_2135_CTXT_security

Run dir: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1`

t=0: `2026-06-11T04:36:14.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 223 chars | read-only inspect |  |
| T0.0-2 | +01:23 | 80.5 s | 523 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit have [dec [dec_sem E_corr]]:= dec_op | probability / pr / probability, 1 goal, goal 223 chars | accepted commit |  |
| T0.0-3 | +01:33 | 9.8 s | 205 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit byequiv (_: ={glob A, glob E, glob M} ==> res{1} => res{2}) => // | probability / pr / probability, 1 goal, goal 566 chars | accepted commit |  |
| T0.0-4 | +01:40 | [6.8 s](./views/Tree_0_0/thinking/turn_004.md) | 180 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 656 chars | accepted commit |  |
| T0.0-5 | +02:01 | 20.4 s | 2.6 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline * | pRHL / procedure_body / relational_program, 1 goal, goal 814 chars | accepted commit |  |
| T0.0-6 | +02:39 | [35.5 s](./views/Tree_0_0/thinking/turn_006.md) | 2.5 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit swap{2} 4 -3 | pRHL / call_site / relational_program, 1 goal, goal 1398 chars | accepted commit |  |
| T0.0-7 | +02:55 | [12.9 s](./views/Tree_0_0/thinking/turn_007.md) | 99 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 1 goal, goal 1398 chars | read-only inspect |  |
| T0.0-8 | +03:04 | 9 s |  | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | inspect call_site_options | pRHL / call_site / failure_diagnostic, 1 goal, goal 1398 chars | read-only inspect |  |
| T0.0-9 | +04:52 | 108.6 s | 2.4 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit call MACa.SUF_CMA.SUF_Wrap.win | pRHL / call_site / failure_diagnostic, 1 goal, goal 1398 chars | accepted commit |  |
| T0.0-10 | +05:08 | [13.8 s](./views/Tree_0_0/thinking/turn_010.md) | 191 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit exact A_forge_ll | ambient / ambient_logic, 8 goals, goal 574 chars | accepted commit |  |
| T0.0-11 | +05:49 | 40.8 s | 167 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit have enc_corr_eq: forall _k _p, equiv [E.enc ~ E.enc : ={glob E, k, p... | equiv / prhl_module / relational_program, 7 goals, goal 1343 chars | accepted commit |  |
| T0.0-12 | +06:04 | [14.8 s](./views/Tree_0_0/thinking/turn_012.md) | 230 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit by move=> _k _p; conseq (_: ={glob E, k, p} ==> ={glob E, res}) (E_corr _k _p) _ => //; proc... | ambient / ambient_logic / relational_program, 8 goals, goal 734 chars | accepted commit |  |
| T0.0-13 | +06:42 | [37.5 s](./views/Tree_0_0/thinking/turn_013.md) | 2.5 s | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit proc; inline * | equiv / prhl_module / relational_program, 7 goals, goal 1704 chars | accepted commit |  |
| T0.0-14 | +07:13 | 28.8 s | 204 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit exists* CTXT_Wrap.k{1}, p{1}; elim* => kk pp; sp; wp; call (_: true); wp; call (enc_corr_eq k... | pRHL / call_site / seq_cut, 7 goals, goal 2551 chars | accepted commit |  |
| T0.0-15 | +07:30 | [16.8 s](./views/Tree_0_0/thinking/turn_015.md) | 250 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit by skip; smt(in_fsetU in_fset1) | pRHL / procedure_body / relational_program, 7 goals, goal 2642 chars | accepted commit |  |
| T0.0-16 | +07:55 | 24.9 s | 149 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit by move=> &2 _; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto | ambient / ambient_logic, 6 goals, goal 556 chars | accepted commit |  |
| T0.0-17 | +08:27 | [31.7 s](./views/Tree_0_0/thinking/turn_017.md) | 251 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit by move=> &2; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto | phoare / procedure_body / procedure_frontier, 5 goals, goal 647 chars | accepted commit |  |
| T0.0-18 | +08:58 | 30.8 s | 161 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit have dec_ph: forall (ge : (glob E)) _k _c, phoare [E.dec : (glob E) =... | equiv / prhl_module / relational_program, 4 goals, goal 1356 chars | accepted commit |  |
| T0.0-19 | +09:04 | 5.8 s | 183 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit by move=> ge _k _c; conseq E_dec_ll (dec_sem ge _k _c) | phoare / procedure_body / procedure_frontier, 5 goals, goal 639 chars | accepted commit |  |
| T0.0-20 | +09:13 | [8.6 s](./views/Tree_0_0/thinking/turn_020.md) | 2.4 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit proc; inline * | equiv / prhl_module / relational_program, 4 goals, goal 1552 chars | accepted commit |  |
| T0.0-21 | +10:12 | 56.3 s | 4.7 s | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit sp; seq 1 1: (!MACa.SUF_CMA.SUF_Wrap.win{2} /\ b{1} = b0{2} /\ c0{1} = m{2} /\ c{1} = (m{2},... | pRHL / call_site / seq_cut, 4 goals, goal 3147 chars | accepted commit |  |
| T0.0-22 | +10:28 | [11.5 s](./views/Tree_0_0/thinking/turn_022.md) | 2.5 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit by call (_: true); skip; smt() | pRHL / call_site / relational_program, 5 goals, goal 2162 chars | accepted commit |  |
| T0.0-23 | +10:52 | 21.6 s | 371 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit if{1}; [exists* (glob E){1}, ek{1}, c0{1}; elim* => ge kk cc; wp; call{1} (dec_ph ge kk cc);... | pRHL / call_site / relational_program, 4 goals, goal 2560 chars | accepted commit |  |
| T0.0-24 | +11:24 | [31.4 s](./views/Tree_0_0/thinking/turn_024.md) | 2.6 s | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit by move=> &2 _; proc; wp; call (EtM_dec_ll E M E_dec_ll M_verify_ll); auto | ambient / ambient_logic, 3 goals, goal 559 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +03:48 |  | 2.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | lookup enc_eq | probability / pr / probability, 1 goal, goal 223 chars | lookup result |  |
| T0.1-2 | +03:59 | 8.1 s | 2.9 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit have [dec [dec_sem enc_corr]] := dec_op | probability / pr / probability, 1 goal, goal 223 chars | accepted commit |  |
| T0.1-3 | +04:08 | 6.5 s | 527 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit have dec_ph: forall ge k0 c0, phoare [E.dec: (glob E) = ge /\ k = k0 /\ c = c0 ==> (glob E) =... | probability / pr / probability, 1 goal, goal 570 chars | accepted commit |  |
| T0.1-4 | +04:31 | 22.8 s | 169 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit have enc_eq: forall k0 p0, equiv [E.enc ~ E.enc: ={glob E, k, p} /\ k... | probability / pr / probability, 1 goal, goal 766 chars | accepted commit |  |
| T0.1-5 | +04:40 | 8.8 s | 187 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit move=> k0 p0; conseq (_: ={glob E, k, p} ==> ={glob E, res}) (enc_corr k0 p0) _ => // | ambient / ambient_logic / relational_program, 2 goals, goal 934 chars | accepted commit |  |
| T0.1-6 | +04:46 | 5.5 s | 528 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit by proc true | equiv / prhl_module / relational_program, 2 goals, goal 826 chars | accepted commit |  |
| T0.1-7 | +04:54 | 7.8 s | 188 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit byequiv (_: ={glob A, glob E, glob M} ==> res{1} => res{2}) => // | probability / pr / probability, 1 goal, goal 1073 chars | accepted commit |  |
| T0.1-8 | +05:04 | 9.2 s | 2.8 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 1163 chars | accepted commit |  |
| T0.1-9 | +05:35 | 28.4 s | 2.6 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit swap{2} 4 -3 | pRHL / call_site / relational_program, 1 goal, goal 1905 chars | accepted commit |  |
| T0.1-10 | +05:48 | 10.8 s | 209 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit call MACa.SUF_CMA.SUF_Wrap.win | pRHL / call_site / relational_program, 1 goal, goal 1905 chars | accepted commit |  |
| T0.1-11 | +05:55 | 6.8 s | 170 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit exact A_forge_ll | ambient / ambient_logic / relational_program, 8 goals, goal 1081 chars | accepted commit |  |
| T0.1-12 | +06:05 | 9.6 s | 2.4 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit proc; inline * | equiv / prhl_module / relational_program, 7 goals, goal 1796 chars | accepted commit |  |
| T0.1-13 | +06:41 | 33.7 s | 256 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit sp 3 0; exlim ek{1}, p0{1} => ek0 pp0; wp; call (_: true); wp; call (enc_eq ek0 pp0); skip; s... | pRHL / call_site / seq_cut, 7 goals, goal 2661 chars | accepted commit |  |
| T0.1-14 | +06:53 | 11.8 s | 177 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit move=> &2 _; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto | ambient / ambient_logic / relational_program, 6 goals, goal 1063 chars | accepted commit |  |
| T0.1-15 | +07:28 | 34.8 s | 225 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit move=> &1; proc; conseq (_: _ ==> true: =1%r) (_: MACa.SUF_CMA.SUF_Wrap.win ==> MACa.SUF_CMA.... | phoare / procedure_body / relational_program, 5 goals, goal 1154 chars | accepted commit |  |
| T0.1-16 | +07:39 | 10.8 s | 168 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit inline *; wp; call (_: MACa.SUF_CMA.SUF_Wrap.win); wp; call (_: MACa.SUF_CMA.SUF_Wrap.win); auto | hoare / procedure_body / relational_program, 6 goals, goal 1185 chars | accepted commit |  |
| T0.1-17 | +07:45 | 5.8 s | 181 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto | phoare / procedure_body / relational_program, 5 goals, goal 1189 chars | accepted commit |  |
| T0.1-18 | +07:51 | 5.6 s | 2.4 s | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit proc; inline * | equiv / prhl_module / relational_program, 4 goals, goal 1809 chars | accepted commit |  |
| T0.1-19 | +08:43 | 49 s | 3 s | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit sp 5 3 | pRHL / call_site / seq_cut, 4 goals, goal 3408 chars | accepted commit |  |
| T0.1-20 | +08:54 | 8.3 s | 2.7 s | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit seq 1 1: (b{1} = b0{2} /\ c0{1} = m{2} /\ t{1} = t0{2} /\ c{1} = (m{2... | pRHL / call_site / seq_cut, 4 goals, goal 3228 chars | accepted commit |  |
| T0.1-21 | +09:07 | 10.4 s | 2.6 s | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit call (_: true); skip; smt() | pRHL / call_site / relational_program, 5 goals, goal 2441 chars | accepted commit |  |
| T0.1-22 | +09:20 | 10.3 s | 2.7 s | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit case (b{1}) | pRHL / call_site / relational_program, 4 goals, goal 2839 chars | accepted commit |  |
| T0.1-23 | +09:36 | 13.9 s | 5.1 s | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit rcondt{1} 1; first by auto. exlim (glob E){1}, ek{1}, c0{1} => ge ek0 cc0; wp; call{1} (dec_p... | pRHL / call_site / relational_program, 5 goals, goal 2864 chars | accepted commit |  |
| T0.1-24 | +10:12 | 30.7 s | 273 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit rcondf{1} 1; first by auto. by wp; skip; smt() | pRHL / call_site / relational_program, 4 goals, goal 2865 chars | accepted commit |  |
| T0.1-25 | +11:06 | 53.7 s | 2.3 s | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | lookup M_verify_ll | ambient / ambient_logic / relational_program, 3 goals, goal 1066 chars | lookup result |  |
| T0.1-26 | +11:33 | 24.3 s | 2.7 s | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit move=> &2 _; proc; inline *; sp; seq 1: true => //; first by call M_verify_ll | ambient / ambient_logic / relational_program, 3 goals, goal 1066 chars | accepted commit |  |
| T0.1-27 | +11:41 | 5.8 s | 196 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit by if; [wp; call E_dec_ll; auto \| auto] | phoare / procedure_body / relational_program, 3 goals, goal 1582 chars | accepted commit |  |
| T0.1-28 | +11:59 | 17.1 s | 2.9 s | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit move=> &1; proc; conseq (_: _ ==> true: =1%r) (_: MACa.SUF_CMA.SUF_Wrap.win ==> MACa.SUF_CMA.... | phoare / procedure_body / relational_program, 2 goals, goal 1157 chars | accepted commit |  |
| T0.1-29 | +12:12 | 10.8 s | 196 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit inline *; wp; call (_: MACa.SUF_CMA.SUF_Wrap.win); auto | hoare / procedure_body / relational_program, 3 goals, goal 1214 chars | accepted commit |  |
| T0.1-30 | +12:17 | 4.7 s | 265 ms | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit by smt() | ambient / ambient_logic / relational_program, 3 goals, goal 1237 chars | accepted commit |  |
| T0.1-31 | +12:24 | 6 s | 3 s | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit by inline *; wp; call M_verify_ll; auto | phoare / procedure_body / relational_program, 2 goals, goal 1218 chars | accepted commit |  |
| T0.1-32 | +12:37 | 10.8 s | 250 ms | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit by wp; call (_: true); call (_: true); skip; smt(in_fset0) | pRHL / call_site / relational_program, 1 goal, goal 2521 chars | accepted commit |  |
| T0.1-33 | +12:42 | 4 s |  | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.1-34 | +12:45 | 3.9 s | 143 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-35 | +12:49 | 3 s |  | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
