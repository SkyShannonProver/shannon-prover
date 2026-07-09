# Agent-View Timeline — `random_eq`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1654_random_eq |
| lemma | `random_eq` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 14 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc; inline *.
  unroll{1} 5.
  rcondt{1} 5.
  by auto=> /=; smt(size_ge0).
  wp; while (c0{1} = c{2} /\ i{1} = i{2} + 1 /\ p0{1} = p{2}); auto=> /#.
  qed.
```

### `Tree_0_1` — incomplete — 7 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  inline *.
  unroll{1} 5.
  rcondt{1} 5.
  by auto=> /=; smt(size_ge0).
  wp; while (c0{1} = c{2} /\ i{1} = i{2} + 1 /\ p0{1} = p{2}).
  by auto=> /#.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1654_random_eq

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_random_eq/r01/2026-06-11_1654_random_eq/iteration_1`

t=0: `2026-06-11T23:56:23.700000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:09 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 209 chars | accepted commit |  |
| T0.0-2 | +00:17 | [6.8 s](./views/Tree_0_0/thinking/turn_002.md) | 198 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit unroll{1} 5 | pRHL / procedure_body / relational_program, 1 goal, goal 1417 chars | accepted commit |  |
| T0.0-3 | +00:27 | [9.8 s](./views/Tree_0_0/thinking/turn_003.md) | 159 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit rcondt{1} 5 | pRHL / procedure_body / relational_program, 1 goal, goal 1747 chars | accepted commit |  |
| T0.0-4 | +00:34 | [6.9 s](./views/Tree_0_0/thinking/turn_004.md) | 3.1 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit by auto=> /=; smt(size_ge0) | hoare / procedure_body / procedure_frontier, 2 goals, goal 220 chars | accepted commit |  |
| T0.0-5 | +01:01 | [23.7 s](./views/Tree_0_0/thinking/turn_005.md) | 256 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit wp; while (c0{1} = c{2} /\ i{1} = i{2} + 1 /\ p0{1} = p{2}); auto=> /# | pRHL / procedure_body / seq_cut, 1 goal, goal 1615 chars | accepted commit |  |
| T0.0-6 | +01:06 | [4.8 s](./views/Tree_0_0/thinking/turn_006.md) | 160 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-7 | +01:13 | 7 s |  | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 209 chars | accepted commit |  |
| T0.1-2 | +00:08 | [6.8 s](./views/Tree_0_1/thinking/turn_002.md) | 204 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 900 chars | accepted commit |  |
| T0.1-3 | +00:15 | [6.8 s](./views/Tree_0_1/thinking/turn_003.md) | 239 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit unroll{1} 5 | pRHL / procedure_body / relational_program, 1 goal, goal 1417 chars | accepted commit |  |
| T0.1-4 | +00:24 | [8.8 s](./views/Tree_0_1/thinking/turn_004.md) | 163 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit rcondt{1} 5 | pRHL / procedure_body / relational_program, 1 goal, goal 1747 chars | accepted commit |  |
| T0.1-5 | +00:33 | [8.9 s](./views/Tree_0_1/thinking/turn_005.md) | 3.1 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit by auto=> /=; smt(size_ge0) | hoare / procedure_body / procedure_frontier, 2 goals, goal 220 chars | accepted commit |  |
| T0.1-6 | +00:52 | [16.1 s](./views/Tree_0_1/thinking/turn_006.md) | 2.9 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp; while (c0{1} = c{2} /\ i{1} = i{2} + 1 /\ p0{1} = p{2}) | pRHL / procedure_body / seq_cut, 1 goal, goal 1615 chars | accepted commit |  |
| T0.1-7 | +01:01 | [5.7 s](./views/Tree_0_1/thinking/turn_007.md) | 3.3 s | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit by auto=> /# | pRHL / procedure_body / seq_cut, 2 goals, goal 853 chars | accepted commit |  |
