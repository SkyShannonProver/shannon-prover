# Agent-View Timeline — `pedersen_correctness`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_0538_pedersen_correctness |
| lemma | `pedersen_correctness` |
| source file | `eval/examples/Pedersen.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 4 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc; inline *; auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_0538_pedersen_correctness

Run dir: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d2_pedersen/r01/2026-06-06_0538_pedersen_correctness/iteration_1`

t=0: `2026-06-06T12:39:09+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) |  | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect call_site_options | hoare / procedure_entry / procedure_frontier, 1 goal, goal 166 chars | read-only inspect |  |
| T0.0-2 | +00:04 | [4.4 s](./views/Tree_0_0/thinking/turn_002.md) | 1.6 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | probe proc; inline *; auto | hoare / procedure_entry / procedure_frontier, 1 goal, goal 166 chars | accepted probe |  |
| T0.0-3 | +00:27 | [20.9 s](./views/Tree_0_0/thinking/turn_003.md) | 105 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit proc; inline *; auto | hoare / procedure_entry / procedure_frontier, 1 goal, goal 166 chars | accepted commit |  |
| T0.0-4 | +00:30 | [2.9 s](./views/Tree_0_0/thinking/turn_004.md) | 114 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
