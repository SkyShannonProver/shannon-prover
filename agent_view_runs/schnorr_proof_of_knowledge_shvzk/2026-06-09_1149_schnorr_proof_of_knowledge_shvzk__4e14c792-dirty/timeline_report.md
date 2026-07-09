# Agent-View Timeline — `schnorr_proof_of_knowledge_shvzk`

| field | value |
|---|---|
| commit | `4e14c792` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-09_1149_schnorr_proof_of_knowledge_shvzk |
| lemma | `schnorr_proof_of_knowledge_shvzk` |
| source file | `eval/examples/SchnorrPK.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 120 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 23 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  rcondf{1} 28.
  auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1).
  conseq (_: ={glob D} ==> _) => //.
  call (_: true).
  rcondt{1} 25.
  auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1).
  conseq (_: _ ==> ={x, t, glob D}).
  smt().
  seq 2 2 : (={w0, glob D}).
  auto.
  swap{2} 10 -5.
  wp.
  rnd (fun (u : ZModE.exp) => u - e1{2} * w{2}) (fun (u : ZModE.exp) => u + e1{2} * w{2}).
  wp.
  rnd (fun (u : ZModE.exp) => u) (fun (u : ZModE.exp) => u).
  wp.
  rnd{1}.
  wp.
  auto => />.
  move=> &2 r1 _ eL _; split=> [rR _|_ z1L _]; [by ring | split; [by ring | move=> _; rewrite -expM -expD; congr; ring]].
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  byequiv (_: ={glob D} ==> ={res}).
  proc.
  call (_: true).
  inline *.
  rcondf{1} 28.
  auto; smt(expN expD exp0 mulVc mulcA mulc1 mulcV mulcC).
  rcondt{1} 25.
  auto; smt(expN expD exp0 mulVc mulcA mulc1 mulcV mulcC).
  swap{1} 15 -5.
  swap{1} 10 1.
  swap{2} 12 -5.
  wp.
  rnd (fun z => z - e{1} * w{1}) (fun r => r + e{1} * w{1}).
  rnd.
  wp.
  rnd{1}.
  auto.
  smt(expD expM expN exp0 GP.ZModE.ZModpRing.mulrC GP.ZModE.ZModpRing.addrK GP.ZModE.ZModpRing.subrK GP.ZModE.ZModpRing.mulr0 GP.ZModE.ZModpRing.addr0 dt_ll dt_fu).
  done.
  smt().
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-09_1149_schnorr_proof_of_knowledge_shvzk

Run dir: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1`

