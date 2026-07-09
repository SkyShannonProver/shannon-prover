# Agent-View Timeline — `step2_3`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1517_step2_3 |
| lemma | `step2_3` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 33 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  congr.
  rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m ()).
  simplify.
  have ->: Pr[CCA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] = Pr[MainD(G4(A), FinRO).distinguish() @ &m : res].
  byequiv => //; proc; inline *; sim.
  have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll.
  have h2 := pr_RO_FinRO_D h_dout (G4(A)) &m () (fun (r:bool) => r); rewrite /= in h2; rewrite -h2.
  have ->: Pr[MainD(G4(A), RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G4(A), Split0.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have hA := SplitD.pr_RO_split (G4(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA.
  have ->: Pr[Split0.IdealAll.MainD(G4(A), RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), ROT.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have ->: Pr[Split0.IdealAll.MainD(G6(A), ROT.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), Split0.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have hB := SplitC1.pr_RO_split (G6(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hB; rewrite hB.
  have ->: Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res] = Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  done.
  rewrite -(SplitC2.pr_RO_split (G9(A)) (fun _ (r:bool) => r) &m ()).
  simplify.
  have ->: Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = Pr[MainD(G5(A), FinRO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll. have hC := pr_RO_FinRO_D h_dout (G5(A)) &m () (fun (r:bool) => r); rewrite /= in hC; rewrite -hC.
  have ->: Pr[MainD(G5(A), RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G5(A), Split0.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have hA := SplitD.pr_RO_split (G5(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA.
  have ->: Pr[Split0.IdealAll.MainD(G5(A), RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G7(A), ROT.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have ->: Pr[Split0.IdealAll.MainD(G7(A), ROT.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G7(A), Split0.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  have hB := SplitC1.pr_RO_split (G7(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hB; rewrite hB.
  have ->: Pr[Split0.IdealAll.MainD(G7(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res] = Pr[Split1.IdealAll.MainD(G9(A), Split1.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  done.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1517_step2_3

Run dir: `artifacts/eval_suite/rerun_struct_core/l1_goal_projection/step2_3/r01/2026-06-10_1517_step2_3/iteration_1`

t=0: `2026-06-10T22:23:38.800000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit congr | probability / pr / probability, 1 goal, goal 424 chars | accepted commit |  |
| T0.0-2 | +00:11 | [8.3 s](./views/Tree_0_0/thinking/turn_002.md) | 689 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m ()) | probability / pr / probability, 2 goals, goal 321 chars | accepted commit |  |
| T0.0-3 | +00:22 | [10.3 s](./views/Tree_0_0/thinking/turn_003.md) | 688 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit simplify | probability / pr / probability, 2 goals, goal 563 chars | accepted commit |  |
| T0.0-4 | +01:16 | [53.7 s](./views/Tree_0_0/thinking/turn_004.md) | 251 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit byequiv=>// | probability / pr / probability, 2 goals, goal 315 chars | accepted commit |  |
| T0.0-5 | +08:06 | 410.3 s | 1.7 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | undo_last_step | equiv / prhl_module / relational_program, 2 goals, goal 369 chars | undo result |  |
| T0.0-6 | +08:48 | [40.1 s](./views/Tree_0_0/thinking/turn_006.md) | 1.9 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit have ->: Pr[CCA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(Fin... | probability / pr / probability, 2 goals, goal 302 chars | accepted commit |  |
| T0.0-7 | +09:08 | [17.4 s](./views/Tree_0_0/thinking/turn_007.md) | 603 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit byequiv => //; proc; inline *; sim | probability / pr / probability, 3 goals, goal 286 chars | accepted commit |  |
| T0.0-8 | +10:16 | [68.3 s](./views/Tree_0_0/thinking/turn_008.md) | 1.7 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit have h2 := pr_RO_FinRO_D (fun (_:nonce*C.counter) => dblock_ll) (G4(A)) &m () (fun (r:bool) =... | probability / pr / probability, 2 goals, goal 274 chars | rejected commit: [error] expecting a `proof-term', not a `formula' |  |
| T0.0-9 | +10:44 | [25.4 s](./views/Tree_0_0/thinking/turn_009.md) | 556 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll | probability / pr / failure_diagnostic, 2 goals, goal 274 chars | accepted commit |  |
| T0.0-10 | +10:52 | [7.5 s](./views/Tree_0_0/thinking/turn_010.md) | 545 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit have h2 := pr_RO_FinRO_D h_dout (G4(A)) &m () (fun (r:bool) => r); rewrite /= in h2; rewrite -h2 | probability / pr / probability, 2 goals, goal 333 chars | accepted commit |  |
| T0.0-11 | +17:55 | [423.1 s](./views/Tree_0_0/thinking/turn_011.md) | 1.9 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit have hA := SplitD.pr_RO_split (G4(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA | probability / pr / probability, 2 goals, goal 435 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-12 | +18:42 | [45.3 s](./views/Tree_0_0/thinking/turn_012.md) | 703 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit have ->: Pr[MainD(G4(A), RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G4(A), Spli... | probability / pr / failure_diagnostic, 2 goals, goal 435 chars | accepted commit |  |
| T0.0-13 | +18:54 | [10.4 s](./views/Tree_0_0/thinking/turn_013.md) | 572 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit have hA := SplitD.pr_RO_split (G4(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA | probability / pr / probability, 2 goals, goal 467 chars | accepted commit |  |
| T0.0-14 | +19:21 | [26.4 s](./views/Tree_0_0/thinking/turn_014.md) | 642 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit have ->: Pr[Split0.IdealAll.MainD(G4(A), RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res] =... | probability / pr / probability, 2 goals, goal 659 chars | accepted commit |  |
| T0.0-15 | +19:39 | [17.4 s](./views/Tree_0_0/thinking/turn_015.md) | 579 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit have ->: Pr[Split0.IdealAll.MainD(G6(A), ROT.RO).distinguish() @ &m : res] = Pr[Split0.IdealA... | probability / pr / probability, 2 goals, goal 640 chars | accepted commit |  |
| T0.0-16 | +20:08 | [28.4 s](./views/Tree_0_0/thinking/turn_016.md) | 606 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit have hB := SplitC1.pr_RO_split (G6(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hB; rewrite hB | probability / pr / probability, 2 goals, goal 652 chars | accepted commit |  |
| T0.0-17 | +20:23 | [14.4 s](./views/Tree_0_0/thinking/turn_017.md) | 584 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit have ->: Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).disti... | probability / pr / probability, 2 goals, goal 937 chars | accepted commit |  |
| T0.0-18 | +20:28 | [4.3 s](./views/Tree_0_0/thinking/turn_018.md) | 670 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit done | probability / pr / probability, 2 goals, goal 885 chars | accepted commit |  |
| T0.0-19 | +20:56 | [27.4 s](./views/Tree_0_0/thinking/turn_019.md) | 623 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit rewrite -(SplitC2.pr_RO_split (G9(A)) (fun _ (r:bool) => r) &m ()) | probability / pr / probability, 1 goal, goal 259 chars | accepted commit |  |
| T0.0-20 | +21:05 | [8.4 s](./views/Tree_0_0/thinking/turn_020.md) | 644 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit simplify | probability / pr / probability, 1 goal, goal 501 chars | accepted commit |  |
| T0.0-21 | +23:00 | [114.4 s](./views/Tree_0_0/thinking/turn_021.md) | 631 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit have ->: Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = Pr[MainD(G5(A), FinRO).distinguish() @... | probability / pr / probability, 1 goal, goal 253 chars | accepted commit |  |
| T0.0-22 | +23:15 | [15.2 s](./views/Tree_0_0/thinking/turn_022.md) | 1.8 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit have hC := pr_RO_FinRO_D h_dout (G5(A)) &m () (fun (r:bool) => r); rewrite /= in hC; rewrite -hC | probability / pr / probability, 1 goal, goal 259 chars | rejected commit: [error] expecting a `proof-term', not a `formula' |  |
| T0.0-23 | +24:18 | [60.4 s](./views/Tree_0_0/thinking/turn_023.md) | 628 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll... | probability / pr / failure_diagnostic, 1 goal, goal 259 chars | accepted commit |  |
| T0.0-24 | +24:31 | [12.4 s](./views/Tree_0_0/thinking/turn_024.md) | 565 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit have ->: Pr[MainD(G5(A), RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G5(A), Spli... | probability / pr / probability, 1 goal, goal 420 chars | accepted commit |  |
| T0.0-25 | +24:35 | [3.3 s](./views/Tree_0_0/thinking/turn_025.md) | 656 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit have hA := SplitD.pr_RO_split (G5(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA | probability / pr / probability, 1 goal, goal 452 chars | accepted commit |  |
| T0.0-26 | +24:42 | [6.4 s](./views/Tree_0_0/thinking/turn_026.md) | 641 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit have ->: Pr[Split0.IdealAll.MainD(G5(A), RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res] =... | probability / pr / probability, 1 goal, goal 644 chars | accepted commit |  |
| T0.0-27 | +24:47 | [4.4 s](./views/Tree_0_0/thinking/turn_027.md) | 611 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit have ->: Pr[Split0.IdealAll.MainD(G7(A), ROT.RO).distinguish() @ &m : res] = Pr[Split0.IdealA... | probability / pr / probability, 1 goal, goal 625 chars | accepted commit |  |
| T0.0-28 | +24:52 | [4.4 s](./views/Tree_0_0/thinking/turn_028.md) | 636 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit have hB := SplitC1.pr_RO_split (G7(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hB; rewrite hB | probability / pr / probability, 1 goal, goal 637 chars | accepted commit |  |
| T0.0-29 | +25:00 | [7.7 s](./views/Tree_0_0/thinking/turn_029.md) | 1.3 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit have ->: Pr[Split0.IdealAll.MainD(G7(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).disti... | probability / pr / probability, 1 goal, goal 922 chars | accepted commit |  |
| T0.0-30 | +25:07 | [5.5 s](./views/Tree_0_0/thinking/turn_030.md) | 465 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit done | probability / pr / probability, 1 goal, goal 870 chars | accepted commit |  |
| T0.0-31 | +25:11 | 4 s |  | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | finish | ambient / closed_candidate, goal 26 chars | repair / unhealthy |  |
| T0.0-32 | +25:14 | [2.6 s](./views/Tree_0_0/thinking/turn_032.md) | 379 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-33 | +25:18 | 4 s |  | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
