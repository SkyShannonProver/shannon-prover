# Agent-View Timeline — `step2`

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-11_0220_step2 |
| lemma | `step2` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-fable-5` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 6 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  have h1 := step1 &m.
  have h2 := step2_1 &m.
  have h3 := step2_2 &m.
  have h4 := step2_3 &m.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  move: (step1 &m) (step2_1 &m) (step2_2 &m) (step2_3 &m) => /#.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_0220_step2

Run dir: `artifacts/eval_suite/night_step2_fable_l4np/l4_checked_action_surface/cc_step2/r01/2026-06-11_0220_step2/iteration_1`

t=0: `2026-06-11T09:21:09+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit have h1 := step1 &m | probability / pr / probability, 1 goal, goal 465 chars | accepted commit |  |
| T0.0-2 | +00:10 | [8.3 s](./views/Tree_0_0/thinking/turn_002.md) | 669 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit have h2 := step2_1 &m | probability / pr / probability, 1 goal, goal 734 chars | accepted commit |  |
| T0.0-3 | +00:16 | 5.3 s | 664 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit have h3 := step2_2 &m | probability / pr / probability, 1 goal, goal 1050 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:14 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit move: (step1 &m) (step2_1 &m) (step2_2 &m) (step2_3 &m) => /# | probability / pr / probability, 1 goal, goal 465 chars | accepted commit |  |
| T0.1-2 | +00:23 | [7.8 s](./views/Tree_0_1/thinking/turn_002.md) | 194 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-3 | +00:30 | 7 s |  | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
