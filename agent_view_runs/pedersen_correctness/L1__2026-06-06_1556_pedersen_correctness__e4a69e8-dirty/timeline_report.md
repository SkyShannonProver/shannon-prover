# Agent-View Timeline — `pedersen_correctness`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1556_pedersen_correctness |
| lemma | `pedersen_correctness` |
| source file | `eval/examples/Pedersen.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 9 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  inline *; auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1556_pedersen_correctness

Run dir: `artifacts/eval_suite/wave1_rerun_l1/l1_goal_projection/d2_pedersen/r01/2026-06-06_1556_pedersen_correctness/iteration_1`

t=0: `2026-06-06T22:57:10.059000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 941 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | hoare / procedure_entry / procedure_frontier, 1 goal, goal 166 chars | accepted commit |  |
| T0.0-2 | +00:04 | [2.9 s](./views/Tree_0_0/thinking/turn_002.md) | 132 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit inline * | hoare / procedure_body / procedure_frontier, 1 goal, goal 355 chars | rejected commit: manager reported rejection |  |
| T0.0-3 | +00:14 | [10.2 s](./views/Tree_0_0/thinking/turn_003.md) | 822 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit inline Pedersen.gen Pedersen.commit Pedersen.verify | hoare / procedure_body / procedure_frontier, 1 goal, goal 355 chars | rejected commit: manager reported rejection |  |
| T0.0-4 | +00:34 | [19.2 s](./views/Tree_0_0/thinking/turn_004.md) | 823 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit inline | hoare / procedure_body / procedure_frontier, 1 goal, goal 355 chars | rejected commit: manager reported rejection |  |
| T0.0-5 | +01:40 | [64.9 s](./views/Tree_0_0/thinking/turn_005.md) | 1.1 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit sp | hoare / procedure_body / procedure_frontier, 1 goal, goal 355 chars | rejected commit: manager reported rejection |  |
| T0.0-6 | +03:13 | [92.2 s](./views/Tree_0_0/thinking/turn_006.md) | 825 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit inline * | hoare / procedure_body / procedure_frontier, 1 goal, goal 355 chars | rejected commit: manager reported rejection |  |
| T0.0-7 | +03:23 | [9.2 s](./views/Tree_0_0/thinking/turn_007.md) | 830 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit inline *; auto | hoare / procedure_body / procedure_frontier, 1 goal, goal 355 chars | accepted commit |  |
| T0.0-8 | +03:30 | [5.9 s](./views/Tree_0_0/thinking/turn_008.md) | 129 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-9 | +03:34 | 4 s |  | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
