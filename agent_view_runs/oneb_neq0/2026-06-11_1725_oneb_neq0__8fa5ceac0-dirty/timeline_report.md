# Agent-View Timeline — `oneb_neq0`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1725_oneb_neq0 |
| lemma | `oneb_neq0` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 7 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  apply/negP=> heq.
  have: oneb.[0] = zerob.[0] by rewrite heq.
  rewrite /oneb /zerob !offunE //; exact/Octet.onew_neq0.
  qed.
```

### `Tree_0_1` — incomplete — 0 tactic(s) committed, not closed (timeline replay — no session history survived)

```easycrypt
proof.
  (* no tactic committed *)
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1725_oneb_neq0

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_oneb_neq0/r01/2026-06-11_1725_oneb_neq0/iteration_1`

t=0: `2026-06-12T00:26:46+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit apply/negP=> /(congr1 (fun b=> b.[0])) /=; rewrite /oneb /zerob !offunE //; exact/Octet.onew_... | ambient / ambient_logic, 1 goal, goal 124 chars | rejected commit: [error] This proof-term argument is not a valid formula: |  |
| T0.0-2 | +00:18 | [15.8 s](./views/Tree_0_0/thinking/turn_002.md) | 1.2 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit apply/negP=> heq; have := congr1 (fun b=> b.[0]) oneb zerob heq; rewrite /oneb /zerob !offunE... | ambient / ambient_logic, 1 goal, goal 124 chars | rejected commit: [error] This proof-term argument is not a valid formula: |  |
| T0.0-3 | +00:37 | [17.8 s](./views/Tree_0_0/thinking/turn_003.md) | 156 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit apply/negP=> heq | ambient / ambient_logic, 1 goal, goal 124 chars | accepted commit |  |
| T0.0-4 | +00:45 | [7.8 s](./views/Tree_0_0/thinking/turn_004.md) | 152 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit have: oneb.[0] = zerob.[0] by rewrite heq | ambient / ambient_logic, 1 goal, goal 146 chars | accepted commit |  |
| T0.0-5 | +00:51 | 5.8 s | 173 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit rewrite /oneb /zerob !offunE //; exact/Octet.onew_neq0 | ambient / ambient_logic, 1 goal, goal 170 chars | accepted commit |  |
| T0.0-6 | +00:59 | [7.9 s](./views/Tree_0_0/thinking/turn_006.md) | 133 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-7 | +01:07 | 8 s |  | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
