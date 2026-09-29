# Agent-View Timeline — `CPA_direct_eq`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1532_CPA_direct_eq |
| lemma | `CPA_direct_eq` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 15 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  move=> P_init_eq P_f_eq &m A.
  byequiv (_: ={glob A} ==> ={res})=> //.
  proc.
  call (_: I (glob P){1} (glob P'){2}).
  by conseq (CBC_Oracle_enc_eq P P' I P_f_eq).
  call P_init_eq.
  by auto.
  qed.
```

### `Tree_0_1` — incomplete — 6 tactic(s) committed, not closed

```easycrypt
proof.
  move=> P_init_eq P_f_eq &m A.
  byequiv (_: ={glob A} ==> ={res})=> //.
  proc.
  call (_: I (glob P){1} (glob P'){2}).
  exact (CBC_Oracle_enc_eq P P' I P_f_eq).
  by call P_init_eq.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1532_CPA_direct_eq

Run dir: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_CPA_direct_eq/r01/2026-06-11_1532_CPA_direct_eq/iteration_1`

t=0: `2026-06-11T22:33:12.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> P_init_eq P_f_eq &m A | probability / pr / probability, 1 goal, goal 543 chars | accepted commit |  |
| T0.0-2 | +00:06 | [4.8 s](./views/Tree_0_0/thinking/turn_002.md) | 189 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit byequiv (_: ={glob A} ==> ={res})=> // | probability / pr / probability, 1 goal, goal 573 chars | accepted commit |  |
| T0.0-3 | +00:10 | 3.8 s | 212 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 648 chars | accepted commit |  |
| T0.0-4 | +00:15 | [4.8 s](./views/Tree_0_0/thinking/turn_004.md) | 195 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit call I | pRHL / call_site / relational_program, 1 goal, goal 718 chars | accepted commit |  |
| T0.0-5 | +00:23 | [7.8 s](./views/Tree_0_0/thinking/turn_005.md) | 203 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit by conseq (CBC_Oracle_enc_eq P P' I P_f_eq) | equiv / prhl_module / relational_program, 2 goals, goal 624 chars | accepted commit |  |
| T0.0-6 | +00:32 | [8.8 s](./views/Tree_0_0/thinking/turn_006.md) | 196 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit call P_init_eq | pRHL / procedure_body / relational_program, 1 goal, goal 862 chars | accepted commit |  |
| T0.0-7 | +00:40 | [7.9 s](./views/Tree_0_0/thinking/turn_007.md) | 143 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit by auto | pRHL / verification_residue / relational_program, 1 goal, goal 887 chars | accepted commit |  |
| T0.0-8 | +00:46 | [5.9 s](./views/Tree_0_0/thinking/turn_008.md) | 139 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-9 | +00:52 | 5 s |  | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:11 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit move=> P_init_eq P_f_eq &m A | probability / pr / probability, 1 goal, goal 543 chars | accepted commit |  |
| T0.1-2 | +00:17 | 4.8 s | 187 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit byequiv (_: ={glob A} ==> ={res})=> // | probability / pr / probability, 1 goal, goal 573 chars | accepted commit |  |
| T0.1-3 | +00:23 | 5.8 s | 218 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 648 chars | accepted commit |  |
| T0.1-4 | +00:29 | [5.8 s](./views/Tree_0_1/thinking/turn_004.md) | 214 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit call I | pRHL / call_site / relational_program, 1 goal, goal 718 chars | accepted commit |  |
| T0.1-5 | +00:36 | [6.8 s](./views/Tree_0_1/thinking/turn_005.md) | 240 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit exact (CBC_Oracle_enc_eq P P' I P_f_eq) | equiv / prhl_module / relational_program, 2 goals, goal 624 chars | accepted commit |  |
| T0.1-6 | +00:45 | [8.8 s](./views/Tree_0_1/thinking/turn_006.md) | 152 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit by call P_init_eq | pRHL / procedure_body / relational_program, 1 goal, goal 862 chars | accepted commit |  |
