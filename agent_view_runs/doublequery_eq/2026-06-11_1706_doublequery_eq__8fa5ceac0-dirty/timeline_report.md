# Agent-View Timeline — `doublequery_eq`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1706_doublequery_eq |
| lemma | `doublequery_eq` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 14 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv=> //=.
  proc; inline *; sim.
  call (_: ={glob F}).
  proc; inline *; sim.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  byequiv=> //=.
  proc.
  call (_: ={glob F}).
  proc.
  while (={i, s, c, p} /\ (glob F){1} = (glob F){2}).
  inline {2} DoubleQuery(F).f; wp; call (_: true); auto.
  auto.
  inline {2} DoubleQuery(F).init; wp; call (_: true); auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1706_doublequery_eq

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_doublequery_eq/r01/2026-06-11_1706_doublequery_eq/iteration_1`

t=0: `2026-06-12T00:07:12.800000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv=> //= | probability / pr / probability, 1 goal, goal 270 chars | accepted commit |  |
| T0.0-2 | +00:12 | [10.8 s](./views/Tree_0_0/thinking/turn_002.md) | 1.2 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc; inline *; sim | equiv / prhl_module / relational_program, 1 goal, goal 452 chars | accepted commit |  |
| T0.0-3 | +01:03 | 49.8 s | 203 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit call (_: ={glob F}) | pRHL / call_site / seq_cut, 1 goal, goal 791 chars | accepted commit |  |
| T0.0-4 | +01:12 | 8.9 s | 1.1 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit proc; inline *; sim | equiv / prhl_module / relational_program, 2 goals, goal 332 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:28 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit byequiv=> //= | probability / pr / probability, 1 goal, goal 270 chars | accepted commit |  |
| T0.1-2 | +00:34 | [4.8 s](./views/Tree_0_1/thinking/turn_002.md) | 195 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 452 chars | accepted commit |  |
| T0.1-3 | +00:39 | [4.8 s](./views/Tree_0_1/thinking/turn_003.md) | 242 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit call (_: ={glob F}) | pRHL / call_site / relational_program, 1 goal, goal 615 chars | accepted commit |  |
| T0.1-4 | +00:45 | [5.8 s](./views/Tree_0_1/thinking/turn_004.md) | 239 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit proc | equiv / prhl_module / relational_program, 2 goals, goal 332 chars | accepted commit |  |
| T0.1-5 | +00:52 | 6.8 s | 231 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit while (={i, s, c, p} /\ (glob F){1} = (glob F){2}) | pRHL / call_site / relational_program, 2 goals, goal 1103 chars | accepted commit |  |
| T0.1-6 | +01:00 | [7.7 s](./views/Tree_0_1/thinking/turn_006.md) | 263 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit inline {2} DoubleQuery(F).f; wp; call (_: true); auto | pRHL / call_site / relational_program, 3 goals, goal 874 chars | accepted commit |  |
| T0.1-7 | +01:08 | [7.8 s](./views/Tree_0_1/thinking/turn_007.md) | 232 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit auto | pRHL / verification_residue / relational_program, 2 goals, goal 893 chars | accepted commit |  |
| T0.1-8 | +01:20 | [11.8 s](./views/Tree_0_1/thinking/turn_008.md) | 164 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit inline {2} DoubleQuery(F).init; wp; call (_: true); auto | pRHL / procedure_body / relational_program, 1 goal, goal 657 chars | accepted commit |  |
| T0.1-9 | +01:26 | [5.8 s](./views/Tree_0_1/thinking/turn_009.md) | 220 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-10 | +01:32 | 6 s |  | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
