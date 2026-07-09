# Agent-View Timeline — `enc_eq`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1534_enc_eq |
| lemma | `enc_eq` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 8 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc; inline *; wp.
  while (={i, s} /\ key0{1} = PRP.k{2} /\ p1{1} = p{2} /\ c1{1} = c{2}); by auto.
  qed.
```

### `Tree_0_1` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  proc; inline *; wp.
  while (={i, s} /\ key0{1} = PRP.k{2} /\ p1{1} = p{2} /\ c1{1} = c{2}).
  auto.
  auto.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1534_enc_eq

Run dir: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_enc_eq/r01/2026-06-11_1534_enc_eq/iteration_1`

t=0: `2026-06-11T22:35:20.800000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:05 | [think](./views/Tree_0_0/thinking/turn_001.md) | 4.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc; inline *; wp | equiv / prhl_module / relational_program, 1 goal, goal 280 chars | accepted commit |  |
| T0.0-2 | +00:26 | 16.8 s | 194 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit while (={i, s} /\ key0{1} = PRP.k{2} /\ p1{1} = p{2} /\ c1{1} = c{2}); by auto | pRHL / procedure_body / seq_cut, 1 goal, goal 2101 chars | accepted commit |  |
| T0.0-3 | +00:31 | [4.8 s](./views/Tree_0_0/thinking/turn_003.md) | 157 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-4 | +00:36 | 5 s |  | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 4.2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc; inline *; wp | equiv / prhl_module / relational_program, 1 goal, goal 280 chars | accepted commit |  |
| T0.1-2 | +00:13 | [8.8 s](./views/Tree_0_1/thinking/turn_002.md) | 205 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit while (={i, s} /\ key0{1} = PRP.k{2} /\ p1{1} = p{2} /\ c1{1} = c{2}) | pRHL / procedure_body / seq_cut, 1 goal, goal 2101 chars | accepted commit |  |
| T0.1-3 | +00:19 | [6 s](./views/Tree_0_1/thinking/turn_003.md) | 3 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit auto | pRHL / procedure_body / relational_program, 2 goals, goal 1002 chars | accepted commit |  |
| T0.1-4 | +00:29 | 6.8 s | 184 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit auto | pRHL / procedure_body / seq_cut, 1 goal, goal 1310 chars | accepted commit |  |
