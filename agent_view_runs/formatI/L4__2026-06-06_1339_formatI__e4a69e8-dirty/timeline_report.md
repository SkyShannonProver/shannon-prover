# Agent-View Timeline — `formatI`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1339_formatI |
| lemma | `formatI` |
| source file | `eval/examples/br93.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 6 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  by move=> h; rewrite -parseK -parseK h.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1339_formatI

Run dir: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d3_formatI/r01/2026-06-06_1339_formatI/iteration_1`

t=0: `2026-06-06T20:39:55.300000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.7 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe by move=> h; rewrite -(parseK r p) -(parseK r' p') h | ambient / ambient_logic, 1 goal, goal 187 chars | rejected probe: too many arguments |  |
| T0.0-2 | +00:08 | 6.2 s | 784 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | lookup parseK | ambient / ambient_logic, 1 goal, goal 187 chars | lookup result |  |
| T0.0-3 | +00:22 | 12.9 s | 126 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | probe by move=> h; rewrite -(parseK r p) -(parseK r' p'); rewrite h | ambient / ambient_logic, 1 goal, goal 187 chars | rejected probe: too many arguments |  |
| T0.0-4 | +00:27 | 4.9 s | 133 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | probe by move=> h; rewrite -parseK -parseK h | ambient / ambient_logic, 1 goal, goal 187 chars | accepted probe |  |
| T0.0-5 | +00:31 | [3.8 s](./views/Tree_0_0/thinking/turn_005.md) | 151 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit by move=> h; rewrite -parseK -parseK h | ambient / ambient_logic, 1 goal, goal 187 chars | accepted commit |  |
| T0.0-6 | +00:36 | [4.8 s](./views/Tree_0_0/thinking/turn_006.md) | 160 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
