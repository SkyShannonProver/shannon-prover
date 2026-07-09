# Agent-View Timeline — `cbc_correct`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1849_cbc_correct |
| lemma | `cbc_correct` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 13 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 3 tactic(s) committed, not closed

```easycrypt
proof.
  move=> hcancel.
  elim: p st => //= pi p ih st.
  rewrite hcancel ih.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  move=> kK; elim: p st => //= pi p ih st.
  rewrite kK ih; split=> //; rewrite xorbC xorbA xorbK xorbC xorb0.
  done.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1849_cbc_correct

Run dir: `artifacts/eval_suite/tree_expand_ig_multi/l4_checked_action_surface/cbc_correct/r01/2026-06-10_1849_cbc_correct/iteration_1`

t=0: `2026-06-11T01:50:04.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:03 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> hcancel | ambient / ambient_logic, 1 goal, goal 260 chars | accepted commit |  |
| T0.0-2 | +00:10 | [4.8 s](./views/Tree_0_0/thinking/turn_002.md) | 1.2 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | probe elim: p st => //= pi p ih st | ambient / ambient_logic, 1 goal, goal 279 chars | accepted probe |  |
| T0.0-3 | +00:20 | [8.8 s](./views/Tree_0_0/thinking/turn_003.md) | 185 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit elim: p st => //= pi p ih st | ambient / ambient_logic, 1 goal, goal 279 chars | accepted commit |  |
| T0.0-4 | +00:25 | [4.7 s](./views/Tree_0_0/thinking/turn_004.md) | 1.3 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | probe rewrite hcancel ih | ambient / ambient_logic, 1 goal, goal 417 chars | accepted probe |  |
| T0.0-5 | +00:32 | [5.9 s](./views/Tree_0_0/thinking/turn_005.md) | 145 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit rewrite hcancel ih | ambient / ambient_logic, 1 goal, goal 417 chars | accepted commit |  |
| T0.0-6 | +00:49 | [16.8 s](./views/Tree_0_0/thinking/turn_006.md) | 1.2 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe by rewrite xorbA (xorbC pi st) -xorbA xorbK xorbC xorb0 | ambient / ambient_logic, 1 goal, goal 343 chars | rejected probe: nothing to rewrite |  |
| T0.0-7 | +00:57 | [6.8 s](./views/Tree_0_0/thinking/turn_007.md) | 175 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | probe rewrite xorbA | ambient / ambient_logic, 1 goal, goal 343 chars | rejected probe: nothing to rewrite |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | probe move=> kK; elim: p st => //= pi p ih st | ambient / ambient_logic, 1 goal, goal 260 chars | accepted probe |  |
| T0.1-2 | +00:26 | [23.8 s](./views/Tree_0_1/thinking/turn_002.md) | 222 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit move=> kK; elim: p st => //= pi p ih st | ambient / ambient_logic, 1 goal, goal 260 chars | accepted commit |  |
| T0.1-3 | +00:41 | [14.7 s](./views/Tree_0_1/thinking/turn_003.md) | 1.3 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | probe rewrite kK ih; split=> //; rewrite xorbC xorbA xorbK xorbC xorb0 | ambient / ambient_logic, 1 goal, goal 412 chars | accepted probe |  |
| T0.1-4 | +00:49 | [6.8 s](./views/Tree_0_1/thinking/turn_004.md) | 161 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit rewrite kK ih; split=> //; rewrite xorbC xorbA xorbK xorbC xorb0 | ambient / ambient_logic, 1 goal, goal 412 chars | accepted commit |  |
| T0.1-5 | +00:55 | [5.8 s](./views/Tree_0_1/thinking/turn_005.md) | 158 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit done | ambient / ambient_logic, 1 goal, goal 317 chars | accepted commit |  |
| T0.1-6 | +00:58 | [2.8 s](./views/Tree_0_1/thinking/turn_006.md) | 152 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