t=0: `2026-06-09T18:49:23+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) |  | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect call_site_options | probability / pr / probability, 1 goal, goal 324 chars | read-only inspect |  |
| T0.0-2 | +01:11 | [70.8 s](./views/Tree_0_0/thinking/turn_002.md) | 1.2 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 324 chars | read-only inspect |  |
| T0.0-3 | +01:18 | [5.7 s](./views/Tree_0_0/thinking/turn_003.md) | 1.3 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | probe byequiv=>// | probability / pr / probability, 1 goal, goal 324 chars | accepted probe |  |
| T0.0-4 | +01:23 | [3.9 s](./views/Tree_0_0/thinking/turn_004.md) | 142 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 324 chars | accepted commit |  |
| T0.0-5 | +01:26 | [3.1 s](./views/Tree_0_0/thinking/turn_005.md) | 876 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 386 chars | accepted commit |  |
| T0.0-6 | +01:40 | [12.8 s](./views/Tree_0_0/thinking/turn_006.md) | 153 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe inline * | pRHL / call_site / seq_cut, 1 goal, goal 1955 chars | accepted probe |  |
| T0.0-7 | +01:49 | [8.7 s](./views/Tree_0_0/thinking/turn_007.md) | 2.3 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit inline * | pRHL / call_site / seq_cut, 1 goal, goal 1955 chars | accepted commit |  |
| T0.0-8 | +03:19 | [87.8 s](./views/Tree_0_0/thinking/turn_008.md) | 192 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | probe rcondf{1} 28 | pRHL / call_site / seq_cut, 1 goal, goal 6208 chars | accepted probe |  |
| T0.0-9 | +03:23 | [3.9 s](./views/Tree_0_0/thinking/turn_009.md) | 122 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit rcondf{1} 28 | pRHL / call_site / seq_cut, 1 goal, goal 6208 chars | accepted commit |  |
| T0.0-10 | +03:33 | [10.2 s](./views/Tree_0_0/thinking/turn_010.md) | 842 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | probe auto | hoare / procedure_body / procedure_frontier, 2 goals, goal 342 chars | accepted probe |  |
| T0.0-11 | +03:48 | [13.8 s](./views/Tree_0_0/thinking/turn_011.md) | 222 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | probe auto => />; smt(expD expM expN mulpV mulVp) | hoare / procedure_body / procedure_frontier, 2 goals, goal 342 chars | rejected probe: cannot find lemma `mulpV' |  |
| T0.0-12 | +03:59 | [10.6 s](./views/Tree_0_0/thinking/turn_012.md) | 3.4 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | probe auto => />; smt(expD expM expN) | hoare / procedure_body / procedure_frontier, 2 goals, goal 342 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-13 | +05:01 | [58.7 s](./views/Tree_0_0/thinking/turn_013.md) | 292 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | probe auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1) | hoare / procedure_body / procedure_frontier, 2 goals, goal 342 chars | accepted probe |  |
| T0.0-14 | +05:06 | [5.4 s](./views/Tree_0_0/thinking/turn_014.md) | 3.6 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1) | hoare / procedure_body / procedure_frontier, 2 goals, goal 342 chars | accepted commit |  |
| T0.0-15 | +05:29 | [18.8 s](./views/Tree_0_0/thinking/turn_015.md) | 220 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | probe call (_: ={glob D}) | pRHL / call_site / seq_cut, 1 goal, goal 3867 chars | rejected probe: The module D can write D (add restriction D to D, or D to D) |  |
| T0.0-16 | +05:55 | [25.8 s](./views/Tree_0_0/thinking/turn_016.md) | 151 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | inspect call_invariant_skeleton | pRHL / call_site / seq_cut, 1 goal, goal 3867 chars | read-only inspect |  |
| T0.0-17 | +06:34 | [38.8 s](./views/Tree_0_0/thinking/turn_017.md) | 232 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | probe conseq (_: ={glob D} ==> _) => // | pRHL / call_site / failure_diagnostic, 1 goal, goal 3867 chars | accepted probe |  |
| T0.0-18 | +06:38 | [3.7 s](./views/Tree_0_0/thinking/turn_018.md) | 3.3 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit conseq (_: ={glob D} ==> _) => // | pRHL / call_site / failure_diagnostic, 1 goal, goal 3867 chars | accepted commit |  |
| T0.0-19 | +06:46 | [4.8 s](./views/Tree_0_0/thinking/turn_019.md) | 161 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | probe call (_: ={glob D}) | pRHL / call_site / seq_cut, 1 goal, goal 3838 chars | rejected probe: The module D can write D (add restriction D to D, or D to D) |  |
| T0.0-20 | +07:11 | [24.9 s](./views/Tree_0_0/thinking/turn_020.md) | 102 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | inspect tactic_forms | pRHL / call_site / seq_cut, 1 goal, goal 3838 chars | read-only inspect |  |
| T0.0-21 | +07:16 | [4.8 s](./views/Tree_0_0/thinking/turn_021.md) | 194 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | probe call true | pRHL / call_site / seq_cut, 1 goal, goal 3838 chars | accepted probe |  |
| T0.0-22 | +07:22 | [6.5 s](./views/Tree_0_0/thinking/turn_022.md) | 3.5 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit call true | pRHL / call_site / seq_cut, 1 goal, goal 3838 chars | accepted commit |  |
| T0.0-23 | +07:37 | [10.8 s](./views/Tree_0_0/thinking/turn_023.md) | 181 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | probe rcondt{1} 25 | pRHL / procedure_body / seq_cut, 1 goal, goal 3993 chars | accepted probe |  |
| T0.0-24 | +07:42 | [4.8 s](./views/Tree_0_0/thinking/turn_024.md) | 155 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit rcondt{1} 25 | pRHL / procedure_body / seq_cut, 1 goal, goal 3993 chars | accepted commit |  |
| T0.0-25 | +07:47 | [4.7 s](./views/Tree_0_0/thinking/turn_025.md) | 1.3 s | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | probe auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1) | hoare / procedure_body / procedure_frontier, 2 goals, goal 257 chars | accepted probe |  |
| T0.0-26 | +08:20 | [32.4 s](./views/Tree_0_0/thinking/turn_026.md) | 3.6 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1) | hoare / procedure_body / procedure_frontier, 2 goals, goal 257 chars | accepted commit |  |
| T0.0-27 | +08:47 | [22.8 s](./views/Tree_0_0/thinking/turn_027.md) | 202 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | probe conseq (_: _ ==> ={x, t, glob D}) | pRHL / procedure_body / seq_cut, 1 goal, goal 3328 chars | accepted probe |  |
| T0.0-28 | +08:53 | [5.8 s](./views/Tree_0_0/thinking/turn_028.md) | 175 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit conseq (_: _ ==> ={x, t, glob D}) | pRHL / procedure_body / seq_cut, 1 goal, goal 3328 chars | accepted commit |  |
| T0.0-29 | +08:57 | [3.6 s](./views/Tree_0_0/thinking/turn_029.md) | 1.4 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | probe smt() | ambient / ambient_logic / relational_program, 2 goals, goal 650 chars | accepted probe |  |
| T0.0-30 | +09:06 | [8.1 s](./views/Tree_0_0/thinking/turn_030.md) | 3.9 s | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit smt() | ambient / ambient_logic / relational_program, 2 goals, goal 650 chars | accepted commit |  |
| T0.0-31 | +09:26 | [15.8 s](./views/Tree_0_0/thinking/turn_031.md) | 179 ms | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | probe seq 2 2 : (={w0, glob D}) | pRHL / procedure_body / seq_cut, 1 goal, goal 3138 chars | accepted probe |  |
| T0.0-32 | +09:30 | [3.8 s](./views/Tree_0_0/thinking/turn_032.md) | 176 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit seq 2 2 : (={w0, glob D}) | pRHL / procedure_body / seq_cut, 1 goal, goal 3138 chars | accepted commit |  |
| T0.0-33 | +09:34 | [3.5 s](./views/Tree_0_0/thinking/turn_033.md) | 1.5 s | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | probe auto | pRHL / procedure_body / relational_program, 2 goals, goal 1280 chars | accepted probe |  |
| T0.0-34 | +10:11 | [35.9 s](./views/Tree_0_0/thinking/turn_034.md) | 4.1 s | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | commit auto | pRHL / procedure_body / relational_program, 2 goals, goal 1280 chars | accepted commit |  |
| T0.0-35 | +12:58 | 162.8 s | 199 ms | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | probe swap{2} 10 -5 | pRHL / procedure_body / seq_cut, 1 goal, goal 2823 chars | accepted probe |  |
| T0.0-36 | +13:07 | 9.3 s | 3.7 s | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit swap{2} 10 -5 | pRHL / procedure_body / seq_cut, 1 goal, goal 2823 chars | accepted commit |  |
| T0.0-37 | +13:23 | 11.8 s | 195 ms | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | probe wp | pRHL / procedure_body / seq_cut, 1 goal, goal 2823 chars | accepted probe |  |
| T0.0-38 | +14:27 | 64 s | 4 s | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 2823 chars | accepted commit |  |
| T0.0-39 | +14:41 | 9.8 s | 209 ms | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | probe rnd (fun (u : ZModE.exp) => u + e1{2} * w{2}) (fun (u : ZModE.exp) =>... | pRHL / procedure_body / seq_cut, 1 goal, goal 1980 chars | accepted probe |  |
| T0.0-40 | +14:56 | 15.5 s | 1.5 s | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit rnd (fun (u : ZModE.exp) => u + e1{2} * w{2}) (fun (u : ZModE.exp) =>... | pRHL / procedure_body / seq_cut, 1 goal, goal 1980 chars | accepted commit |  |
| T0.0-41 | +15:06 | 7.8 s | 172 ms | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | probe wp | pRHL / procedure_body / seq_cut, 1 goal, goal 2144 chars | accepted probe |  |
| T0.0-42 | +15:17 | 10.6 s | 1.4 s | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 2144 chars | accepted commit |  |
| T0.0-43 | +15:26 | 7.8 s | 174 ms | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | probe rnd (fun (u : ZModE.exp) => u) (fun (u : ZModE.exp) => u) | pRHL / procedure_body / seq_cut, 1 goal, goal 1897 chars | accepted probe |  |
| T0.0-44 | +16:19 | 53 s |  | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | undo_last_step | pRHL / procedure_body / seq_cut, 1 goal, goal 1897 chars | undo result |  |
| T0.0-45 | +17:36 | 77 s |  | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | undo_last_step | pRHL / procedure_body / seq_cut, 1 goal, goal 1897 chars | undo result |  |
| T0.0-46 | +18:40 | 64.0 s | 35.0 s | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | undo_to_checkpoint | pRHL / procedure_body / seq_cut, 1 goal, goal 1897 chars | checkpoint rewind selected |  |
| T0.0-47 | +19:23 | 7.6 s | 1.4 s | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | undo_last_step | pRHL / procedure_body / seq_cut, 1 goal, goal 2144 chars | undo result |  |
| T0.0-48 | +19:34 | 9.6 s | 2.4 s | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | probe rnd (fun (u : ZModE.exp) => u - e1{2} * w{2}) (fun (u : ZModE.exp) =>... | pRHL / procedure_body / seq_cut, 1 goal, goal 1968 chars | accepted probe |  |
| T0.0-49 | +19:45 | 8.7 s | 1.3 s | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | commit rnd (fun (u : ZModE.exp) => u - e1{2} * w{2}) (fun (u : ZModE.exp) =>... | pRHL / procedure_body / seq_cut, 1 goal, goal 1968 chars | accepted commit |  |
| T0.0-50 | +19:52 | 5.7 s | 1.3 s | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 2144 chars | accepted commit |  |
| T0.0-51 | +19:59 | 5.8 s | 171 ms | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit rnd (fun (u : ZModE.exp) => u) (fun (u : ZModE.exp) => u) | pRHL / procedure_body / seq_cut, 1 goal, goal 1897 chars | accepted commit |  |
| T0.0-52 | +20:33 | 34.1 s | 4.9 s | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | probe auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1) | pRHL / procedure_body / relational_program, 1 goal, goal 1947 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-53 | +20:46 | 7.8 s | 191 ms | [turn_052.json](./views/Tree_0_0/turn_052.json) · [inline read](./views/Tree_0_0/followups/turn_052.md) | probe wp | pRHL / procedure_body / relational_program, 1 goal, goal 1947 chars | accepted probe |  |
| T0.0-54 | +20:58 | 11.8 s | 184 ms | [turn_053.json](./views/Tree_0_0/turn_053.json) · [inline read](./views/Tree_0_0/followups/turn_053.md) | commit wp | pRHL / procedure_body / relational_program, 1 goal, goal 1947 chars | accepted commit |  |
| T0.0-55 | +21:34 | 35.7 s | 1.3 s | [turn_054.json](./views/Tree_0_0/turn_054.json) · [inline read](./views/Tree_0_0/followups/turn_054.md) | probe rnd{1} | pRHL / procedure_body / relational_program, 1 goal, goal 1861 chars | accepted probe |  |
| T0.0-56 | +21:39 | 3.8 s | 162 ms | [turn_055.json](./views/Tree_0_0/turn_055.json) · [inline read](./views/Tree_0_0/followups/turn_055.md) | commit rnd{1} | pRHL / procedure_body / relational_program, 1 goal, goal 1861 chars | accepted commit |  |
| T0.0-57 | +21:48 | 9.5 s | 4.5 s | [turn_056.json](./views/Tree_0_0/turn_056.json) · [inline read](./views/Tree_0_0/followups/turn_056.md) | probe auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1) | pRHL / procedure_body / relational_program, 1 goal, goal 1888 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-58 | +22:05 | 11.8 s | 159 ms | [turn_057.json](./views/Tree_0_0/turn_057.json) · [inline read](./views/Tree_0_0/followups/turn_057.md) | probe wp | pRHL / procedure_body / relational_program, 1 goal, goal 1888 chars | accepted probe |  |
| T0.0-59 | +22:09 | 3.8 s | 166 ms | [turn_058.json](./views/Tree_0_0/turn_058.json) · [inline read](./views/Tree_0_0/followups/turn_058.md) | commit wp | pRHL / procedure_body / relational_program, 1 goal, goal 1888 chars | accepted commit |  |
| T0.0-60 | +23:24 | 74.6 s | 1.4 s | [turn_059.json](./views/Tree_0_0/turn_059.json) · [inline read](./views/Tree_0_0/followups/turn_059.md) | probe auto => /> | pRHL / procedure_body / relational_program, 1 goal, goal 1679 chars | accepted probe |  |
| T0.0-61 | +23:52 | 26.7 s | 3.3 s | [turn_060.json](./views/Tree_0_0/turn_060.json) · [inline read](./views/Tree_0_0/followups/turn_060.md) | probe auto => />; smt(expD expM) | pRHL / procedure_body / relational_program, 1 goal, goal 1679 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-62 | +24:11 | 15.8 s | 188 ms | [turn_061.json](./views/Tree_0_0/turn_061.json) · [inline read](./views/Tree_0_0/followups/turn_061.md) | commit auto => /> | pRHL / procedure_body / relational_program, 1 goal, goal 1679 chars | accepted commit |  |
| T0.0-63 | +24:36 | 25.4 s | 4.6 s | [turn_062.json](./views/Tree_0_0/turn_062.json) · [inline read](./views/Tree_0_0/followups/turn_062.md) | probe move=> &2 r1 _ eL _; split=> [rR _\|_ z1L _]; [by ring \| split; [by ring \| move=> _; smt(expD... | ambient / ambient_logic, 1 goal, goal 613 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-64 | +24:48 | 6.8 s | 150 ms | [turn_063.json](./views/Tree_0_0/turn_063.json) · [inline read](./views/Tree_0_0/followups/turn_063.md) | probe move=> &2 r1 _ eL _; split=> [rR _\|_ z1L _]; [by ring \| split; [by ring \| move=> _]] | ambient / ambient_logic, 1 goal, goal 613 chars | accepted probe |  |
| T0.0-65 | +25:03 | 15.2 s | 787 ms | [turn_064.json](./views/Tree_0_0/turn_064.json) · [inline read](./views/Tree_0_0/followups/turn_064.md) | lookup expM | ambient / ambient_logic, 1 goal, goal 613 chars | lookup result |  |
| T0.0-66 | +25:28 | 23.9 s | 149 ms | [turn_065.json](./views/Tree_0_0/turn_065.json) · [inline read](./views/Tree_0_0/followups/turn_065.md) | probe move=> &2 r1 _ eL _; split=> [rR _\|_ z1L _]; [by ring \| split; [by ring \| move=> _; rewrite -... | ambient / ambient_logic, 1 goal, goal 613 chars | accepted probe |  |
| T0.0-67 | +25:32 | 3.9 s | 150 ms | [turn_066.json](./views/Tree_0_0/turn_066.json) · [inline read](./views/Tree_0_0/followups/turn_066.md) | commit move=> &2 r1 _ eL _; split=> [rR _\|_ z1L _]; [by ring \| split; [by ring \| move=> _; rewrite -... | ambient / ambient_logic, 1 goal, goal 613 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:05 |  |  | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect call_site_options | probability / pr / probability, 1 goal, goal 324 chars | read-only inspect |  |
| T0.1-2 | +00:36 | 31.3 s | 1.7 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 324 chars | read-only inspect |  |
| T0.1-3 | +00:46 | 7.7 s | 1.3 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | probe byequiv (_: ={glob D} ==> ={res}) | probability / pr / probability, 1 goal, goal 324 chars | accepted probe |  |
| T0.1-4 | +00:51 | 3.9 s | 113 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit byequiv (_: ={glob D} ==> ={res}) | probability / pr / probability, 1 goal, goal 324 chars | accepted commit |  |
| T0.1-5 | +01:59 | 68.2 s | 806 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | probe proc | equiv / prhl_module / relational_program, 3 goals, goal 372 chars | accepted probe |  |
| T0.1-6 | +02:13 | 13.1 s | 903 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit proc | equiv / prhl_module / relational_program, 3 goals, goal 372 chars | accepted commit |  |
| T0.1-7 | +02:24 | 9.9 s | 134 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | probe call (_: ={glob D}) | pRHL / call_site / seq_cut, 3 goals, goal 1941 chars | rejected probe: The module D can write D (add restriction D to D, or D to D) |  |
| T0.1-8 | +02:37 | 12.8 s | 186 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | probe call true | pRHL / call_site / seq_cut, 3 goals, goal 1941 chars | accepted probe |  |
| T0.1-9 | +02:42 | 4.8 s | 153 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit call true | pRHL / call_site / seq_cut, 3 goals, goal 1941 chars | accepted commit |  |
| T0.1-10 | +02:49 | 7.2 s | 848 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | probe inline * | pRHL / call_site / relational_program, 3 goals, goal 2089 chars | accepted probe |  |
| T0.1-11 | +02:54 | 3.8 s | 2.2 s | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit inline * | pRHL / call_site / relational_program, 3 goals, goal 2089 chars | accepted commit |  |
| T0.1-12 | +04:19 | 82.8 s | 178 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | probe rcondf{1} 28 | pRHL / procedure_body / seq_cut, 3 goals, goal 6343 chars | accepted probe |  |
| T0.1-13 | +04:26 | 6.9 s | 141 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit rcondf{1} 28 | pRHL / procedure_body / seq_cut, 3 goals, goal 6343 chars | accepted commit |  |
| T0.1-14 | +04:37 | 11.2 s | 830 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | probe auto | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | accepted probe |  |
| T0.1-15 | +04:56 | 18.3 s | 3.7 s | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | probe auto; smt(expD expM) | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | rejected probe: cannot prove goal (strict) |  |
| T0.1-16 | +05:27 | 26.6 s | 386 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | probe auto; smt(expN expD exp0 mulVc mulcA mulc1 mulcV mulcC) | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | accepted probe |  |
| T0.1-17 | +05:32 | 5.2 s | 3.8 s | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit auto; smt(expN expD exp0 mulVc mulcA mulc1 mulcV mulcC) | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | accepted commit |  |
| T0.1-18 | +07:30 | 113.9 s | 103 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | inspect tactic_forms | pRHL / procedure_body / seq_cut, 3 goals, goal 4008 chars | read-only inspect |  |
| T0.1-19 | +08:20 | 49.8 s | 226 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | probe rcondt{1} 25 | pRHL / procedure_body / seq_cut, 3 goals, goal 4008 chars | accepted probe |  |
| T0.1-20 | +08:26 | 5.8 s | 153 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit rcondt{1} 25 | pRHL / procedure_body / seq_cut, 3 goals, goal 4008 chars | accepted commit |  |
| T0.1-21 | +08:30 | 4.1 s | 3.9 s | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | commit auto; smt(expN expD exp0 mulVc mulcA mulc1 mulcV mulcC) | hoare / procedure_body / procedure_frontier, 4 goals, goal 257 chars | accepted commit |  |
| T0.1-22 | +08:42 | 7.8 s | 183 ms | [turn_021.json](./views/Tree_0_1/turn_021.json) · [inline read](./views/Tree_0_1/followups/turn_021.md) | probe swap{2} 12 -5 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted probe |  |
| T0.1-23 | +10:12 | 89.8 s | 196 ms | [turn_022.json](./views/Tree_0_1/turn_022.json) · [inline read](./views/Tree_0_1/followups/turn_022.md) | probe swap{1} 15 -5 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted probe |  |
| T0.1-24 | +10:17 | 5.1 s | 3.9 s | [turn_023.json](./views/Tree_0_1/turn_023.json) · [inline read](./views/Tree_0_1/followups/turn_023.md) | commit swap{1} 15 -5 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted commit |  |
| T0.1-25 | +10:27 | 5.8 s | 196 ms | [turn_024.json](./views/Tree_0_1/turn_024.json) · [inline read](./views/Tree_0_1/followups/turn_024.md) | probe wp | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted probe |  |
| T0.1-26 | +11:51 | 84 s |  | [turn_025.json](./views/Tree_0_1/turn_025.json) · [inline read](./views/Tree_0_1/followups/turn_025.md) | undo_last_step | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | undo result |  |
| T0.1-27 | +12:22 | 30.8 s | 221 ms | [turn_026.json](./views/Tree_0_1/turn_026.json) · [inline read](./views/Tree_0_1/followups/turn_026.md) | probe swap{1} 10 1 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted probe |  |
| T0.1-28 | +12:27 | 5.3 s | 3.7 s | [turn_027.json](./views/Tree_0_1/turn_027.json) · [inline read](./views/Tree_0_1/followups/turn_027.md) | commit swap{1} 10 1 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted commit |  |
| T0.1-29 | +12:36 | 4.8 s | 199 ms | [turn_028.json](./views/Tree_0_1/turn_028.json) · [inline read](./views/Tree_0_1/followups/turn_028.md) | probe swap{2} 12 -5 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted probe |  |
| T0.1-30 | +14:13 | 97.2 s | 3.8 s | [turn_029.json](./views/Tree_0_1/turn_029.json) · [inline read](./views/Tree_0_1/followups/turn_029.md) | commit swap{2} 12 -5 | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted commit |  |
| T0.1-31 | +15:18 | 60.8 s | 185 ms | [turn_030.json](./views/Tree_0_1/turn_030.json) · [inline read](./views/Tree_0_1/followups/turn_030.md) | probe wp | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted probe |  |
| T0.1-32 | +15:30 | 12.5 s | 3.5 s | [turn_031.json](./views/Tree_0_1/turn_031.json) · [inline read](./views/Tree_0_1/followups/turn_031.md) | commit wp | pRHL / procedure_body / seq_cut, 3 goals, goal 3343 chars | accepted commit |  |
| T0.1-33 | +16:42 | 67.8 s | 184 ms | [turn_032.json](./views/Tree_0_1/turn_032.json) · [inline read](./views/Tree_0_1/followups/turn_032.md) | inspect tactic_forms | pRHL / procedure_body / seq_cut, 3 goals, goal 2220 chars | read-only inspect |  |
| T0.1-34 | +17:16 | 33.8 s | 195 ms | [turn_033.json](./views/Tree_0_1/turn_033.json) · [inline read](./views/Tree_0_1/followups/turn_033.md) | probe rnd (fun z => z - e{1} * w{1}) (fun r => r + e{1} * w{1}) | pRHL / procedure_body / seq_cut, 3 goals, goal 2220 chars | accepted probe |  |
| T0.1-35 | +17:30 | 13.6 s | 1.4 s | [turn_034.json](./views/Tree_0_1/turn_034.json) · [inline read](./views/Tree_0_1/followups/turn_034.md) | commit rnd (fun z => z - e{1} * w{1}) (fun r => r + e{1} * w{1}) | pRHL / procedure_body / seq_cut, 3 goals, goal 2220 chars | accepted commit |  |
| T0.1-36 | +17:53 | 21.8 s | 216 ms | [turn_035.json](./views/Tree_0_1/turn_035.json) · [inline read](./views/Tree_0_1/followups/turn_035.md) | probe rnd | pRHL / procedure_body / seq_cut, 3 goals, goal 2376 chars | accepted probe |  |
| T0.1-37 | +18:09 | 15.7 s | 1.3 s | [turn_036.json](./views/Tree_0_1/turn_036.json) · [inline read](./views/Tree_0_1/followups/turn_036.md) | commit rnd | pRHL / procedure_body / seq_cut, 3 goals, goal 2376 chars | accepted commit |  |
| T0.1-38 | +18:34 | 23.8 s | 218 ms | [turn_037.json](./views/Tree_0_1/turn_037.json) · [inline read](./views/Tree_0_1/followups/turn_037.md) | probe wp | pRHL / procedure_body / seq_cut, 3 goals, goal 2426 chars | accepted probe |  |
| T0.1-39 | +18:54 | 19.6 s | 1.4 s | [turn_038.json](./views/Tree_0_1/turn_038.json) · [inline read](./views/Tree_0_1/followups/turn_038.md) | commit wp | pRHL / procedure_body / seq_cut, 3 goals, goal 2426 chars | accepted commit |  |
| T0.1-40 | +19:03 | 7.8 s | 174 ms | [turn_039.json](./views/Tree_0_1/turn_039.json) · [inline read](./views/Tree_0_1/followups/turn_039.md) | probe rnd{1} | pRHL / procedure_body / seq_cut, 3 goals, goal 3223 chars | accepted probe |  |
| T0.1-41 | +19:58 | 54.7 s | 1.3 s | [turn_040.json](./views/Tree_0_1/turn_040.json) · [inline read](./views/Tree_0_1/followups/turn_040.md) | commit rnd{1} | pRHL / procedure_body / seq_cut, 3 goals, goal 3223 chars | accepted commit |  |
| T0.1-42 | +20:11 | 11.6 s | 3.4 s | [turn_041.json](./views/Tree_0_1/turn_041.json) · [inline read](./views/Tree_0_1/followups/turn_041.md) | probe auto; smt(expN expD exp0 mulVc mulcA mulc1 mulcV mulcC) | pRHL / procedure_body / seq_cut, 3 goals, goal 3329 chars | rejected probe: cannot prove goal (strict) |  |
| T0.1-43 | +20:20 | 5.7 s | 257 ms | [turn_042.json](./views/Tree_0_1/turn_042.json) · [inline read](./views/Tree_0_1/followups/turn_042.md) | probe auto | pRHL / procedure_body / seq_cut, 3 goals, goal 3329 chars | accepted probe |  |
| T0.1-44 | +21:21 | 60.8 s | 196 ms | [turn_043.json](./views/Tree_0_1/turn_043.json) · [inline read](./views/Tree_0_1/followups/turn_043.md) | commit auto | pRHL / procedure_body / seq_cut, 3 goals, goal 3329 chars | accepted commit |  |
| T0.1-45 | +22:33 | 72.4 s | 4.6 s | [turn_044.json](./views/Tree_0_1/turn_044.json) · [inline read](./views/Tree_0_1/followups/turn_044.md) | probe smt(expD expM expN exp0 dt_ll dt_fu) | ambient / ambient_logic / relational_program, 3 goals, goal 3060 chars | rejected probe: cannot prove goal (strict) |  |
| T0.1-46 | +23:29 | 50.8 s | 154 ms | [turn_045.json](./views/Tree_0_1/turn_045.json) · [inline read](./views/Tree_0_1/followups/turn_045.md) | probe smt(expD expM expN exp0 mulrC addrK subrK mulr0 addr0 dt_ll dt_fu) | ambient / ambient_logic / relational_program, 3 goals, goal 3060 chars | rejected probe: cannot find lemma `mulrC' |  |
| T0.1-47 | +24:14 | 45.3 s | 3.7 s | [turn_046.json](./views/Tree_0_1/turn_046.json) · [inline read](./views/Tree_0_1/followups/turn_046.md) | probe move=> &1 &2 eqD; rewrite eqD /=; smt(expD expM expN exp0 dt_ll dt_fu) | ambient / ambient_logic / relational_program, 3 goals, goal 3060 chars | rejected probe: cannot prove goal (strict) |  |
| T0.1-48 | +24:53 | 35.4 s | 553 ms | [turn_047.json](./views/Tree_0_1/turn_047.json) · [inline read](./views/Tree_0_1/followups/turn_047.md) | probe smt(expD expM expN exp0 GP.ZModE.ZModpRing.mulrC GP.ZModE.ZModpRing.addrK GP.ZModE.ZModpRing.subrK GP.ZModE.ZModpRing.mulr0 GP.ZModE.ZModpRing.addr0 dt_ll dt_fu) | ambient / ambient_logic / relational_program, 3 goals, goal 3060 chars | accepted probe |  |
| T0.1-49 | +25:01 | 7.5 s | 532 ms | [turn_048.json](./views/Tree_0_1/turn_048.json) · [inline read](./views/Tree_0_1/followups/turn_048.md) | commit smt(expD expM expN exp0 GP.ZModE.ZModpRing.mulrC GP.ZModE.ZModpRing.addrK GP.ZModE.ZModpRing.subrK GP.ZModE.ZModpRing.mulr0 GP.ZModE.ZModpRing.addr0 dt_ll dt_fu) | ambient / ambient_logic / relational_program, 3 goals, goal 3060 chars | accepted commit |  |
| T0.1-50 | +25:08 | 5.8 s | 185 ms | [turn_049.json](./views/Tree_0_1/turn_049.json) · [inline read](./views/Tree_0_1/followups/turn_049.md) | commit done | ambient / ambient_logic, 2 goals, goal 198 chars | accepted commit |  |
| T0.1-51 | +25:19 | 10.8 s | 169 ms | [turn_050.json](./views/Tree_0_1/turn_050.json) · [inline read](./views/Tree_0_1/followups/turn_050.md) | commit smt() | ambient / ambient_logic / relational_program, 1 goal, goal 208 chars | accepted commit |  |
| T0.1-52 | +25:34 | 14.8 s | 193 ms | [turn_051.json](./views/Tree_0_1/turn_051.json) · [inline read](./views/Tree_0_1/followups/turn_051.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-53 | +25:36 | 2 s |  | [turn_052.json](./views/Tree_0_1/turn_052.json) · [inline read](./views/Tree_0_1/followups/turn_052.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
