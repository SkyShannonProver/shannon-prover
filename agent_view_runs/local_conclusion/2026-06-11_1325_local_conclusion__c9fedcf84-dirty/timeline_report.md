# Agent-View Timeline — `local_conclusion`

| field | value |
|---|---|
| commit | `c9fedcf84` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1325_local_conclusion |
| lemma | `local_conclusion` |
| source file | `eval/examples/MEE-CBC/MAC_then_Pad_then_CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 3 |
| eval mode | True |
| outcome | proved |
| turns | 53 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 22 tactic(s) committed, not closed

```easycrypt
proof.
  rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m).
  have <-: Pr[CBCa.SKEa.RCPA.INDR_CPA(Random, QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)))).main() @ &m : res] = Pr[CBCa.SKEa.RCPA.INDR_CPA(CBCa.SKEa.RCPA.Ideal, QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)))).main() @ &m : res].
  byequiv=> //=; proc; inline *.
  wp; call (_: ={OracleBounder.qC, RCPA_WUF_RCPA.RCPAa.mk}); last by auto.
  proc; inline MAC.tag.
  inline{1} RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(Random)).O').S.enc; inline{2} RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(CBCa.SKEa.RCPA.Ideal)).O').S.enc.
  inline{1} QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(Random)).O'.enc; inline{2} QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(CBCa.SKEa.RCPA.Ideal)).O'.enc.
  inline{1} CBCa.SKEa.RCPA.RCPA_Wrap(Random).enc; inline{2} CBCa.SKEa.RCPA.RCPA_Wrap(CBCa.SKEa.RCPA.Ideal).enc.
  sp; if=> //.
  by wp; call Random_Ideal; auto=> />.
  by wp; while (={i, r, p0}); auto=> />.
  have H := CBCa.Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))) &m.
  have ->: Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)))).main() @ &m : res] = Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PRPr.PseudoRP)), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)))).main() @ &m : res].
  byequiv=> //=; sim.
  have ->: Pr[IND(PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main() @ &m : res] = Pr[PRFt.IND(PRPr.PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main() @ &m : res].
  byequiv=> //=; sim.
  have ->: Pr[IND(PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main() @ &m : res] = Pr[PRFt.IND(PRPi.PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main() @ &m : res].
  byequiv=> //=; sim.
  apply H.
  move=> O enc_ll; islossless.
  apply (A_distinguish_ll (<: RCPA_WUF_RCPA.RCPAa(MAC, A, RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), O).S).Sim) _).
  islossless.
  (* proof not completed in this run *)
```

### `Tree_0_1` — incomplete — 13 tactic(s) committed, not closed

```easycrypt
proof.
  rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m).
  have <-: Pr[CBCa.SKEa.RCPA.INDR_CPA(Random,QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m: res] = Pr[CBCa.SKEa.RCPA.INDR_CPA(CBCa.SKEa.RCPA.Ideal,QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m: res].
  byequiv=> //=; proc; inline *; wp; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}).
  proc; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}).
  call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}); auto.
  sp; if; first by smt().
  wp; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}); auto.
  call Random_Ideal; auto.
  by sim.
  by inline *; auto.
  by auto.
  have CC := Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A))) &m.
  have eL: Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m : res] = Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PRPr.PseudoRP)), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m : res].
  (* proof not completed in this run *)
