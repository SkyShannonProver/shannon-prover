# Agent-View Timeline — `step2_1`

| field | value |
|---|---|
| commit | `95d4bbf9` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-08_1656_step2_1 |
| lemma | `step2_1` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 43 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  have ->: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res].
  byequiv (_: ={glob A} ==> ={res}) => //.
  proc.
  call (_: ={Mem.k} /\ OpCCRO.OCC.gs{1} = StLSke.gs{2}).
  proc; inline *; auto.
  move=> &1 &2 [-> [-> ->]]; rewrite /enc /get /=.
  smt().
  proc; inline *; auto.
  move=> &1 &2 [-> [-> ->]]; rewrite /dec /get /=; smt().
  inline *; auto.
  conseq (_: _ ==> ={glob A} /\ RO.m{1} = RO.m{2}); first by smt().
  sim.
  apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A _ &m).
  proc; sim.
  proc; auto.
  apply A_ll.
  qed.
```

### `Tree_0_1` — incomplete — 12 tactic(s) committed, not closed

```easycrypt
proof.
  have ->: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res].
  byequiv (_: ={glob A} ==> ={res}) => //.
  proc.
  call (_: ={glob Mem} /\ OpCCRO.OCC.gs{1} = StLSke.gs{2}).
  proc.
  inline *; wp; skip => />.
  move=> &2.
  rewrite /enc /=.
  rewrite /get; case: (p{2}) => n a p1 /=.
  done.
  proc; inline *; wp; skip => />.
  by move=> &2; rewrite /dec /get; case: (c{2}) => n a c0 t /=; smt().
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_1656_step2_1

