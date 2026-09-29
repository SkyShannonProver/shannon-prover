# Agent-View Timeline — `formatI`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1337_formatI |
| lemma | `formatI` |
| source file | `eval/examples/br93.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 8 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  move=> h.
  have h1 := parseK r p.
  rewrite h parseK in h1.
  by rewrite h1.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1337_formatI

Run dir: `artifacts/eval_suite/wave1_recover_both/l1_goal_projection/d3_formatI/r01/2026-06-06_1337_formatI/iteration_1`

t=0: `2026-06-06T20:37:44.021000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 979 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> h | ambient / ambient_logic, 1 goal, goal 187 chars | accepted commit |  |
| T0.0-2 | +00:06 | [5.1 s](./views/Tree_0_0/thinking/turn_002.md) | 853 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit rewrite -(parseK r p) -(parseK r' p') h | ambient / ambient_logic, 1 goal, goal 200 chars | rejected commit: proof state unchanged |  |
| T0.0-3 | +00:32 | [25.1 s](./views/Tree_0_0/thinking/turn_003.md) | 866 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit rewrite -(parseK r p) -(parseK r' p') | ambient / ambient_logic, 1 goal, goal 200 chars | rejected commit: proof state unchanged |  |
| T0.0-4 | +01:20 | [46.9 s](./views/Tree_0_0/thinking/turn_004.md) | 145 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit have h1 := parseK r p | ambient / ambient_logic, 1 goal, goal 200 chars | accepted commit |  |
| T0.0-5 | +01:24 | [3.8 s](./views/Tree_0_0/thinking/turn_005.md) | 152 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit rewrite h parseK in h1 | ambient / ambient_logic, 1 goal, goal 228 chars | accepted commit |  |
| T0.0-6 | +01:30 | [5.8 s](./views/Tree_0_0/thinking/turn_006.md) | 156 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit by rewrite h1 | ambient / ambient_logic, 1 goal, goal 222 chars | accepted commit |  |
| T0.0-7 | +01:34 | [3.8 s](./views/Tree_0_0/thinking/turn_007.md) | 153 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-8 | +01:37 | 3 s |  | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
