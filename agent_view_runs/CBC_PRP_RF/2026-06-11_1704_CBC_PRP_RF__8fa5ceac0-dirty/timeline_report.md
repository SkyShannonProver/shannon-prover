# Agent-View Timeline — `CBC_PRP_RF`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1704_CBC_PRP_RF |
| lemma | `CBC_PRP_RF` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 5 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  rewrite (refactor_abstract PRP &m) (refactor_abstract PRFi &m).
  smt().
  qed.
```

### `Tree_0_1` — incomplete — 1 tactic(s) committed, not closed

```easycrypt
proof.
  rewrite (refactor_abstract PRP &m) (refactor_abstract PRFi &m).
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1704_CBC_PRP_RF

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_CBC_PRP_RF/r01/2026-06-11_1704_CBC_PRP_RF/iteration_1`

t=0: `2026-06-12T00:05:14.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit rewrite (refactor_abstract PRP &m) (refactor_abstract PRFi &m) | probability / pr / probability, 1 goal, goal 570 chars | accepted commit |  |
| T0.0-2 | +00:08 | [6.8 s](./views/Tree_0_0/thinking/turn_002.md) | 164 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit smt() | probability / pr / probability, 1 goal, goal 554 chars | accepted commit |  |
| T0.0-3 | +00:17 | [8.9 s](./views/Tree_0_0/thinking/turn_003.md) | 148 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-4 | +00:25 | 7 s |  | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:08 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit rewrite (refactor_abstract PRP &m) (refactor_abstract PRFi &m) | probability / pr / probability, 1 goal, goal 570 chars | accepted commit |  |
