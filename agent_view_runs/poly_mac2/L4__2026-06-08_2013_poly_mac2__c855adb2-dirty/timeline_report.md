# Agent-View Timeline — `poly_mac2`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-08_2013_poly_mac2 |
| lemma | `poly_mac2` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
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
  proc.
  inline *.
  wp; skip; smt().
  qed.
```

### `Tree_0_1` — incomplete — 2 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  inline *.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_2013_poly_mac2

Run dir: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/poly_mac2/r01/2026-06-08_2013_poly_mac2/iteration_1`

t=0: `2026-06-09T03:13:54.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:08 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 267 chars | accepted commit |  |
| T0.0-2 | +00:15 | [5.7 s](./views/Tree_0_0/thinking/turn_002.md) | 268 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 801 chars | accepted commit |  |
| T0.0-3 | +00:27 | [11.8 s](./views/Tree_0_0/thinking/turn_003.md) | 236 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit wp; skip; smt() | pRHL / procedure_body / relational_program, 1 goal, goal 976 chars | accepted commit |  |
| T0.0-4 | +00:32 | [4.8 s](./views/Tree_0_0/thinking/turn_004.md) | 175 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 267 chars | accepted commit |  |
| T0.1-2 | +00:12 | [10.7 s](./views/Tree_0_1/thinking/turn_002.md) | 273 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 801 chars | accepted commit |  |
