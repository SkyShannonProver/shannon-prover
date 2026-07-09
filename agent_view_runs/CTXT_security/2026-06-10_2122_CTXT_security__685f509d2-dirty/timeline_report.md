# Agent-View Timeline — `CTXT_security`

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-10_2122_CTXT_security |
| lemma | `CTXT_security` |
| source file | `eval/examples/MEE-CBC/RCPA_CMA.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 36 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 0 tactic(s) committed, not closed (timeline replay — no session history survived)

```easycrypt
proof.
  (* no tactic committed *)
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  have [dec [dec_sem enc_corr]] := dec_op.
  byequiv (_: ={glob A, glob E, glob M} ==> res{1} => res{2}) => //.
  proc; inline *.
  swap{2} 4 -3.
  call (_: MACa.SUF_CMA.SUF_Wrap.win, ={glob E, glob M} /\ CTXT_Wrap.k{1} = (CMAa.ek, MACa.SUF_CMA.SUF_Wrap.k){2} /\ CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\ !CTXT_Wrap.win{1} /\ (forall ct, ct \in CTXT_Wrap.s{1} => dec CMAa.ek{2} ct.`1 <> None)).
  exact A_forge_ll.
  proc; inline *.
  exists* CMAa.ek{2}, p{2}; elim* => ek_ p_.
  wp; call (_: true); wp.
  call (_: ={glob E, k, p} /\ k{1} = ek_ /\ p{1} = p_ ==> ={glob E, res} /\ dec ek_ res{1} = Some p_).
  conseq (_: ={glob E, k, p} ==> ={glob E, res}) (enc_corr ek_ p_) _ => //.
  by proc true.
  auto => />; smt(in_fsetU in_fset1).
  move=> &2 _; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.
  move=> &1; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.
  proc; inline *.
  seq 6 4: (={glob E, glob M} /\ CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\ CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\ !CTXT_Wrap.win{1} /\ !MACa.SUF_CMA.SUF_Wrap.win{2} /\ (forall ct0, ct0 \in CTXT_Wrap.s{1} => dec CMAa.ek{2} ct0.`1 <> None) /\ b{1} = b0{2} /\ c0{1} = m{2} /\ t{1} = t0{2} /\ c{1} = (m{2}, t0{2}) /\ ek{1} = CMAa.ek{2} /\ p0{1} = None).
  call (_: true); auto => /> /#.
  if{1}.
  exists* (glob E){1}, ek{1}, c0{1}; elim* => ge ek_ c_; wp; call{1} (_: (glob E) = ge /\ k = ek_ /\ c = c_ ==> (glob E) = ge /\ res = dec ek_ c_).
  by conseq E_dec_ll (dec_sem ge ek_ c_).
  auto => /> /#.
  auto => />.
  move=> &2 _; proc; inline *; seq 6: true 1%r 1%r 0%r _ => //; [by call M_verify_ll; auto | if; [by wp; call E_dec_ll; auto | by auto]].
  move=> &1; proc; inline *; wp; call M_verify_ll; auto => />.
  wp; call (_: true); call (_: true); auto => />; smt(in_fset0).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_2122_CTXT_security

Run dir: `artifacts/eval_suite/mee_ctxt_fable_l1/l1_goal_projection/mee_CTXT_security/r01/2026-06-10_2122_CTXT_security/iteration_1`

