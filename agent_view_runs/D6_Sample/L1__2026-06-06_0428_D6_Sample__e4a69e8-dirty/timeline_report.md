# Agent-View Timeline — `D6_Sample`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_0428_D6_Sample |
| lemma | `D6_Sample` |
| source file | `eval/examples/Dice4_6.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 7 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  sp.
  while (={r} /\ 1 <= r{1} <= 6).
  auto=> />; smt(supp_dinter).
  skip=> /> /#.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_0428_D6_Sample

Run dir: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d0_d6_sample/r01/2026-06-06_0428_D6_Sample/iteration_1`

t=0: `2026-06-06T11:29:41.032000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 968 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 188 chars | accepted commit |  |
| T0.0-2 | +00:07 | [5.8 s](./views/Tree_0_0/thinking/turn_002.md) | 151 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit sp | pRHL / procedure_body / relational_program, 1 goal, goal 586 chars | accepted commit |  |
| T0.0-3 | +00:13 | [5.8 s](./views/Tree_0_0/thinking/turn_003.md) | 168 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit while (={r} /\ 1 <= r{1} <= 6) | pRHL / procedure_body / relational_program, 1 goal, goal 418 chars | accepted commit |  |
| T0.0-4 | +00:35 | [21.7 s](./views/Tree_0_0/thinking/turn_004.md) | 328 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit auto=> />; smt(supp_dinter) | pRHL / procedure_body / relational_program, 2 goals, goal 400 chars | accepted commit |  |
| T0.0-5 | +00:53 | [17.9 s](./views/Tree_0_0/thinking/turn_005.md) | 127 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit skip=> /> /# | pRHL / prhl_module / relational_program, 1 goal, goal 402 chars | accepted commit |  |
| T0.0-6 | +00:55 | [1.9 s](./views/Tree_0_0/thinking/turn_006.md) | 137 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-7 | +00:59 | 4 s |  | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
