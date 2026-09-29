# Agent-View Timeline — `andbDl`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1742_andbDl |
| lemma | `andbDl` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
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

### `Tree_0_0` — incomplete — 1 tactic(s) committed, not closed

```easycrypt
proof.
  by move=> b1 b2 b3; apply/blockP=> i ge0_gti_n; rewrite !andbE // !xorbE // !andbE // andwDl.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  rewrite /left_distributive.
  by move=> x y z; apply/blockP=> i ge0_gti_n; rewrite !(andbE, xorbE) // andwDl.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1742_andbDl

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_andbDl/r01/2026-06-11_1742_andbDl/iteration_1`

t=0: `2026-06-12T00:43:05.400000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit by move=> [] [] [] | ambient / ambient_logic, 1 goal, goal 138 chars | rejected commit: [error] invalid intro-pattern: nothing to eliminate |  |
| T0.1-2 | +00:12 | 9.8 s | 155 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit rewrite /left_distributive | ambient / ambient_logic, 1 goal, goal 138 chars | accepted commit |  |
| T0.1-3 | +00:53 | [40.7 s](./views/Tree_0_1/thinking/turn_003.md) | 287 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit by move=> x y z; apply/blockP=> i ge0_gti_n; rewrite !(andbE, xorbE) // andwDl | ambient / ambient_logic, 1 goal, goal 185 chars | accepted commit |  |
| T0.1-4 | +01:00 | [6.9 s](./views/Tree_0_1/thinking/turn_004.md) | 141 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-5 | +01:08 | 7 s |  | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