t=0: `2026-06-11T04:26:21.100000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 |  | 2.9 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit have [dec [dec_sem enc_corr]] := dec_op | probability / pr / probability, 1 goal, goal 223 chars | accepted commit |  |
| T0.1-2 | +00:11 | 7.8 s | 171 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit byequiv (_: ={glob A, glob E, glob M} ==> res{1} => res{2}) => // | probability / pr / probability, 1 goal, goal 570 chars | accepted commit |  |
| T0.1-3 | +00:18 | 6.6 s | 2.4 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 660 chars | accepted commit |  |
| T0.1-4 | +00:28 | 8.6 s | 2.4 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit swap{2} 4 -3 | pRHL / call_site / relational_program, 1 goal, goal 1402 chars | accepted commit |  |
| T0.1-5 | +00:43 | 11.8 s | 181 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit call (_: ={glob E, glob M} /\ CTXT_Wrap.k{1} = (CMAa.ek, MACa.SUF_CMA... | pRHL / call_site / relational_program, 1 goal, goal 1402 chars | accepted commit |  |
| T0.1-6 | +00:53 | 9.9 s | 5.1 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc; inline * | equiv / prhl_module / relational_program, 3 goals, goal 1067 chars | accepted commit |  |
| T0.1-7 | +01:09 | 10.8 s | 193 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit wp; call (_: true); wp; call (_: true); auto => /> | pRHL / call_site / seq_cut, 3 goals, goal 1914 chars | accepted commit |  |
| T0.1-8 | +01:16 | 7.6 s | 2.4 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit proc; inline * | equiv / prhl_module / relational_program, 2 goals, goal 1073 chars | accepted commit |  |
| T0.1-9 | +03:58 | 159.6 s | 2.4 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | undo_last_step | pRHL / call_site / seq_cut, 2 goals, goal 2661 chars | undo result |  |
| T0.1-10 | +04:11 | 9.7 s | 2.3 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | undo_last_step | equiv / prhl_module / seq_cut, 2 goals, goal 1060 chars | undo result |  |
| T0.1-11 | +04:20 | 6.8 s | 2.2 s | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | undo_last_step | pRHL / call_site / seq_cut, 3 goals, goal 1901 chars | undo result |  |
| T0.1-12 | +04:28 | 5.7 s | 2.3 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | undo_last_step | equiv / prhl_module / seq_cut, 3 goals, goal 1054 chars | undo result |  |
| T0.1-13 | +04:42 | 12.6 s | 2.4 s | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit call MACa.SUF_CMA.SUF_Wrap.win | pRHL / call_site / seq_cut, 1 goal, goal 1389 chars | accepted commit |  |
| T0.1-14 | +04:54 | 8.8 s | 174 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit exact A_forge_ll | ambient / ambient_logic, 8 goals, goal 578 chars | accepted commit |  |
| T0.1-15 | +05:24 | 29.6 s | 2.4 s | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit proc; inline * | equiv / prhl_module / relational_program, 7 goals, goal 1263 chars | accepted commit |  |
| T0.1-16 | +05:33 | 6.7 s | 2.3 s | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit exists* CMAa.ek{2}, p{2}; elim* => ek_ p_ | pRHL / call_site / seq_cut, 7 goals, goal 2110 chars | accepted commit |  |
| T0.1-17 | +05:42 | 6.7 s | 2.3 s | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit wp; call (_: true); wp | pRHL / call_site / seq_cut, 7 goals, goal 2164 chars | accepted commit |  |
| T0.1-18 | +05:55 | 10.8 s | 191 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit call (_: ={glob E, k, p} /\ k{1} = ek_ /\ p{1} = p_ ==> ={glob E, res... | pRHL / call_site / seq_cut, 7 goals, goal 1997 chars | accepted commit |  |
| T0.1-19 | +06:04 | 8.8 s | 181 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit conseq (_: ={glob E, k, p} ==> ={glob E, res}) (enc_corr ek_ p_) _ => // | equiv / prhl_module / relational_program, 8 goals, goal 696 chars | accepted commit |  |
| T0.1-20 | +06:15 | 10.8 s | 218 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit by proc true | equiv / prhl_module / relational_program, 8 goals, goal 631 chars | accepted commit |  |
| T0.1-21 | +06:26 | 10.8 s | 247 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit auto => />; smt(in_fsetU in_fset1) | pRHL / procedure_body / relational_program, 7 goals, goal 2304 chars | accepted commit |  |
| T0.1-22 | +06:41 | 14.8 s | 188 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit move=> &2 _; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto | ambient / ambient_logic, 6 goals, goal 560 chars | accepted commit |  |
| T0.1-23 | +07:00 | 18.8 s | 179 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit move=> &1; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto | phoare / procedure_body / procedure_frontier, 5 goals, goal 651 chars | accepted commit |  |
| T0.1-24 | +07:25 | 25.1 s | 4.9 s | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit proc; inline * | equiv / prhl_module / relational_program, 4 goals, goal 1272 chars | accepted commit |  |
| T0.1-25 | +08:00 | 30.5 s | 2.5 s | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit seq 6 4: (={glob E, glob M} /\ CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF... | pRHL / call_site / seq_cut, 4 goals, goal 2863 chars | accepted commit |  |
| T0.1-26 | +08:09 | 6.5 s | 2.5 s | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | commit call (_: true); auto => /> /# | pRHL / call_site / seq_cut, 5 goals, goal 2065 chars | accepted commit |  |
| T0.1-27 | +08:20 | 8.3 s | 2.7 s | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit if{1} | pRHL / call_site / relational_program, 4 goals, goal 2293 chars | accepted commit |  |
| T0.1-28 | +08:40 | 16.8 s | 169 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit exists* (glob E){1}, ek{1}, c0{1}; elim* => ge ek_ c_; wp; call{1} (_: (glob E) = ge /\ k = e... | pRHL / call_site / relational_program, 5 goals, goal 2165 chars | accepted commit |  |
| T0.1-29 | +08:49 | 8.8 s | 196 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit by conseq E_dec_ll (dec_sem ge ek_ c_) | phoare / procedure_body / procedure_frontier, 6 goals, goal 620 chars | accepted commit |  |
| T0.1-30 | +09:00 | 10.7 s | 294 ms | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit auto => /> /# | pRHL / procedure_body / relational_program, 5 goals, goal 1934 chars | accepted commit |  |
| T0.1-31 | +09:08 | 8.3 s | 2.7 s | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | commit auto => /> | pRHL / procedure_body / relational_program, 4 goals, goal 2103 chars | accepted commit |  |
| T0.1-32 | +09:50 | 39.3 s | 2.7 s | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit move=> &2 _; proc; inline *; seq 6: true 1%r 1%r 0%r _ => //; [by call M_verify_ll; auto \| if... | ambient / ambient_logic, 3 goals, goal 563 chars | accepted commit |  |
| T0.1-33 | +10:10 | 17.2 s | 2.8 s | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | commit move=> &1; proc; inline *; wp; call M_verify_ll; auto => /> | phoare / procedure_body / procedure_frontier, 2 goals, goal 654 chars | accepted commit |  |
| T0.1-34 | +10:26 | 12.7 s | 265 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit wp; call (_: true); call (_: true); auto => />; smt(in_fset0) | pRHL / call_site / relational_program, 1 goal, goal 2000 chars | accepted commit |  |
| T0.1-35 | +10:32 | 5.9 s | 139 ms | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-36 | +11:12 | 40 s |  | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
