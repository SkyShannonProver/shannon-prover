# Agent-View Timeline — `step1`

| field | value |
|---|---|
| commit | `0958fbb` **(dirty/uncommitted)** |
| branch | `eval-suite-48` |
| run time | 2026-06-03_1548_step1 |
| lemma | `step1` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 105 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  congr.
  have -> : Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(OpCCinit.OChaChaPoly(I_stateless))).main() @ &m : res] by byequiv=>//; proc; inline *; sim.
  rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
  byequiv => //.
  proc.
  inline{2} D(A, IndBlock).guess.
  seq 1 2 : (={glob A} /\ Mem.k{1} = IndBlock.k{2}).
  inline *; auto.
  wp; call (_: Mem.k{1} = IndBlock.k{2}).
  proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc. wp. call poly_mac1. call chacha_enc1. auto.
  proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq 1 1 : (t'{1} = t'{2} /\ t{1} = t{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ c0{1} = c{2} /\ result{1} = result{2} /\ k{1} = IndBlock.k{2} /\ Mem.k{1} = IndBlock.k{2}).
  call poly_mac1. auto. if => //. wp. call chacha_enc1. auto. auto.
  auto.
  congr.
  have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = Pr[MainD(G2, RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have -> : Pr[MainD(G2, RO).distinguish() @ &m : res] = Pr[MainD(G2, FinRO).distinguish() @ &m : res] by apply (FiniteRO.pr_RO_FinRO_D _ G2 &m tt (fun (b:bool) => b)); move=> ?; exact dblock_ll.
  rewrite -(OpCCRO.pr_CCP_OCCP IFinRO G1 &m).
  byequiv => //.
  proc.
  inline{2} G2(FinRO).distinguish.
  seq 1 3 : (={glob A} /\ OpCCRO.OCC.gs{1} = RO.m{2}).
  inline{1} RealOrcls(GenChaChaPoly(OCC(IFinRO))).init GenChaChaPoly(OCC(IFinRO)).init GenChaChaPoly(OCC(IFinRO)).kg IFinRO.init. inline{2} D(A, G2(FinRO).CCRO).O.init. seq 1 1 : (={glob A, RO.m}). sim. wp. rnd{1}. auto.
  wp; call (_: OpCCRO.OCC.gs{1} = RO.m{2}).
  proc. inline{1} GenChaChaPoly(OpCCRO.OCC(IFinRO)).enc. wp. call poly_mac2. call chacha_enc2. auto.
  proc. inline{1} GenChaChaPoly(OpCCRO.OCC(IFinRO)).dec. sp. seq 1 1 : (t'{1} = t'{2} /\ t{1} = t{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ c0{1} = c{2} /\ result{1} = result{2} /\ OpCCRO.OCC.gs{1} = RO.m{2}).
  call poly_mac2. auto. if => //. wp. call chacha_enc2. auto. auto.
  auto.
  qed.
```

### `Tree_0_1` — incomplete — 12 tactic(s) committed, not closed

```easycrypt
proof.
  have ->: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = Pr[Indist.Distinguish(D(A), IndBlock).game() @ &m : res].
  have ->: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(OpCCinit.OChaChaPoly(I_stateless))).main() @ &m : res].
  byequiv => //.
  proc; sim.
  inline *; auto.
  rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
  byequiv => //.
  proc.
  inline{2} D(A, IndBlock).guess.
  wp.
  call (_: Mem.k{1} = IndBlock.k{2}).
  proc; inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc; wp; call poly_mac1; call chacha_enc1; auto.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-03_1548_step1

Run dir: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1`

t=0: `2026-06-03T22:49:06.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe congr | probability / pr / probability, 1 goal, goal 357 chars | accepted probe |  |
| T0.0-2 | +00:32 | [29.4 s](./views/Tree_0_0/thinking/turn_002.md) | 643 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit congr | probability / pr / probability, 1 goal, goal 357 chars | accepted commit |  |
| T0.0-3 | +00:43 | [10.5 s](./views/Tree_0_0/thinking/turn_003.md) | 1.5 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | inspect pr_bridge_routes | probability / pr / probability, 2 goals, goal 261 chars | read-only inspect |  |
| T0.0-4 | +00:56 | [11.4 s](./views/Tree_0_0/thinking/turn_004.md) | 632 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit have -> : Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = Pr[CCA_game(A, RealOrcls... | probability / pr / probability, 2 goals, goal 261 chars | accepted commit |  |
| T0.0-5 | +01:08 | [11.6 s](./views/Tree_0_0/thinking/turn_005.md) | 1.4 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | inspect pr_bridge_routes | probability / pr / probability, 2 goals, goal 287 chars | read-only inspect |  |
| T0.0-6 | +01:49 | [39.4 s](./views/Tree_0_0/thinking/turn_006.md) | 647 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe byequiv=>// | probability / pr / probability, 2 goals, goal 287 chars | accepted probe |  |
| T0.0-7 | +02:07 | [16.8 s](./views/Tree_0_0/thinking/turn_007.md) | 194 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit byequiv=>// | probability / pr / probability, 2 goals, goal 287 chars | accepted commit |  |
| T0.0-8 | +02:48 | [41 s](./views/Tree_0_0/thinking/turn_008.md) |  | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | inspect call_site_options | equiv / prhl_module / relational_program, 2 goals, goal 342 chars | read-only inspect |  |
| T0.0-9 | +03:16 | [27.8 s](./views/Tree_0_0/thinking/turn_009.md) | 1.2 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | probe proc | equiv / prhl_module / relational_program, 2 goals, goal 342 chars | accepted probe |  |
| T0.0-10 | +07:48 | [271 s](./views/Tree_0_0/thinking/turn_010.md) | 1 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | lookup pr_CCP_OCCP | equiv / prhl_module / relational_program, 2 goals, goal 342 chars | lookup result |  |
| T0.0-11 | +08:31 | 42.5 s | 1.5 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | undo_last_step | equiv / prhl_module / relational_program, 2 goals, goal 342 chars | undo result |  |
| T0.0-12 | +09:01 | [28.3 s](./views/Tree_0_0/thinking/turn_012.md) | 2.7 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | probe rewrite -(pr_CCP_OCCP I_stateless G1 &m) | probability / pr / probability, 2 goals, goal 274 chars | rejected probe: invalid argument (incompatible module type): |  |
| T0.0-13 | +09:23 | [19.6 s](./views/Tree_0_0/thinking/turn_013.md) | 368 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | inspect diagnose | probability / pr / probability, 2 goals, goal 274 chars | read-only inspect |  |
| T0.0-14 | +09:57 | [33.4 s](./views/Tree_0_0/thinking/turn_014.md) | 648 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | probe rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m) | probability / pr / probability, 2 goals, goal 274 chars | accepted probe |  |
| T0.0-15 | +10:09 | [11.4 s](./views/Tree_0_0/thinking/turn_015.md) | 601 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m) | probability / pr / probability, 2 goals, goal 274 chars | accepted commit |  |
| T0.0-16 | +10:19 | [8.8 s](./views/Tree_0_0/thinking/turn_016.md) | 194 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit byequiv=>// | probability / pr / probability, 2 goals, goal 271 chars | accepted commit |  |
| T0.0-17 | +11:04 | [44.7 s](./views/Tree_0_0/thinking/turn_017.md) | 268 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 459 chars | accepted commit |  |
| T0.0-18 | +11:40 | [35.8 s](./views/Tree_0_0/thinking/turn_018.md) | 1.2 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | probe inline{2} D(A, IndBlock).guess | pRHL / call_site / relational_program, 2 goals, goal 900 chars | accepted probe |  |
| T0.0-19 | +12:04 | [23.7 s](./views/Tree_0_0/thinking/turn_019.md) | 1.3 s | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit inline{2} D(A, IndBlock).guess | pRHL / call_site / relational_program, 2 goals, goal 900 chars | accepted commit |  |
| T0.0-20 | +12:11 | [4.9 s](./views/Tree_0_0/thinking/turn_020.md) | 118 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | inspect call_invariant_skeleton | pRHL / call_site / seq_cut, 2 goals, goal 1110 chars | read-only inspect |  |
| T0.0-21 | +12:49 | [38 s](./views/Tree_0_0/thinking/turn_021.md) | 1 s | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | inspect goal_info | pRHL / call_site / failure_diagnostic, 2 goals, goal 1110 chars | read-only inspect |  |
| T0.0-22 | +13:49 | [59 s](./views/Tree_0_0/thinking/turn_022.md) | 1 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | lookup RealOrcls | pRHL / call_site / failure_diagnostic, 2 goals, goal 1110 chars | lookup result |  |
| T0.0-23 | +14:47 | [56.8 s](./views/Tree_0_0/thinking/turn_023.md) | 190 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | probe seq 1 2 : (={glob A} /\ Mem.k{1} = IndBlock.k{2}) | pRHL / call_site / failure_diagnostic, 2 goals, goal 1110 chars | accepted probe |  |
| T0.0-24 | +14:50 | [2.7 s](./views/Tree_0_0/thinking/turn_024.md) | 270 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit seq 1 2 : (={glob A} /\ Mem.k{1} = IndBlock.k{2}) | pRHL / call_site / failure_diagnostic, 2 goals, goal 1110 chars | accepted commit |  |
| T0.0-25 | +15:11 | [20.8 s](./views/Tree_0_0/thinking/turn_025.md) | 1.2 s | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | probe inline *; auto | pRHL / procedure_body / relational_program, 3 goals, goal 606 chars | accepted probe |  |
| T0.0-26 | +15:22 | [10.7 s](./views/Tree_0_0/thinking/turn_026.md) | 1.3 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit inline *; auto | pRHL / procedure_body / relational_program, 3 goals, goal 606 chars | accepted commit |  |
| T0.0-27 | +15:38 | [13.8 s](./views/Tree_0_0/thinking/turn_027.md) | 219 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | probe wp; call (_: Mem.k{1} = IndBlock.k{2}) | pRHL / call_site / seq_cut, 2 goals, goal 777 chars | accepted probe |  |
| T0.0-28 | +15:56 | [17.8 s](./views/Tree_0_0/thinking/turn_028.md) | 198 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit wp; call (_: Mem.k{1} = IndBlock.k{2}) | pRHL / call_site / seq_cut, 2 goals, goal 777 chars | accepted commit |  |
| T0.0-29 | +16:27 | [30.8 s](./views/Tree_0_0/thinking/turn_029.md) | 1.2 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | probe proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc. wp. cal... | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted probe |  |
| T0.0-30 | +17:14 | [45.8 s](./views/Tree_0_0/thinking/turn_030.md) | 242 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc. wp. cal... | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted commit |  |
| T0.0-31 | +18:52 | [97.7 s](./views/Tree_0_0/thinking/turn_031.md) | 1.3 s | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | probe proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | accepted probe |  |
| T0.0-32 | +20:11 | [77.7 s](./views/Tree_0_0/thinking/turn_032.md) | 255 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | probe proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq... | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-33 | +20:29 | [17.7 s](./views/Tree_0_0/thinking/turn_033.md) | 270 ms | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | commit proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq... | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | accepted commit |  |
| T0.0-34 | +20:44 | [14.8 s](./views/Tree_0_0/thinking/turn_034.md) | 1.2 s | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | probe call poly_mac1. auto | pRHL / call_site / relational_program, 4 goals, goal 1279 chars | accepted probe |  |
| T0.0-35 | +21:11 | [25.7 s](./views/Tree_0_0/thinking/turn_035.md) | 253 ms | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | probe call poly_mac1. auto. if => //. wp. call chacha_enc1. auto. auto | pRHL / call_site / relational_program, 4 goals, goal 1279 chars | accepted probe |  |
| T0.0-36 | +21:28 | [16.7 s](./views/Tree_0_0/thinking/turn_036.md) | 292 ms | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit call poly_mac1. auto. if => //. wp. call chacha_enc1. auto. auto | pRHL / call_site / relational_program, 4 goals, goal 1279 chars | accepted commit |  |
| T0.0-37 | +21:42 | [13.8 s](./views/Tree_0_0/thinking/turn_037.md) | 1.2 s | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | probe auto | pRHL / procedure_body / seq_cut, 2 goals, goal 486 chars | accepted probe |  |
| T0.0-38 | +21:49 | [5.7 s](./views/Tree_0_0/thinking/turn_038.md) | 254 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit auto | pRHL / procedure_body / seq_cut, 2 goals, goal 486 chars | accepted commit |  |
| T0.0-39 | +22:18 | [29.7 s](./views/Tree_0_0/thinking/turn_039.md) | 1.3 s | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | probe congr | probability / pr / probability, 1 goal, goal 256 chars | accepted probe |  |
| T0.0-40 | +22:51 | [31.4 s](./views/Tree_0_0/thinking/turn_040.md) | 622 ms | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit congr | probability / pr / probability, 1 goal, goal 256 chars | accepted commit |  |
| T0.0-41 | +22:58 | [6.5 s](./views/Tree_0_0/thinking/turn_041.md) | 1.5 s | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 252 chars | read-only inspect |  |
| T0.0-42 | +23:08 | [8.4 s](./views/Tree_0_0/thinking/turn_042.md) | 647 ms | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = Pr[MainD(G2, RO).distinguis... | probability / pr / probability, 1 goal, goal 252 chars | accepted commit |  |
| T0.0-43 | +23:16 | [6.8 s](./views/Tree_0_0/thinking/turn_043.md) | 1.2 s | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | lookup pr_RO_FinRO_D | probability / pr / probability, 1 goal, goal 241 chars | lookup result |  |
| T0.0-44 | +23:44 | [27.5 s](./views/Tree_0_0/thinking/turn_044.md) | 1.5 s | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 241 chars | read-only inspect |  |
| T0.0-45 | +24:29 | [43.3 s](./views/Tree_0_0/thinking/turn_045.md) | 683 ms | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | probe have -> : Pr[MainD(G2, RO).distinguish() @ &m : res] = Pr[MainD(G2, FinRO).distinguish() @ &m... | probability / pr / probability, 1 goal, goal 241 chars | accepted probe |  |
| T0.0-46 | +24:58 | [28.3 s](./views/Tree_0_0/thinking/turn_046.md) | 670 ms | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | commit have -> : Pr[MainD(G2, RO).distinguish() @ &m : res] = Pr[MainD(G2, FinRO).distinguish() @ &m... | probability / pr / probability, 1 goal, goal 241 chars | accepted commit |  |
| T0.0-47 | +25:09 | [10.3 s](./views/Tree_0_0/thinking/turn_047.md) | 1.7 s | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | probe rewrite -(OpCCRO.pr_CCP_OCCP IFinRO G1 &m) | probability / pr / probability, 1 goal, goal 244 chars | accepted probe |  |
| T0.0-48 | +25:16 | [5.4 s](./views/Tree_0_0/thinking/turn_048.md) | 590 ms | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | commit rewrite -(OpCCRO.pr_CCP_OCCP IFinRO G1 &m) | probability / pr / probability, 1 goal, goal 244 chars | accepted commit |  |
| T0.0-49 | +25:25 | [7.8 s](./views/Tree_0_0/thinking/turn_049.md) | 200 ms | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 231 chars | accepted commit |  |
| T0.0-50 | +25:32 | [6.8 s](./views/Tree_0_0/thinking/turn_050.md) | 1.2 s | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | probe proc | equiv / prhl_module / relational_program, 1 goal, goal 288 chars | accepted probe |  |
| T0.0-51 | +25:57 | [24.7 s](./views/Tree_0_0/thinking/turn_051.md) | 303 ms | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 288 chars | accepted commit |  |
| T0.0-52 | +26:06 | [7.7 s](./views/Tree_0_0/thinking/turn_052.md) | 1.3 s | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | probe inline{2} G2(FinRO).distinguish | pRHL / call_site / relational_program, 1 goal, goal 676 chars | accepted probe |  |
| T0.0-53 | +27:20 | [73.7 s](./views/Tree_0_0/thinking/turn_053.md) | 1.3 s | [turn_052.json](./views/Tree_0_0/turn_052.json) · [inline read](./views/Tree_0_0/followups/turn_052.md) | commit inline{2} G2(FinRO).distinguish | pRHL / call_site / relational_program, 1 goal, goal 676 chars | accepted commit |  |
| T0.0-54 | +31:50 | [267.9 s](./views/Tree_0_0/thinking/turn_054.md) | 1.1 s | [turn_053.json](./views/Tree_0_0/turn_053.json) · [inline read](./views/Tree_0_0/followups/turn_053.md) | lookup FinRO | pRHL / call_site / seq_cut, 1 goal, goal 986 chars | lookup result |  |
| T0.0-55 | +32:07 | [16.7 s](./views/Tree_0_0/thinking/turn_055.md) | 315 ms | [turn_054.json](./views/Tree_0_0/turn_054.json) · [inline read](./views/Tree_0_0/followups/turn_054.md) | commit seq 1 3 : (={glob A} /\ OpCCRO.OCC.gs{1} = RO.m{2}) | pRHL / call_site / seq_cut, 1 goal, goal 986 chars | accepted commit |  |
| T0.0-56 | +32:52 | [44.7 s](./views/Tree_0_0/thinking/turn_056.md) | 1.3 s | [turn_055.json](./views/Tree_0_0/turn_055.json) · [inline read](./views/Tree_0_0/followups/turn_055.md) | probe inline{1} RealOrcls(GenChaChaPoly(OCC(IFinRO))).init GenChaChaPoly(OC... | pRHL / procedure_body / relational_program, 2 goals, goal 569 chars | accepted probe |  |
| T0.0-57 | +34:06 | [71.8 s](./views/Tree_0_0/thinking/turn_057.md) | 232 ms | [turn_056.json](./views/Tree_0_0/turn_056.json) · [inline read](./views/Tree_0_0/followups/turn_056.md) | probe inline{1} RealOrcls(GenChaChaPoly(OCC(IFinRO))).init GenChaChaPoly(OC... | pRHL / procedure_body / relational_program, 2 goals, goal 569 chars | accepted probe |  |
| T0.0-58 | +34:19 | [13.6 s](./views/Tree_0_0/thinking/turn_058.md) | 1.4 s | [turn_057.json](./views/Tree_0_0/turn_057.json) · [inline read](./views/Tree_0_0/followups/turn_057.md) | commit inline{1} RealOrcls(GenChaChaPoly(OCC(IFinRO))).init GenChaChaPoly(OC... | pRHL / procedure_body / seq_cut, 2 goals, goal 569 chars | accepted commit |  |
| T0.0-59 | +34:34 | [12.8 s](./views/Tree_0_0/thinking/turn_059.md) | 212 ms | [turn_058.json](./views/Tree_0_0/turn_058.json) · [inline read](./views/Tree_0_0/followups/turn_058.md) | commit wp; call (_: OpCCRO.OCC.gs{1} = RO.m{2}) | pRHL / call_site / seq_cut, 1 goal, goal 698 chars | accepted commit |  |
| T0.0-60 | +34:46 | [11.7 s](./views/Tree_0_0/thinking/turn_060.md) | 1.3 s | [turn_059.json](./views/Tree_0_0/turn_059.json) · [inline read](./views/Tree_0_0/followups/turn_059.md) | probe proc. inline{1} GenChaChaPoly(OpCCRO.OCC(IFinRO)).enc. wp. call poly_... | equiv / prhl_module / relational_program, 3 goals, goal 314 chars | accepted probe |  |
| T0.0-61 | +35:21 | [33.8 s](./views/Tree_0_0/thinking/turn_061.md) | 209 ms | [turn_060.json](./views/Tree_0_0/turn_060.json) · [inline read](./views/Tree_0_0/followups/turn_060.md) | commit proc. inline{1} GenChaChaPoly(OpCCRO.OCC(IFinRO)).enc. wp. call poly_... | equiv / prhl_module / relational_program, 3 goals, goal 314 chars | accepted commit |  |
| T0.0-62 | +35:40 | [18.7 s](./views/Tree_0_0/thinking/turn_062.md) | 1.3 s | [turn_061.json](./views/Tree_0_0/turn_061.json) · [inline read](./views/Tree_0_0/followups/turn_061.md) | probe proc. inline{1} GenChaChaPoly(OpCCRO.OCC(IFinRO)).dec. sp. seq 1 1 :... | equiv / prhl_module / relational_program, 2 goals, goal 314 chars | accepted probe |  |
| T0.0-63 | +35:48 | [7.7 s](./views/Tree_0_0/thinking/turn_063.md) | 314 ms | [turn_062.json](./views/Tree_0_0/turn_062.json) · [inline read](./views/Tree_0_0/followups/turn_062.md) | commit proc. inline{1} GenChaChaPoly(OpCCRO.OCC(IFinRO)).dec. sp. seq 1 1 :... | equiv / prhl_module / seq_cut, 2 goals, goal 314 chars | accepted commit |  |
| T0.0-64 | +36:02 | [12.7 s](./views/Tree_0_0/thinking/turn_064.md) | 1.3 s | [turn_063.json](./views/Tree_0_0/turn_063.json) · [inline read](./views/Tree_0_0/followups/turn_063.md) | probe call poly_mac2. auto. if => //. wp. call chacha_enc2. auto. auto | pRHL / call_site / relational_program, 3 goals, goal 1238 chars | accepted probe |  |
| T0.0-65 | +36:19 | [16.7 s](./views/Tree_0_0/thinking/turn_065.md) | 325 ms | [turn_064.json](./views/Tree_0_0/turn_064.json) · [inline read](./views/Tree_0_0/followups/turn_064.md) | commit call poly_mac2. auto. if => //. wp. call chacha_enc2. auto. auto | pRHL / call_site / relational_program, 3 goals, goal 1238 chars | accepted commit |  |
| T0.0-66 | +36:24 | [3.8 s](./views/Tree_0_0/thinking/turn_066.md) | 229 ms | [turn_065.json](./views/Tree_0_0/turn_065.json) · [inline read](./views/Tree_0_0/followups/turn_065.md) | commit auto | pRHL / procedure_body / seq_cut, 1 goal, goal 465 chars | accepted commit |  |
| T0.0-67 | +36:38 | [13.8 s](./views/Tree_0_0/thinking/turn_067.md) | 224 ms | [turn_066.json](./views/Tree_0_0/turn_066.json) · [inline read](./views/Tree_0_0/followups/turn_066.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-68 | +36:47 | [8.9 s](./views/Tree_0_0/thinking/turn_068.md) | 110 ms | [turn_067.json](./views/Tree_0_0/turn_067.json) · [inline read](./views/Tree_0_0/followups/turn_067.md) | inspect goal_info | complete / unknown / closed_candidate, 0 goals, goal 12 chars | read-only inspect |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:07 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 357 chars | read-only inspect |  |
| T0.1-2 | +00:38 | [29.8 s](./views/Tree_0_1/thinking/turn_002.md) | 199 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | inspect lemma_index | probability / pr / probability, 1 goal, goal 357 chars | read-only inspect |  |
| T0.1-3 | +01:15 | [36.8 s](./views/Tree_0_1/thinking/turn_003.md) | 1.2 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | lookup Indist.Distinguish | probability / pr / probability, 1 goal, goal 357 chars | lookup result |  |
| T0.1-4 | +01:51 | [35.4 s](./views/Tree_0_1/thinking/turn_004.md) | 1.6 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | probe have ->: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = P... | probability / pr / probability, 1 goal, goal 357 chars | accepted probe |  |
| T0.1-5 | +01:58 | [5.4 s](./views/Tree_0_1/thinking/turn_005.md) | 597 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit have ->: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = P... | probability / pr / probability, 1 goal, goal 357 chars | accepted commit |  |
| T0.1-6 | +02:10 | [10.9 s](./views/Tree_0_1/thinking/turn_006.md) | 1.1 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | lookup CCA_game | probability / pr / probability, 2 goals, goal 261 chars | lookup result |  |
| T0.1-7 | +02:48 | [36.8 s](./views/Tree_0_1/thinking/turn_007.md) | 1.2 s | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | lookup RealOrcls | probability / pr / probability, 2 goals, goal 261 chars | lookup result |  |
| T0.1-8 | +06:28 | [218.8 s](./views/Tree_0_1/thinking/turn_008.md) | 1.2 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | lookup pr_CCP_OCCP | probability / pr / probability, 2 goals, goal 261 chars | lookup result |  |
| T0.1-9 | +07:12 | [43.7 s](./views/Tree_0_1/thinking/turn_009.md) | 338 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | inspect equiv_bridge_lemmas | probability / pr / probability, 2 goals, goal 261 chars | read-only inspect |  |
| T0.1-10 | +08:21 | [68.4 s](./views/Tree_0_1/thinking/turn_010.md) | 1.6 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | probe have h1: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = P... | probability / pr / probability, 2 goals, goal 261 chars | accepted probe |  |
| T0.1-11 | +08:45 | [22.4 s](./views/Tree_0_1/thinking/turn_011.md) | 640 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit have ->: Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = P... | probability / pr / probability, 2 goals, goal 261 chars | accepted commit |  |
| T0.1-12 | +09:02 | [16.3 s](./views/Tree_0_1/thinking/turn_012.md) | 1.7 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | probe byequiv=>// | probability / pr / probability, 3 goals, goal 287 chars | accepted probe |  |
| T0.1-13 | +09:12 | [7.8 s](./views/Tree_0_1/thinking/turn_013.md) | 195 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit byequiv=>// | probability / pr / probability, 3 goals, goal 287 chars | accepted commit |  |
| T0.1-14 | +09:37 | [24.8 s](./views/Tree_0_1/thinking/turn_014.md) | 1.2 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | probe proc | equiv / prhl_module / relational_program, 3 goals, goal 502 chars | accepted probe |  |
| T0.1-15 | +10:02 | [23.8 s](./views/Tree_0_1/thinking/turn_015.md) | 209 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | probe proc; sim | equiv / prhl_module / relational_program, 3 goals, goal 502 chars | accepted probe |  |
| T0.1-16 | +10:18 | [15.7 s](./views/Tree_0_1/thinking/turn_016.md) | 280 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit proc; sim | equiv / prhl_module / relational_program, 3 goals, goal 502 chars | accepted commit |  |
| T0.1-17 | +10:30 | [11.8 s](./views/Tree_0_1/thinking/turn_017.md) | 1.2 s | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | probe inline *; auto | pRHL / procedure_body / seq_cut, 3 goals, goal 471 chars | accepted probe |  |
| T0.1-18 | +10:41 | [10.3 s](./views/Tree_0_1/thinking/turn_018.md) | 663 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit inline *; auto | pRHL / procedure_body / seq_cut, 3 goals, goal 471 chars | accepted commit |  |
| T0.1-19 | +11:04 | [22.4 s](./views/Tree_0_1/thinking/turn_019.md) | 1.6 s | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | probe rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m) | probability / pr / probability, 2 goals, goal 287 chars | accepted probe |  |
| T0.1-20 | +11:17 | [11.4 s](./views/Tree_0_1/thinking/turn_020.md) | 627 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m) | probability / pr / probability, 2 goals, goal 287 chars | accepted commit |  |
| T0.1-21 | +11:54 | [35.8 s](./views/Tree_0_1/thinking/turn_021.md) | 207 ms | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit byequiv=>// | probability / pr / probability, 2 goals, goal 271 chars | accepted commit |  |
| T0.1-22 | +12:25 | [30.7 s](./views/Tree_0_1/thinking/turn_022.md) | 278 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 459 chars | accepted commit |  |
| T0.1-23 | +12:52 | [26.9 s](./views/Tree_0_1/thinking/turn_023.md) | 1.1 s | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 2 goals, goal 900 chars | read-only inspect |  |
| T0.1-24 | +13:15 | [21.8 s](./views/Tree_0_1/thinking/turn_024.md) | 211 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | probe inline{2} D(A, IndBlock).guess | pRHL / call_site / failure_diagnostic, 2 goals, goal 900 chars | accepted probe |  |
| T0.1-25 | +13:38 | [23.7 s](./views/Tree_0_1/thinking/turn_025.md) | 1.3 s | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | commit inline{2} D(A, IndBlock).guess | pRHL / call_site / failure_diagnostic, 2 goals, goal 900 chars | accepted commit |  |
| T0.1-26 | +13:50 | [9.8 s](./views/Tree_0_1/thinking/turn_026.md) | 186 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | probe wp | pRHL / call_site / seq_cut, 2 goals, goal 1110 chars | accepted probe |  |
| T0.1-27 | +14:01 | [10.8 s](./views/Tree_0_1/thinking/turn_027.md) | 1.2 s | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | commit wp | pRHL / call_site / seq_cut, 2 goals, goal 1110 chars | accepted commit |  |
| T0.1-28 | +14:15 | [12.8 s](./views/Tree_0_1/thinking/turn_028.md) | 212 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | probe call Mem.k | pRHL / call_site / seq_cut, 2 goals, goal 1028 chars | accepted probe |  |
| T0.1-29 | +14:28 | [12.8 s](./views/Tree_0_1/thinking/turn_029.md) | 184 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | commit call Mem.k | pRHL / call_site / relational_program, 2 goals, goal 1028 chars | accepted commit |  |
| T0.1-30 | +14:54 | [25.8 s](./views/Tree_0_1/thinking/turn_030.md) | 1.2 s | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | probe proc; inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted probe |  |
| T0.1-31 | +15:26 | [30.8 s](./views/Tree_0_1/thinking/turn_031.md) | 211 ms | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | probe proc; inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc; wp; call poly_mac1; call chacha... | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted probe |  |
| T0.1-32 | +15:38 | [11.8 s](./views/Tree_0_1/thinking/turn_032.md) | 194 ms | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit proc; inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc; wp; call poly_mac1; call chacha... | equiv / prhl_module / relational_program, 4 goals, goal 332 chars | accepted commit |  |
| T0.1-33 | +16:06 | [27.8 s](./views/Tree_0_1/thinking/turn_033.md) | 1.2 s | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | probe proc; inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | accepted probe |  |
| T0.1-34 | +17:30 | [82.8 s](./views/Tree_0_1/thinking/turn_034.md) | 216 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | probe proc; inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec; sp; wp | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | accepted probe |  |
| T0.1-35 | +18:08 | 38 s |  | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | unknown | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | repair / unhealthy |  |
| T0.1-36 | +18:14 | 6 s |  | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | unknown | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | repair / unhealthy |  |
| T0.1-37 | +18:21 | 7 s |  | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | unknown | equiv / prhl_module / relational_program, 3 goals, goal 332 chars | repair / unhealthy |  |
