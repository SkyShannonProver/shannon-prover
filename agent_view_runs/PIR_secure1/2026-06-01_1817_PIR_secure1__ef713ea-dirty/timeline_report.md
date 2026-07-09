# Agent-View Timeline — `PIR_secure1`

| field | value |
|---|---|
| commit | `ef713ea` **(dirty/uncommitted)** |
| branch | `ablation/l1-l4-surface` |
| run time | 2026-06-01_1817_PIR_secure1 |
| lemma | `PIR_secure1` |
| source file | `eval/examples/PIR.ec` |
| model | `claude-opus-4-6` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 9 |

Each row below: the view the agent saw → the intent it submitted → the manager result. Click a `turn_NNN.json` link to open that step's exact `ProverWorkspaceView` (copied into `./views/`).

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 3 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  inline *.
  wp.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc; inline *; wp.
  while (={PIR.s, j}).
  auto.
  auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-01_1817_PIR_secure1

Run dir: `artifacts/eval_suite/l1_l4_surface_ablation/l1_goal_projection/pir_secure1_exec/r01/2026-06-01_1817_PIR_secure1/iteration_1`

t=0: `2026-06-02T01:18:29.400000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.6 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted commit |  |
| T0.0-2 | +00:27 | [25.7 s](./views/Tree_0_0/thinking/turn_002.md) | 266 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) | commit inline * | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected commit: manager reported rejection |  |
| T0.0-3 | +00:48 | [20.5 s](./views/Tree_0_0/thinking/turn_003.md) | 1.5 s | [turn_002.json](./views/Tree_0_0/turn_002.json) | commit wp | pRHL / verification_residue / relational_program, 1 goal, goal 1066 chars | rejected commit: manager reported rejection |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:24 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc; inline *; wp | equiv / prhl_module / relational_program, 1 goal, goal 175 chars | accepted commit |  |
| T0.1-2 | +00:39 | [13.7 s](./views/Tree_0_1/thinking/turn_002.md) | 295 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) | commit while (={PIR.s, j}) | pRHL / verification_residue / relational_program, 1 goal, goal 1024 chars | accepted commit |  |
| T0.1-3 | +00:50 | [10.8 s](./views/Tree_0_1/thinking/turn_003.md) | 246 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) | commit auto | pRHL / verification_residue / relational_program, 2 goals, goal 945 chars | accepted commit |  |
| T0.1-4 | +00:56 | [5.8 s](./views/Tree_0_1/thinking/turn_004.md) | 230 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) | commit auto | pRHL / verification_residue / relational_program, 1 goal, goal 589 chars | accepted commit |  |
| T0.1-5 | +01:00 | [3.8 s](./views/Tree_0_1/thinking/turn_005.md) | 211 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-6 | +01:04 | 3 s |  | [turn_005.json](./views/Tree_0_1/turn_005.json) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
