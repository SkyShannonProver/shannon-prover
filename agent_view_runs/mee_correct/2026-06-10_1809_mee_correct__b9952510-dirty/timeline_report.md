# Agent-View Timeline — `mee_correct`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1809_mee_correct |
| lemma | `mee_correct` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 4 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  move=> PiK; rewrite /mee_enc /mee_dec /= cbc_correct // padK /=.
  done.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1809_mee_correct

Run dir: `artifacts/eval_suite/rerun_iclass/l1_goal_projection/mee_correct/r01/2026-06-10_1809_mee_correct/iteration_1`

t=0: `2026-06-11T01:10:14.400000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> PiK; rewrite /mee_enc /mee_dec /= cbc_correct // padK /= | ambient / ambient_logic, 1 goal, goal 300 chars | accepted commit |  |
| T0.0-2 | +00:08 | [6.8 s](./views/Tree_0_0/thinking/turn_002.md) | 158 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit done | ambient / ambient_logic, 1 goal, goal 264 chars | accepted commit |  |
| T0.0-3 | +00:11 | [2.9 s](./views/Tree_0_0/thinking/turn_003.md) | 147 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-4 | +00:16 | 4 s |  | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
