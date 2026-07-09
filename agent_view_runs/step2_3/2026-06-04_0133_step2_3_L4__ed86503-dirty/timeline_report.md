# Agent-View Timeline — `step2_3`

| field | value |
|---|---|
| commit | `ed86503` **(dirty/uncommitted)** |
| branch | `eval-suite-48` |
| run time | 2026-06-04_0133_step2_3 |
| lemma | `step2_3` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 65 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 8 tactic(s) committed, not closed

```easycrypt
proof.
  congr.
  have ->: Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] = Pr[MainD(G4(A), FinRO).distinguish() @ &m : res].
  byequiv => //; proc; inline *; sim.
  rewrite -(pr_RO_FinRO_D _ (G4(A)) &m tt (fun (r:bool) => r)).
  move=> _; exact dblock_ll.
  have ->: Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res] = Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res].
  apply eq_sym; apply (SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m tt).
  have ->: Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res].
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  congr.
  have -> : Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] = Pr[MainD(G4(A), FinRO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ b => b) &m ()) /=.
  have -> : Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  rewrite -(SplitC1.pr_RO_split (G6(A)) (fun _ b => b) &m ()) /=.
  have -> : Pr[Split0.IdealAll.MainD(G6(A), Split0.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G4(A), SplitD.RO_DOM(SplitD.ROT.RO, SplitD.ROF.RO)).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  rewrite -(SplitD.pr_RO_split (G4(A)) (fun _ b => b) &m ()) /=.
  have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll.
  rewrite -(FiniteRO.pr_RO_FinRO_D Hll (G4(A)) &m () (fun b => b)) /=.
  byequiv => //; proc; inline *; sim.
  have -> : Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = Pr[MainD(G5(A), FinRO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  rewrite -(SplitC2.pr_RO_split (G9(A)) (fun _ b => b) &m ()) /=.
  have -> : Pr[Split1.IdealAll.MainD(G9(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G7(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  rewrite -(SplitC1.pr_RO_split (G7(A)) (fun _ b => b) &m ()) /=.
  have -> : Pr[Split0.IdealAll.MainD(G7(A), Split0.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G5(A), SplitD.RO_DOM(SplitD.ROT.RO, SplitD.ROF.RO)).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.
  rewrite -(SplitD.pr_RO_split (G5(A)) (fun _ b => b) &m ()) /=.
  have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll.
  rewrite -(FiniteRO.pr_RO_FinRO_D Hll (G5(A)) &m () (fun b => b)) /=.
  byequiv => //; proc; inline *; sim.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-04_0133_step2_3

Run dir: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1`

