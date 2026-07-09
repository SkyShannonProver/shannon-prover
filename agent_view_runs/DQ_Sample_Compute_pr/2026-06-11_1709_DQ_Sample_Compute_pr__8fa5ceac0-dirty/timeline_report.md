# Agent-View Timeline — `DQ_Sample_Compute_pr`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1709_DQ_Sample_Compute_pr |
| lemma | `DQ_Sample_Compute_pr` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 11 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv (: ={glob A} ==> DoubleQuery.bad{1} = Compute.bad{2})=> //.
  proc.
  call (_: ={bad,qs}(DoubleQuery,Compute)).
  by conseq DQ_Sample_Compute_eq.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  byequiv (: ={glob A} ==> ={bad}(DoubleQuery,Compute))=> //.
  proc.
  call (_: ={bad,qs}(DoubleQuery,Compute)).
  by conseq DQ_Sample_Compute_eq.
  by inline *; auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1709_DQ_Sample_Compute_pr

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_DQ_Sample_Compute_pr/r01/2026-06-11_1709_DQ_Sample_Compute_pr/iteration_1`

t=0: `2026-06-12T00:10:21.700000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:01 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.1 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv (: ={glob A} ==> DoubleQuery.bad{1} = Compute.bad{2})=> // | probability / pr / probability, 1 goal, goal 266 chars | accepted commit |  |
| T0.0-2 | +00:07 | [4.8 s](./views/Tree_0_0/thinking/turn_002.md) | 1.2 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 370 chars | accepted commit |  |
| T0.0-3 | +00:14 | [5.8 s](./views/Tree_0_0/thinking/turn_003.md) | 177 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit call (_: ={bad,qs}(DoubleQuery,Compute)) | pRHL / call_site / relational_program, 1 goal, goal 517 chars | accepted commit |  |
| T0.0-4 | +00:22 | [7.8 s](./views/Tree_0_0/thinking/turn_004.md) | 211 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit by conseq DQ_Sample_Compute_eq | equiv / prhl_module / relational_program, 2 goals, goal 407 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit byequiv (: ={glob A} ==> ={bad}(DoubleQuery,Compute))=> // | probability / pr / probability, 1 goal, goal 266 chars | accepted commit |  |
| T0.1-2 | +00:05 | 3.9 s | 1.1 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 370 chars | accepted commit |  |
| T0.1-3 | +00:11 | [4.8 s](./views/Tree_0_1/thinking/turn_003.md) | 169 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit call (_: ={bad,qs}(DoubleQuery,Compute)) | pRHL / call_site / relational_program, 1 goal, goal 517 chars | accepted commit |  |
| T0.1-4 | +00:18 | [6.8 s](./views/Tree_0_1/thinking/turn_004.md) | 195 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit by conseq DQ_Sample_Compute_eq | equiv / prhl_module / relational_program, 2 goals, goal 407 chars | accepted commit |  |
| T0.1-5 | +00:23 | [4.9 s](./views/Tree_0_1/thinking/turn_005.md) | 143 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit by inline *; auto | pRHL / procedure_body / relational_program, 1 goal, goal 649 chars | accepted commit |  |
| T0.1-6 | +00:27 | [3.8 s](./views/Tree_0_1/thinking/turn_006.md) | 158 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-7 | +00:31 | 4 s |  | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