Run dir: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1`

t=0: `2026-06-08T23:56:49.753000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 247 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect lemma_index | probability / pr / probability, 1 goal, goal 409 chars | read-only inspect |  |
| T0.0-2 | +01:11 | [71.2 s](./views/Tree_0_0/thinking/turn_002.md) | 2.8 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 409 chars | read-only inspect |  |
| T0.0-3 | +01:20 | [5.7 s](./views/Tree_0_0/thinking/turn_003.md) | 1.3 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | lookup CCA_UFCMA.CCA_CPA_UFCMA | probability / pr / probability, 1 goal, goal 409 chars | lookup result |  |
| T0.0-4 | +03:20 | [118.3 s](./views/Tree_0_0/thinking/turn_004.md) | 713 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit have ->: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m :... | probability / pr / probability, 1 goal, goal 409 chars | accepted commit |  |
| T0.0-5 | +03:40 | [19.8 s](./views/Tree_0_0/thinking/turn_005.md) | 206 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit byequiv (_: ={glob A} ==> ={res}) => // | probability / pr / probability, 2 goals, goal 270 chars | accepted commit |  |
| T0.0-6 | +03:49 | [8.7 s](./views/Tree_0_0/thinking/turn_006.md) | 296 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 415 chars | accepted commit |  |
| T0.0-7 | +03:54 | [4.7 s](./views/Tree_0_0/thinking/turn_007.md) | 1.3 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 2 goals, goal 505 chars | read-only inspect |  |
| T0.0-8 | +04:11 | [15.9 s](./views/Tree_0_0/thinking/turn_008.md) | 101 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | inspect call_subgoals | pRHL / call_site / failure_diagnostic, 2 goals, goal 505 chars | read-only inspect |  |
| T0.0-9 | +04:16 | [4.8 s](./views/Tree_0_0/thinking/turn_009.md) | 195 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit call (_: ={Mem.k} /\ OpCCRO.OCC.gs{1} = StLSke.gs{2}) | pRHL / call_site / failure_diagnostic, 2 goals, goal 505 chars | accepted commit |  |
| T0.0-10 | +04:45 | [28.7 s](./views/Tree_0_0/thinking/turn_010.md) | 268 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit proc; inline *; auto | equiv / prhl_module / relational_program, 4 goals, goal 362 chars | accepted commit |  |
| T0.0-11 | +05:17 | [31.7 s](./views/Tree_0_0/thinking/turn_011.md) | 328 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit move=> &1 &2 [-> [-> ->]]; rewrite /enc /get /= | ambient / ambient_logic / relational_program, 4 goals, goal 668 chars | accepted commit |  |
| T0.0-12 | +05:37 | [19.7 s](./views/Tree_0_0/thinking/turn_012.md) | 275 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit smt() | ambient / ambient_logic, 4 goals, goal 1261 chars | accepted commit |  |
| T0.0-13 | +05:51 | [13.7 s](./views/Tree_0_0/thinking/turn_013.md) | 290 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit proc; inline *; auto | equiv / prhl_module / relational_program, 3 goals, goal 362 chars | accepted commit |  |
| T0.0-14 | +06:05 | [13.6 s](./views/Tree_0_0/thinking/turn_014.md) | 394 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit move=> &1 &2 [-> [-> ->]]; rewrite /dec /get /=; smt() | ambient / ambient_logic / relational_program, 3 goals, goal 851 chars | accepted commit |  |
| T0.0-15 | +06:32 | [26.7 s](./views/Tree_0_0/thinking/turn_015.md) | 349 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit inline *; auto | pRHL / procedure_body / relational_program, 2 goals, goal 583 chars | accepted commit |  |
| T0.0-16 | +06:42 | [9.5 s](./views/Tree_0_0/thinking/turn_016.md) | 1.5 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit sim | pRHL / verification_residue / relational_program, 2 goals, goal 1305 chars | rejected commit: [error] cannot infer the set of equalities |  |
| T0.0-17 | +07:09 | 26 s |  | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | unknown | pRHL / verification_residue / relational_program, 2 goals, goal 1305 chars | repair / unhealthy |  |
| T0.0-18 | +07:13 | 4 s |  | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | unknown | pRHL / verification_residue / relational_program, 2 goals, goal 1305 chars | repair / unhealthy |  |
| T0.0-19 | +07:18 | 4.7 s | 312 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit conseq (_: _ ==> ={glob A} /\ RO.m{1} = RO.m{2}); first by smt() | pRHL / verification_residue / relational_program, 2 goals, goal 1305 chars | accepted commit |  |
| T0.0-20 | +07:24 | [5.3 s](./views/Tree_0_0/thinking/turn_020.md) | 655 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit sim | pRHL / verification_residue / relational_program, 2 goals, goal 1021 chars | accepted commit |  |
| T0.0-21 | +07:54 | [29.8 s](./views/Tree_0_0/thinking/turn_021.md) | 237 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A _ &m) | probability / pr / probability, 1 goal, goal 413 chars | accepted commit |  |
| T0.0-22 | +08:02 | [7.8 s](./views/Tree_0_0/thinking/turn_022.md) | 199 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit proc; sim | equiv / prhl_module / relational_program, 3 goals, goal 225 chars | accepted commit |  |
| T0.0-23 | +08:08 | [5.8 s](./views/Tree_0_0/thinking/turn_023.md) | 227 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit proc; auto | hoare / procedure_body / procedure_frontier, 2 goals, goal 182 chars | accepted commit |  |
| T0.0-24 | +08:12 | [3.8 s](./views/Tree_0_0/thinking/turn_024.md) | 206 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit apply A_ll | ambient / ambient_logic, 1 goal, goal 224 chars | accepted commit |  |
| T0.0-25 | +08:15 | [2.8 s](./views/Tree_0_0/thinking/turn_025.md) | 203 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:07 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.9 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 409 chars | read-only inspect |  |
| T0.1-2 | +00:14 | [3.7 s](./views/Tree_0_1/thinking/turn_002.md) | 270 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | inspect lemma_index | probability / pr / probability, 1 goal, goal 409 chars | read-only inspect |  |
| T0.1-3 | +01:19 | [64.6 s](./views/Tree_0_1/thinking/turn_003.md) | 1.4 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | lookup CCA_UFCMA.CCA_CPA_UFCMA | probability / pr / probability, 1 goal, goal 409 chars | lookup result |  |
| T0.1-4 | +03:51 | [150.3 s](./views/Tree_0_1/thinking/turn_004.md) | 655 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit have ->: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m :... | probability / pr / probability, 1 goal, goal 409 chars | accepted commit |  |
| T0.1-5 | +04:00 | [8.8 s](./views/Tree_0_1/thinking/turn_005.md) | 218 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit byequiv (_: ={glob A} ==> ={res}) => // | probability / pr / probability, 2 goals, goal 270 chars | accepted commit |  |
| T0.1-6 | +04:05 | [4.7 s](./views/Tree_0_1/thinking/turn_006.md) | 286 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 415 chars | accepted commit |  |
| T0.1-7 | +04:14 | [8.8 s](./views/Tree_0_1/thinking/turn_007.md) | 1.2 s | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 2 goals, goal 505 chars | read-only inspect |  |
| T0.1-8 | +04:22 | [6.9 s](./views/Tree_0_1/thinking/turn_008.md) | 94 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | inspect call_subgoals | pRHL / call_site / failure_diagnostic, 2 goals, goal 505 chars | read-only inspect |  |
| T0.1-9 | +04:29 | [6.8 s](./views/Tree_0_1/thinking/turn_009.md) | 206 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit call (_: ={glob Mem} /\ OpCCRO.OCC.gs{1} = StLSke.gs{2}) | pRHL / call_site / failure_diagnostic, 2 goals, goal 505 chars | accepted commit |  |
| T0.1-10 | +05:18 | [48.7 s](./views/Tree_0_1/thinking/turn_010.md) | 271 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit proc | equiv / prhl_module / relational_program, 4 goals, goal 474 chars | accepted commit |  |
| T0.1-11 | +05:24 | [5.8 s](./views/Tree_0_1/thinking/turn_011.md) | 203 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit inline *; wp; skip => /> | pRHL / call_site / relational_program, 4 goals, goal 564 chars | accepted commit |  |
| T0.1-12 | +05:45 | [20.4 s](./views/Tree_0_1/thinking/turn_012.md) | 1.6 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit by move=> &2; rewrite /enc /get /= | ambient / ambient_logic, 4 goals, goal 663 chars | rejected commit: [by]: cannot close goals |  |
| T0.1-13 | +06:09 | [22.8 s](./views/Tree_0_1/thinking/turn_013.md) | 249 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit move=> &2 | ambient / ambient_logic, 4 goals, goal 663 chars | accepted commit |  |
| T0.1-14 | +06:17 | [7.8 s](./views/Tree_0_1/thinking/turn_014.md) | 210 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit rewrite /enc /= | ambient / ambient_logic, 4 goals, goal 677 chars | accepted commit |  |
| T0.1-15 | +06:57 | [39.8 s](./views/Tree_0_1/thinking/turn_015.md) | 210 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit rewrite /get; case: (p{2}) => n a p1 /= | ambient / ambient_logic, 4 goals, goal 876 chars | accepted commit |  |
| T0.1-16 | +07:00 | [2.8 s](./views/Tree_0_1/thinking/turn_016.md) | 211 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit done | ambient / ambient_logic, 4 goals, goal 239 chars | accepted commit |  |
| T0.1-17 | +07:12 | [11.8 s](./views/Tree_0_1/thinking/turn_017.md) | 207 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit proc; inline *; wp; skip => /> | equiv / prhl_module / relational_program, 3 goals, goal 474 chars | accepted commit |  |
| T0.1-18 | +07:36 | [23.6 s](./views/Tree_0_1/thinking/turn_018.md) | 414 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit by move=> &2; rewrite /dec /get; case: (c{2}) => n a c0 t /=; smt() | ambient / ambient_logic, 3 goals, goal 775 chars | accepted commit |  |
