# Agent-View Timeline — `step2_1`

| field | value |
|---|---|
| commit | `95d4bbf9` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-08_1612_step2_1 |
| lemma | `step2_1` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 39 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 14 tactic(s) committed, not closed

```easycrypt
proof.
  have <- : Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res].
  byequiv => //; proc.
  call (_: StLSke.gs{1} = OpCCRO.OCC.gs{2} /\ ={Mem.k}).
  proc; inline *; wp; skip => />.
  move=> &2; rewrite /enc /get //=.
  by case: (p{2}).
  proc; inline *; wp; skip => />.
  move=> &2; case: (c{2}) => n a c0 t /=; rewrite /dec /get /=; smt().
  conseq (: _ ==> (glob A){1} = (glob A){2} /\ StLSke.gs{1} = OCC.gs{2} /\ Mem.k{1} = Mem.k{2}).
  smt().
  inline *; wp; rnd; sim.
  apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A A_ll &m).
  proc; sim.
  proc; auto.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  have hL : Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res].
  byequiv => //.
  proc.
  call (_: ={Mem.k} /\ OCC.gs{1} = StLSke.gs{2}).
  proc; inline *.
  wp; skip => />.
  move=> &2; rewrite /enc /get /=.
  smt().
  proc; inline *.
  wp; skip => />.
  move=> &2; rewrite /dec /get /=; smt().
  conseq (_ : _ ==> ={glob A} /\ Mem.k{1} = Mem.k{2} /\ OCC.gs{1} = StLSke.gs{2}).
  by move=> />.
  inline *; sim.
  rewrite hL.
  apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A _ &m).
  sim.
  proc; auto.
  apply A_ll.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_1612_step2_1

Run dir: `artifacts/eval_suite/medium4_l1_l4noprobe/l1_goal_projection/chacha_step2_1/r01/2026-06-08_1612_step2_1/iteration_1`

t=0: `2026-06-08T23:16:42.800000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:02 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.9 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit have <- : Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res] =... | probability / pr / probability, 1 goal, goal 409 chars | accepted commit |  |
| T0.0-2 | +00:17 | [12.7 s](./views/Tree_0_0/thinking/turn_002.md) | 326 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit byequiv => //; proc | probability / pr / probability, 2 goals, goal 270 chars | accepted commit |  |
| T0.0-3 | +00:26 | [8.8 s](./views/Tree_0_0/thinking/turn_003.md) | 228 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit call StLSke.gs | pRHL / call_site / relational_program, 2 goals, goal 534 chars | accepted commit |  |
| T0.0-4 | +00:46 | [19.8 s](./views/Tree_0_0/thinking/turn_004.md) | 197 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit proc; inline *; wp; skip => /> | equiv / prhl_module / relational_program, 4 goals, goal 362 chars | accepted commit |  |
| T0.0-5 | +01:02 | [15.7 s](./views/Tree_0_0/thinking/turn_005.md) | 264 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit move=> &2; rewrite /enc /get //= | ambient / ambient_logic, 4 goals, goal 657 chars | accepted commit |  |
| T0.0-6 | +01:11 | [8.8 s](./views/Tree_0_0/thinking/turn_006.md) | 198 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit by case: (p{2}) | ambient / ambient_logic, 4 goals, goal 1207 chars | accepted commit |  |
| T0.0-7 | +01:19 | [7.8 s](./views/Tree_0_0/thinking/turn_007.md) | 237 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit proc; inline *; wp; skip => /> | equiv / prhl_module / relational_program, 3 goals, goal 362 chars | accepted commit |  |
| T0.0-8 | +01:57 | [37.7 s](./views/Tree_0_0/thinking/turn_008.md) | 314 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit move=> &2; case: (c{2}) => n a c0 t /=; rewrite /dec /get /=; smt() | ambient / ambient_logic, 3 goals, goal 766 chars | accepted commit |  |
| T0.0-9 | +02:36 | [38.4 s](./views/Tree_0_0/thinking/turn_009.md) | 1.6 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit inline *; sim | pRHL / procedure_body / relational_program, 2 goals, goal 612 chars | rejected commit: [error] cannot infer the set of equalities |  |
| T0.0-10 | +03:10 | [32.7 s](./views/Tree_0_0/thinking/turn_010.md) | 271 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit conseq (: _ ==> (glob A){1} = (glob A){2} /\ StLSke.gs{1} = OCC.gs{2}... | pRHL / procedure_body / relational_program, 2 goals, goal 612 chars | accepted commit |  |
| T0.0-11 | +03:22 | [11.7 s](./views/Tree_0_0/thinking/turn_011.md) | 319 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit smt() | ambient / ambient_logic / relational_program, 3 goals, goal 571 chars | accepted commit |  |
| T0.0-12 | +03:39 | [16.3 s](./views/Tree_0_0/thinking/turn_012.md) | 675 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit inline *; wp; rnd; sim | pRHL / procedure_body / relational_program, 2 goals, goal 418 chars | accepted commit |  |
| T0.0-13 | +04:00 | [20.8 s](./views/Tree_0_0/thinking/turn_013.md) | 212 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A A_ll &m) | probability / pr / probability, 1 goal, goal 413 chars | accepted commit |  |
| T0.0-14 | +04:12 | [11.8 s](./views/Tree_0_0/thinking/turn_014.md) | 205 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit proc; sim | equiv / prhl_module / relational_program, 2 goals, goal 225 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit have hL : Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m... | probability / pr / probability, 1 goal, goal 409 chars | accepted commit |  |
| T0.1-2 | +00:05 | [2.8 s](./views/Tree_0_1/thinking/turn_002.md) | 211 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit byequiv=>// | probability / pr / probability, 2 goals, goal 270 chars | accepted commit |  |
| T0.1-3 | +00:09 | [3.7 s](./views/Tree_0_1/thinking/turn_003.md) | 315 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 444 chars | accepted commit |  |
| T0.1-4 | +00:20 | 11 s |  | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | unknown | pRHL / call_site / relational_program, 2 goals, goal 534 chars | repair / unhealthy |  |
| T0.1-5 | +00:25 | [4.8 s](./views/Tree_0_1/thinking/turn_005.md) | 204 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit call (_: ={Mem.k} /\ OCC.gs{1} = StLSke.gs{2}) | pRHL / call_site / relational_program, 2 goals, goal 534 chars | accepted commit |  |
| T0.1-6 | +00:37 | [11.7 s](./views/Tree_0_1/thinking/turn_006.md) | 282 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc; inline * | equiv / prhl_module / relational_program, 4 goals, goal 362 chars | accepted commit |  |
| T0.1-7 | +00:50 | [12.8 s](./views/Tree_0_1/thinking/turn_007.md) | 208 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit wp; skip => /> | pRHL / procedure_body / relational_program, 4 goals, goal 1601 chars | accepted commit |  |
| T0.1-8 | +01:04 | [13.8 s](./views/Tree_0_1/thinking/turn_008.md) | 234 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit move=> &2; rewrite /enc /get /= | ambient / ambient_logic, 4 goals, goal 663 chars | accepted commit |  |
| T0.1-9 | +01:24 | [19.6 s](./views/Tree_0_1/thinking/turn_009.md) | 1.4 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit by case: p{2} | ambient / ambient_logic, 4 goals, goal 1081 chars | rejected commit: [error] parse error |  |
| T0.1-10 | +01:31 | [5.8 s](./views/Tree_0_1/thinking/turn_010.md) | 238 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit smt() | ambient / ambient_logic, 4 goals, goal 1081 chars | accepted commit |  |
| T0.1-11 | +01:40 | [8.7 s](./views/Tree_0_1/thinking/turn_011.md) | 285 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit proc; inline * | equiv / prhl_module / relational_program, 3 goals, goal 362 chars | accepted commit |  |
| T0.1-12 | +01:47 | [6.8 s](./views/Tree_0_1/thinking/turn_012.md) | 197 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit wp; skip => /> | pRHL / procedure_body / relational_program, 3 goals, goal 2126 chars | accepted commit |  |
| T0.1-13 | +01:57 | [9.7 s](./views/Tree_0_1/thinking/turn_013.md) | 296 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit move=> &2; rewrite /dec /get /=; smt() | ambient / ambient_logic, 3 goals, goal 775 chars | accepted commit |  |
| T0.1-14 | +02:40 | [42.6 s](./views/Tree_0_1/thinking/turn_014.md) | 1.4 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit inline *; sim | pRHL / procedure_body / relational_program, 2 goals, goal 612 chars | rejected commit: [error] cannot infer the set of equalities |  |
| T0.1-15 | +02:56 | [14.6 s](./views/Tree_0_1/thinking/turn_015.md) | 355 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit conseq (_ : _ ==> ={glob A} /\ Mem.k{1} = Mem.k{2} /\ OCC.gs{1} = StL... | pRHL / procedure_body / relational_program, 2 goals, goal 612 chars | accepted commit |  |
| T0.1-16 | +03:04 | [7.7 s](./views/Tree_0_1/thinking/turn_016.md) | 290 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit by move=> /> | ambient / ambient_logic / relational_program, 3 goals, goal 571 chars | accepted commit |  |
| T0.1-17 | +03:10 | [5.3 s](./views/Tree_0_1/thinking/turn_017.md) | 693 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit inline *; sim | pRHL / procedure_body / relational_program, 2 goals, goal 418 chars | accepted commit |  |
| T0.1-18 | +03:16 | [5.4 s](./views/Tree_0_1/thinking/turn_018.md) | 640 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit rewrite hL | probability / pr / probability, 1 goal, goal 555 chars | accepted commit |  |
| T0.1-19 | +03:31 | [15.1 s](./views/Tree_0_1/thinking/turn_019.md) | 1.9 s | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit apply (CCA_UFCMA.CCA_CPA_UFCMA St A &m) | probability / pr / probability, 1 goal, goal 546 chars | rejected commit: [error] expecting a `proof-term', not a `formula' |  |
| T0.1-20 | +03:49 | [15.7 s](./views/Tree_0_1/thinking/turn_020.md) | 273 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A _ &m) | probability / pr / probability, 1 goal, goal 546 chars | accepted commit |  |
| T0.1-21 | +04:03 | [13.8 s](./views/Tree_0_1/thinking/turn_021.md) | 249 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit sim | equiv / prhl_module / relational_program, 3 goals, goal 358 chars | accepted commit |  |
| T0.1-22 | +04:10 | [6.7 s](./views/Tree_0_1/thinking/turn_022.md) | 268 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit proc; auto | hoare / procedure_body / procedure_frontier, 2 goals, goal 315 chars | accepted commit |  |
| T0.1-23 | +04:14 | [3.8 s](./views/Tree_0_1/thinking/turn_023.md) | 188 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | commit apply A_ll | ambient / ambient_logic, 1 goal, goal 357 chars | accepted commit |  |
| T0.1-24 | +04:17 | [2.8 s](./views/Tree_0_1/thinking/turn_024.md) | 202 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-25 | +04:31 | 14 s |  | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