t=0: `2026-06-04T08:33:54.800000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:20 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 424 chars | read-only inspect |  |
| T0.0-2 | +00:52 | [30.8 s](./views/Tree_0_0/thinking/turn_002.md) | 163 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | inspect equiv_bridge_lemmas | probability / pr / probability, 1 goal, goal 424 chars | read-only inspect |  |
| T0.0-3 | +04:21 | [208.9 s](./views/Tree_0_0/thinking/turn_003.md) | 135 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | inspect lemma_index | probability / pr / probability, 1 goal, goal 424 chars | read-only inspect |  |
| T0.0-4 | +06:35 | [133.8 s](./views/Tree_0_0/thinking/turn_004.md) | 1.2 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | probe congr | probability / pr / probability, 1 goal, goal 424 chars | accepted probe |  |
| T0.0-5 | +06:48 | [11.3 s](./views/Tree_0_0/thinking/turn_005.md) | 658 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit congr | probability / pr / probability, 1 goal, goal 424 chars | accepted commit |  |
| T0.0-6 | +12:12 | [323.4 s](./views/Tree_0_0/thinking/turn_006.md) | 1.6 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe have ->: Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(Fin... | probability / pr / probability, 2 goals, goal 321 chars | accepted probe |  |
| T0.0-7 | +12:22 | [8.4 s](./views/Tree_0_0/thinking/turn_007.md) | 612 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit have ->: Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(Fin... | probability / pr / probability, 2 goals, goal 321 chars | accepted commit |  |
| T0.0-8 | +12:30 | [7.4 s](./views/Tree_0_0/thinking/turn_008.md) | 1.6 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | probe byequiv => //; proc; inline *; sim | probability / pr / probability, 3 goals, goal 286 chars | accepted probe |  |
| T0.0-9 | +12:42 | [10.5 s](./views/Tree_0_0/thinking/turn_009.md) | 540 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit byequiv => //; proc; inline *; sim | probability / pr / probability, 3 goals, goal 286 chars | accepted commit |  |
| T0.0-10 | +13:39 | [56.9 s](./views/Tree_0_0/thinking/turn_010.md) | 1.1 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | lookup pr_RO_FinRO_D | probability / pr / probability, 2 goals, goal 280 chars | lookup result |  |
| T0.0-11 | +14:13 | [32.5 s](./views/Tree_0_0/thinking/turn_011.md) | 1.5 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | probe rewrite -(pr_RO_FinRO_D (fun (_:nonce*C.counter) => dblock_ll) (G4(A)... | probability / pr / probability, 2 goals, goal 280 chars | rejected probe: expecting a `proof-term', not a `formula' |  |
| T0.0-12 | +15:13 | [58.5 s](./views/Tree_0_0/thinking/turn_012.md) | 544 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | probe rewrite -(pr_RO_FinRO_D _ (G4(A)) &m) | probability / pr / probability, 2 goals, goal 280 chars | rejected probe: nothing to rewrite |  |
| T0.0-13 | +15:44 | [30.5 s](./views/Tree_0_0/thinking/turn_013.md) | 534 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | probe rewrite -(pr_RO_FinRO_D _ (G4(A)) &m tt (fun (r:bool) => r)) | probability / pr / probability, 2 goals, goal 280 chars | accepted probe |  |
| T0.0-14 | +16:02 | [17.8 s](./views/Tree_0_0/thinking/turn_014.md) | 203 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit rewrite -(pr_RO_FinRO_D _ (G4(A)) &m tt (fun (r:bool) => r)) | probability / pr / probability, 2 goals, goal 280 chars | accepted commit |  |
| T0.0-15 | +16:11 | [8.5 s](./views/Tree_0_0/thinking/turn_015.md) | 538 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit move=> _; exact dblock_ll | ambient / ambient_logic, 3 goals, goal 196 chars | accepted commit |  |
| T0.0-16 | +18:15 | [123.5 s](./views/Tree_0_0/thinking/turn_016.md) | 1.5 s | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | probe have ->: Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.R... | probability / pr / probability, 2 goals, goal 299 chars | accepted probe |  |
| T0.0-17 | +18:29 | [12.5 s](./views/Tree_0_0/thinking/turn_017.md) | 529 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit have ->: Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.R... | probability / pr / probability, 2 goals, goal 299 chars | accepted commit |  |
| T0.0-18 | +18:51 | [21.4 s](./views/Tree_0_0/thinking/turn_018.md) | 1.6 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | probe apply eq_sym; apply (SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m tt) | probability / pr / probability, 3 goals, goal 309 chars | accepted probe |  |
| T0.0-19 | +19:03 | [10.5 s](./views/Tree_0_0/thinking/turn_019.md) | 532 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit apply eq_sym; apply (SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m tt) | probability / pr / probability, 3 goals, goal 309 chars | accepted commit |  |
| T0.0-20 | +19:36 | [32.4 s](./views/Tree_0_0/thinking/turn_020.md) | 1.6 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | probe have ->: Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distingu... | probability / pr / probability, 2 goals, goal 293 chars | accepted probe |  |
| T0.0-21 | +19:47 | [9.5 s](./views/Tree_0_0/thinking/turn_021.md) | 541 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit have ->: Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distingu... | probability / pr / probability, 2 goals, goal 293 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 424 chars | read-only inspect |  |
| T0.1-2 | +00:33 | [32 s](./views/Tree_0_1/thinking/turn_002.md) |  | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | inspect proof_map | probability / pr / probability, 1 goal, goal 424 chars | read-only inspect |  |
| T0.1-3 | +00:47 | 13.8 s | 168 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | inspect equiv_bridge_lemmas | probability / pr / probability, 1 goal, goal 424 chars | read-only inspect |  |
| T0.1-4 | +07:00 | [372.8 s](./views/Tree_0_1/thinking/turn_004.md) | 1.2 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | probe congr | probability / pr / probability, 1 goal, goal 424 chars | accepted probe |  |
| T0.1-5 | +07:13 | [11.4 s](./views/Tree_0_1/thinking/turn_005.md) | 648 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit congr | probability / pr / probability, 1 goal, goal 424 chars | accepted commit |  |
| T0.1-6 | +07:48 | [34.3 s](./views/Tree_0_1/thinking/turn_006.md) | 1.7 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | probe have -> : Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : re... | probability / pr / probability, 2 goals, goal 321 chars | accepted probe |  |
| T0.1-7 | +08:02 | [12.5 s](./views/Tree_0_1/thinking/turn_007.md) | 529 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit have -> : Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : re... | probability / pr / probability, 2 goals, goal 321 chars | accepted commit |  |
| T0.1-8 | +08:11 | [8.8 s](./views/Tree_0_1/thinking/turn_008.md) | 1.2 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | lookup SplitC2.pr_RO_split | probability / pr / probability, 2 goals, goal 280 chars | lookup result |  |
| T0.1-9 | +09:02 | [49.8 s](./views/Tree_0_1/thinking/turn_009.md) | 1.2 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | lookup SplitC1.pr_RO_split | probability / pr / probability, 2 goals, goal 280 chars | lookup result |  |
| T0.1-10 | +09:08 | 4.8 s | 1.2 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | lookup SplitD.pr_RO_split | probability / pr / probability, 2 goals, goal 280 chars | lookup result |  |
| T0.1-11 | +09:20 | 10.9 s | 1.1 s | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | lookup pr_RO_FinRO_D | probability / pr / probability, 2 goals, goal 280 chars | lookup result |  |
| T0.1-12 | +10:50 | [88.5 s](./views/Tree_0_1/thinking/turn_012.md) | 1.5 s | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | probe rewrite -(SplitC2.pr_RO_split (G8 A)) | probability / pr / probability, 2 goals, goal 280 chars | rejected probe: expecting a `module', not a `formula' |  |
| T0.1-13 | +11:07 | [15.5 s](./views/Tree_0_1/thinking/turn_013.md) | 523 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | probe rewrite -(SplitC2.pr_RO_split (G8(A))) | probability / pr / probability, 2 goals, goal 280 chars | rejected probe: nothing to rewrite |  |
| T0.1-14 | +11:25 | [17.5 s](./views/Tree_0_1/thinking/turn_014.md) | 545 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | probe rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ b => b) &m ()) | probability / pr / probability, 2 goals, goal 280 chars | accepted probe |  |
| T0.1-15 | +12:40 | [74.5 s](./views/Tree_0_1/thinking/turn_015.md) | 528 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | probe rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 2 goals, goal 280 chars | accepted probe |  |
| T0.1-16 | +13:21 | [40.5 s](./views/Tree_0_1/thinking/turn_016.md) | 523 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 2 goals, goal 280 chars | accepted commit |  |
| T0.1-17 | +14:06 | [44.4 s](./views/Tree_0_1/thinking/turn_017.md) | 1.6 s | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | probe have -> : Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[... | probability / pr / probability, 2 goals, goal 274 chars | accepted probe |  |
| T0.1-18 | +14:21 | [13.4 s](./views/Tree_0_1/thinking/turn_018.md) | 551 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit have -> : Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[... | probability / pr / probability, 2 goals, goal 274 chars | accepted commit |  |
| T0.1-19 | +14:27 | [5.4 s](./views/Tree_0_1/thinking/turn_019.md) | 1.6 s | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | probe rewrite -(SplitC1.pr_RO_split (G6(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 2 goals, goal 326 chars | accepted probe |  |
| T0.1-20 | +14:54 | [25.5 s](./views/Tree_0_1/thinking/turn_020.md) | 518 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit rewrite -(SplitC1.pr_RO_split (G6(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 2 goals, goal 326 chars | accepted commit |  |
| T0.1-21 | +15:08 | [13.4 s](./views/Tree_0_1/thinking/turn_021.md) | 1.6 s | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | probe have -> : Pr[Split0.IdealAll.MainD(G6(A), Split0.IdealAll.RO).distinguish() @ &m : res] = Pr[... | probability / pr / probability, 2 goals, goal 274 chars | accepted probe |  |
| T0.1-22 | +15:19 | [9.4 s](./views/Tree_0_1/thinking/turn_022.md) | 569 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | commit have -> : Pr[Split0.IdealAll.MainD(G6(A), Split0.IdealAll.RO).distinguish() @ &m : res] = Pr[... | probability / pr / probability, 2 goals, goal 274 chars | accepted commit |  |
| T0.1-23 | +15:24 | [4.4 s](./views/Tree_0_1/thinking/turn_023.md) | 1.6 s | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | probe rewrite -(SplitD.pr_RO_split (G4(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 2 goals, goal 281 chars | accepted probe |  |
| T0.1-24 | +15:37 | [11.4 s](./views/Tree_0_1/thinking/turn_024.md) | 554 ms | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit rewrite -(SplitD.pr_RO_split (G4(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 2 goals, goal 281 chars | accepted commit |  |
| T0.1-25 | +16:12 | [34.4 s](./views/Tree_0_1/thinking/turn_025.md) | 1.6 s | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | probe rewrite -(FiniteRO.pr_RO_FinRO_D (fun _ => Block.dblock_ll) (G4(A)) &... | probability / pr / probability, 2 goals, goal 274 chars | rejected probe: expecting a `proof-term', not a `formula' |  |
| T0.1-26 | +17:24 | [70.5 s](./views/Tree_0_1/thinking/turn_026.md) | 549 ms | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | probe have Hll : forall (_ : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll | probability / pr / probability, 2 goals, goal 274 chars | rejected probe: invalid name: `_ |  |
| T0.1-27 | +17:30 | [5.5 s](./views/Tree_0_1/thinking/turn_027.md) | 546 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | probe have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll | probability / pr / probability, 2 goals, goal 274 chars | accepted probe |  |
| T0.1-28 | +17:38 | [7.5 s](./views/Tree_0_1/thinking/turn_028.md) | 550 ms | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll | probability / pr / probability, 2 goals, goal 274 chars | accepted commit |  |
| T0.1-29 | +17:44 | [5.4 s](./views/Tree_0_1/thinking/turn_029.md) | 1.6 s | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | probe rewrite -(FiniteRO.pr_RO_FinRO_D Hll (G4(A)) &m () (fun b => b)) /= | probability / pr / probability, 2 goals, goal 330 chars | accepted probe |  |
| T0.1-30 | +17:57 | [11.5 s](./views/Tree_0_1/thinking/turn_030.md) | 547 ms | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit rewrite -(FiniteRO.pr_RO_FinRO_D Hll (G4(A)) &m () (fun b => b)) /= | probability / pr / probability, 2 goals, goal 330 chars | accepted commit |  |
| T0.1-31 | +18:04 | [6.4 s](./views/Tree_0_1/thinking/turn_031.md) | 1.6 s | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | probe byequiv => //; proc; inline *; sim | probability / pr / probability, 2 goals, goal 327 chars | accepted probe |  |
| T0.1-32 | +18:37 | [31.4 s](./views/Tree_0_1/thinking/turn_032.md) | 593 ms | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit byequiv => //; proc; inline *; sim | probability / pr / probability, 2 goals, goal 327 chars | accepted commit |  |
| T0.1-33 | +18:46 | [8.3 s](./views/Tree_0_1/thinking/turn_033.md) | 1.7 s | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | probe have -> : Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = Pr[MainD(G5(A), FinRO).distinguish() @... | probability / pr / probability, 1 goal, goal 259 chars | accepted probe |  |
| T0.1-34 | +18:59 | [11.4 s](./views/Tree_0_1/thinking/turn_034.md) | 552 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | commit have -> : Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = Pr[MainD(G5(A), FinRO).distinguish() @... | probability / pr / probability, 1 goal, goal 259 chars | accepted commit |  |
| T0.1-35 | +19:05 | [5.5 s](./views/Tree_0_1/thinking/turn_035.md) | 547 ms | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit rewrite -(SplitC2.pr_RO_split (G9(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 1 goal, goal 265 chars | accepted commit |  |
| T0.1-36 | +19:14 | [8.4 s](./views/Tree_0_1/thinking/turn_036.md) | 609 ms | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | commit have -> : Pr[Split1.IdealAll.MainD(G9(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[... | probability / pr / probability, 1 goal, goal 259 chars | accepted commit |  |
| T0.1-37 | +19:19 | [4.4 s](./views/Tree_0_1/thinking/turn_037.md) | 568 ms | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | commit rewrite -(SplitC1.pr_RO_split (G7(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 1 goal, goal 311 chars | accepted commit |  |
| T0.1-38 | +19:27 | [7.4 s](./views/Tree_0_1/thinking/turn_038.md) | 566 ms | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | commit have -> : Pr[Split0.IdealAll.MainD(G7(A), Split0.IdealAll.RO).distinguish() @ &m : res] = Pr[... | probability / pr / probability, 1 goal, goal 259 chars | accepted commit |  |
| T0.1-39 | +19:32 | [4.4 s](./views/Tree_0_1/thinking/turn_039.md) | 587 ms | [turn_038.json](./views/Tree_0_1/turn_038.json) · [inline read](./views/Tree_0_1/followups/turn_038.md) | commit rewrite -(SplitD.pr_RO_split (G5(A)) (fun _ b => b) &m ()) /= | probability / pr / probability, 1 goal, goal 266 chars | accepted commit |  |
| T0.1-40 | +19:39 | [6.4 s](./views/Tree_0_1/thinking/turn_040.md) | 552 ms | [turn_039.json](./views/Tree_0_1/turn_039.json) · [inline read](./views/Tree_0_1/followups/turn_039.md) | commit have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll | probability / pr / probability, 1 goal, goal 259 chars | accepted commit |  |
| T0.1-41 | +19:45 | [5.5 s](./views/Tree_0_1/thinking/turn_041.md) | 544 ms | [turn_040.json](./views/Tree_0_1/turn_040.json) · [inline read](./views/Tree_0_1/followups/turn_040.md) | commit rewrite -(FiniteRO.pr_RO_FinRO_D Hll (G5(A)) &m () (fun b => b)) /= | probability / pr / probability, 1 goal, goal 315 chars | accepted commit |  |
| T0.1-42 | +19:51 | [5.8 s](./views/Tree_0_1/thinking/turn_042.md) | 225 ms | [turn_041.json](./views/Tree_0_1/turn_041.json) · [inline read](./views/Tree_0_1/followups/turn_041.md) | commit byequiv => //; proc; inline *; sim | probability / pr / probability, 1 goal, goal 312 chars | accepted commit |  |
| T0.1-43 | +19:56 | [4.8 s](./views/Tree_0_1/thinking/turn_043.md) | 203 ms | [turn_042.json](./views/Tree_0_1/turn_042.json) · [inline read](./views/Tree_0_1/followups/turn_042.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-44 | +20:07 | [10.9 s](./views/Tree_0_1/thinking/turn_044.md) | 105 ms | [turn_043.json](./views/Tree_0_1/turn_043.json) · [inline read](./views/Tree_0_1/followups/turn_043.md) | inspect goal_info | complete / unknown / closed_candidate, 0 goals, goal 12 chars | read-only inspect |  |