```

### `Tree_0_1_r1` — proved

```easycrypt
proof.
  rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m).
  have <-: Pr[CBCa.SKEa.RCPA.INDR_CPA(Random,QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m: res] = Pr[CBCa.SKEa.RCPA.INDR_CPA(CBCa.SKEa.RCPA.Ideal,QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m: res].
  byequiv=> //=; proc; inline *; wp; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}).
  proc; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}).
  call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}); auto.
  sp; if; first by smt().
  wp; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}); auto.
  call Random_Ideal; auto.
  by sim.
  by inline *; auto.
  by auto.
  have CC := Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A))) &m.
  have eL: Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m : res] = Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PRPr.PseudoRP)), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A)))).main() @ &m : res].
  byequiv=> //=; sim.
  rewrite eL.
  have ->: Pr[IND(PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main () @ &m : res] = Pr[PRFt.IND(PRPr.PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main () @ &m : res] by byequiv=> //=; sim.
  have ->: Pr[IND(PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main () @ &m : res] = Pr[PRFt.IND(PRPi.PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main () @ &m : res] by byequiv=> //=; sim.
  apply CC.
  move=> O O_enc_ll; proc.
  call (A_distinguish_ll (<: RCPA_WUF_RCPA.RCPAa(MAC, A, RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), O).S).Sim)).
  by proc; inline *; wp; call O_enc_ll; auto.
  by inline *; auto; smt(d_mK_uffu).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1325_local_conclusion

Run dir: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1`

t=0: `2026-06-11T20:32:37.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +03:07 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m) | probability / pr / probability, 1 goal, goal 569 chars | accepted commit |  |
| T0.0-2 | +03:21 | 11.5 s | 487 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit have <-: Pr[CBCa.SKEa.RCPA.INDR_CPA(Random, QueryBounder(RCPAa(RCPA_W... | probability / pr / probability, 1 goal, goal 689 chars | accepted commit |  |
| T0.0-3 | +03:32 | 10.7 s | 270 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit byequiv=> //=; proc; inline * | probability / pr / probability, 2 goals, goal 416 chars | accepted commit |  |
| T0.0-4 | +03:46 | 13.8 s | 180 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit wp; call (_: ={OracleBounder.qC, RCPA_WUF_RCPA.RCPAa.mk}); last by auto | pRHL / call_site / relational_program, 2 goals, goal 3147 chars | accepted commit |  |
| T0.0-5 | +04:18 | 31.7 s | 258 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit proc; inline MAC.tag | equiv / prhl_module / relational_program, 2 goals, goal 829 chars | accepted commit |  |
| T0.0-6 | +04:34 | [15.8 s](./views/Tree_0_0/thinking/turn_006.md) | 248 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit inline{1} RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)),... | pRHL / call_site / relational_program, 2 goals, goal 1934 chars | accepted commit |  |
| T0.0-7 | +04:46 | [11.8 s](./views/Tree_0_0/thinking/turn_007.md) | 207 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit inline{1} QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(Random)).... | pRHL / call_site / relational_program, 2 goals, goal 1832 chars | accepted commit |  |
| T0.0-8 | +05:10 | [23.8 s](./views/Tree_0_0/thinking/turn_008.md) | 211 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit inline{1} CBCa.SKEa.RCPA.RCPA_Wrap(Random).enc; inline{2} CBCa.SKEa.RCPA.RCPA_Wrap(CBCa.SKEa.... | pRHL / call_site / relational_program, 2 goals, goal 3077 chars | accepted commit |  |
| T0.0-9 | +05:31 | [20.8 s](./views/Tree_0_0/thinking/turn_009.md) | 229 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit sp; if=> // | pRHL / call_site / relational_program, 2 goals, goal 3407 chars | accepted commit |  |
| T0.0-10 | +05:42 | [10.8 s](./views/Tree_0_0/thinking/turn_010.md) | 195 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit by wp; call Random_Ideal; auto=> /> | pRHL / call_site / relational_program, 3 goals, goal 1972 chars | accepted commit |  |
| T0.0-11 | +05:54 | [11.4 s](./views/Tree_0_0/thinking/turn_011.md) | 578 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit by wp; while (={i, r, p0}); auto=> /> | pRHL / verification_residue / relational_program, 2 goals, goal 1340 chars | accepted commit |  |
| T0.0-12 | +06:16 | [21.4 s](./views/Tree_0_0/thinking/turn_012.md) | 2.6 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit apply/(Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))) &m) | probability / pr / probability, 1 goal, goal 675 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-13 | +06:54 | [35.4 s](./views/Tree_0_0/thinking/turn_013.md) | 2.6 s | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit apply/(CBCa.Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))) &m) | probability / pr / probability, 1 goal, goal 675 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-14 | +07:47 | [50.4 s](./views/Tree_0_0/thinking/turn_014.md) | 2.6 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit apply/(CBCa.Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))) &m _) | probability / pr / probability, 1 goal, goal 675 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-15 | +08:55 | [65.4 s](./views/Tree_0_0/thinking/turn_015.md) | 613 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit have H := CBCa.Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))) &m | probability / pr / probability, 1 goal, goal 675 chars | accepted commit |  |
| T0.0-16 | +11:13 | [137.2 s](./views/Tree_0_0/thinking/turn_016.md) | 2.8 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit apply H | probability / pr / probability, 1 goal, goal 1503 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-17 | +15:28 | [252.3 s](./views/Tree_0_0/thinking/turn_017.md) | 2.7 s | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit have ->: Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBoun... | probability / pr / probability, 1 goal, goal 1503 chars | accepted commit |  |
| T0.0-18 | +15:37 | 6.4 s | 590 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit byequiv=> //=; sim | probability / pr / probability, 2 goals, goal 1267 chars | accepted commit |  |
| T0.0-19 | +15:46 | 8.4 s | 594 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit have ->: Pr[IND(PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(... | probability / pr / probability, 1 goal, goal 1508 chars | accepted commit |  |
| T0.0-20 | +15:52 | 5.5 s | 525 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit byequiv=> //=; sim | probability / pr / probability, 2 goals, goal 1184 chars | accepted commit |  |
| T0.0-21 | +16:22 | [29.4 s](./views/Tree_0_0/thinking/turn_021.md) | 581 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit have ->: Pr[IND(PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa... | probability / pr / probability, 1 goal, goal 1530 chars | accepted commit |  |
| T0.0-22 | +16:28 | 5.4 s | 556 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit byequiv=> //=; sim | probability / pr / probability, 2 goals, goal 1186 chars | accepted commit |  |
| T0.0-23 | +16:34 | 5.8 s | 167 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit apply H | probability / pr / probability, 1 goal, goal 1552 chars | accepted commit |  |
| T0.0-24 | +18:07 | [92.8 s](./views/Tree_0_0/thinking/turn_024.md) | 183 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit move=> O enc_ll; islossless | ambient / ambient_logic, 1 goal, goal 1131 chars | accepted commit |  |
| T0.0-25 | +18:30 | 22.8 s | 167 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit apply (A_distinguish_ll (<: RCPA_WUF_RCPA.RCPAa(MAC, A, RCPAa(RCPA_WU... | phoare / procedure_body / procedure_frontier, 2 goals, goal 1203 chars | accepted commit |  |
| T0.0-26 | +18:38 | 7.8 s | 153 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit islossless | phoare / procedure_body / procedure_frontier, 2 goals, goal 1186 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m) | probability / pr / probability, 1 goal, goal 569 chars | accepted commit |  |
| T0.1-2 | +00:15 | [12.5 s](./views/Tree_0_1/thinking/turn_002.md) | 528 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit have <-: Pr[CBCa.SKEa.RCPA.INDR_CPA(Random,QueryBounder(RCPAa(RCPA_WU... | probability / pr / probability, 1 goal, goal 689 chars | accepted commit |  |
| T0.1-3 | +00:26 | 10.7 s | 271 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit byequiv=> //=; proc; call (_: true) | probability / pr / probability, 2 goals, goal 416 chars | accepted commit |  |
| T0.1-4 | +02:42 | 135.7 s | 2.3 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | undo_last_step | pRHL / call_site / relational_program, 3 goals, goal 1265 chars | undo result |  |
| T0.1-5 | +02:52 | 7 s | 2 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit byequiv=> //=; proc; inline *; wp; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}) | probability / pr / probability, 2 goals, goal 404 chars | accepted commit |  |
| T0.1-6 | +03:24 | [30.8 s](./views/Tree_0_1/thinking/turn_006.md) | 181 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}) | equiv / prhl_module / relational_program, 3 goals, goal 829 chars | accepted commit |  |
| T0.1-7 | +03:42 | 17.8 s | 192 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}); auto | pRHL / call_site / relational_program, 4 goals, goal 1114 chars | accepted commit |  |
| T0.1-8 | +05:09 | [86.7 s](./views/Tree_0_1/thinking/turn_008.md) | 259 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit sp; if; first by smt() | pRHL / call_site / relational_program, 4 goals, goal 1940 chars | accepted commit |  |
| T0.1-9 | +05:20 | 10.8 s | 197 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit wp; call (_: ={glob RCPA_WUF_RCPA.RCPAa, glob OracleBounder}); auto | pRHL / call_site / relational_program, 5 goals, goal 1047 chars | accepted commit |  |
| T0.1-10 | +05:27 | [6.8 s](./views/Tree_0_1/thinking/turn_010.md) | 215 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit call Random_Ideal; auto | pRHL / call_site / relational_program, 5 goals, goal 772 chars | accepted commit |  |
| T0.1-11 | +05:39 | 11.8 s | 195 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit by sim | pRHL / verification_residue / relational_program, 4 goals, goal 779 chars | accepted commit |  |
| T0.1-12 | +05:53 | 13.8 s | 194 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit by inline *; auto | pRHL / verification_residue / relational_program, 3 goals, goal 625 chars | accepted commit |  |
| T0.1-13 | +06:03 | 9.4 s | 568 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit by auto | pRHL / verification_residue / relational_program, 2 goals, goal 907 chars | accepted commit |  |
| T0.1-14 | +06:15 | [11.3 s](./views/Tree_0_1/thinking/turn_014.md) | 2.7 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit apply (Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A))) &m) | probability / pr / probability, 1 goal, goal 675 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.1-15 | +07:41 | [83.4 s](./views/Tree_0_1/thinking/turn_015.md) | 617 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit have CC := Conclusion (<: RCPAa(RCPA_WUF_RCPA.RCPAa(MAC,A))) &m | probability / pr / probability, 1 goal, goal 675 chars | accepted commit |  |
| T0.1-16 | +12:07 | 265.4 s | 2.6 s | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit have eL: Pr[CBCa.SKEa.RCPA.INDR_CPA(IV_Wrap(CBC(PseudoRP)), QueryBoun... | probability / pr / probability, 1 goal, goal 1520 chars | accepted commit |  |

### Tree-0.1.r1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1.r1-1 | +14:11 | [think](./views/Tree_0_1_r1/thinking/turn_001.md) | 604 ms | [manager_bootstrap_0_1_r1.json](./views/_bootstrap/manager_bootstrap_0_1_r1.json) | commit byequiv=> //=; sim | probability / pr / probability, 2 goals, goal 1284 chars | accepted commit |  |
| T0.1.r1-2 | +15:29 | 77.4 s | 582 ms | [turn_001.json](./views/Tree_0_1_r1/turn_001.json) · [inline read](./views/Tree_0_1_r1/followups/turn_001.md) | commit rewrite eL | probability / pr / probability, 1 goal, goal 1839 chars | accepted commit |  |
| T0.1.r1-3 | +15:39 | 9.5 s | 520 ms | [turn_002.json](./views/Tree_0_1_r1/turn_002.json) · [inline read](./views/Tree_0_1_r1/followups/turn_002.md) | commit have ->: Pr[IND(PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main () @ &m... | probability / pr / probability, 1 goal, goal 1844 chars | accepted commit |  |
| T0.1.r1-4 | +15:47 | [7.4 s](./views/Tree_0_1_r1/thinking/turn_004.md) | 634 ms | [turn_003.json](./views/Tree_0_1_r1/turn_003.json) · [inline read](./views/Tree_0_1_r1/followups/turn_003.md) | commit have ->: Pr[IND(PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main () @ &... | probability / pr / probability, 1 goal, goal 1866 chars | accepted commit |  |
| T0.1.r1-5 | +15:55 | [7.8 s](./views/Tree_0_1_r1/thinking/turn_005.md) | 181 ms | [turn_004.json](./views/Tree_0_1_r1/turn_004.json) · [inline read](./views/Tree_0_1_r1/followups/turn_004.md) | commit apply CC | probability / pr / probability, 1 goal, goal 1888 chars | accepted commit |  |
| T0.1.r1-6 | +18:04 | [128.8 s](./views/Tree_0_1_r1/thinking/turn_006.md) | 199 ms | [turn_005.json](./views/Tree_0_1_r1/turn_005.json) · [inline read](./views/Tree_0_1_r1/followups/turn_005.md) | commit move=> O O_enc_ll; proc | ambient / ambient_logic, 1 goal, goal 1467 chars | accepted commit |  |
| T0.1.r1-7 | +18:13 | [8.8 s](./views/Tree_0_1_r1/thinking/turn_007.md) | 170 ms | [turn_006.json](./views/Tree_0_1_r1/turn_006.json) · [inline read](./views/Tree_0_1_r1/followups/turn_006.md) | commit call (A_distinguish_ll (<: RCPA_WUF_RCPA.RCPAa(MAC, A, RCPAa(RCPA_WUF... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1749 chars | accepted commit |  |
| T0.1.r1-8 | +18:25 | [11.8 s](./views/Tree_0_1_r1/thinking/turn_008.md) | 172 ms | [turn_007.json](./views/Tree_0_1_r1/turn_007.json) · [inline read](./views/Tree_0_1_r1/followups/turn_007.md) | commit by proc; inline *; wp; call O_enc_ll; auto | phoare / procedure_body / procedure_frontier, 2 goals, goal 1523 chars | accepted commit |  |
| T0.1.r1-9 | +18:34 | [8.8 s](./views/Tree_0_1_r1/thinking/turn_009.md) | 210 ms | [turn_008.json](./views/Tree_0_1_r1/turn_008.json) · [inline read](./views/Tree_0_1_r1/followups/turn_008.md) | commit by inline *; auto; smt(d_mK_uffu) | phoare / procedure_body / procedure_frontier, 1 goal, goal 1503 chars | accepted commit |  |
| T0.1.r1-10 | +18:39 | [4.8 s](./views/Tree_0_1_r1/thinking/turn_010.md) | 157 ms | [turn_009.json](./views/Tree_0_1_r1/turn_009.json) · [inline read](./views/Tree_0_1_r1/followups/turn_009.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1.r1-11 | +18:50 | 10 s |  | [turn_010.json](./views/Tree_0_1_r1/turn_010.json) · [inline read](./views/Tree_0_1_r1/followups/turn_010.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
