# Agent-View Timeline — `CPprgL`

| field | value |
|---|---|
| commit | `ef713ea` **(dirty/uncommitted)** |
| branch | `feat/agent-thinking-trace` |
| run time | 2026-06-01_0002_CPprgL |
| lemma | `CPprgL` |
| source file | `eval/examples/PRG.ec` |
| model | `claude-opus-4-6` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 4 |

Each row below: the view the agent saw → the intent it submitted → the manager result. Click a `turn_NNN.json` link to open that step's exact `ProverWorkspaceView` (copied into `./views/`).

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  by move=> PprgL; proc; sp; if=> //; call PprgL; wp.
  qed.
```

### `Tree_0_1` — incomplete — 0 tactic(s) committed, not closed

```easycrypt
proof.
  (* no tactic committed *)
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-01_0002_CPprgL

Run dir: `artifacts/eval_suite/compiler_ladder_matrix/l4_checked_action_surface/easy_prg_CPprgL/r01/2026-06-01_0002_CPprgL/iteration_1`

t=0: `2026-06-01T07:03:31.800000+00:00`

| View | Action time | Agent think | Manager time | Decision View | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe by move=> PprgL; proc; sp; if=> //; call PprgL; wp | ambient / ambient_logic, 1 goal, goal 205 chars | accepted probe |  |
| T0.0-2 | +00:07 | [4.8 s](./views/Tree_0_0/thinking/turn_002.md) | 249 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) | commit by move=> PprgL; proc; sp; if=> //; call PprgL; wp | ambient / ambient_logic, 1 goal, goal 205 chars | accepted commit |  |
| T0.0-3 | +00:14 | [6.8 s](./views/Tree_0_0/thinking/turn_003.md) | 191 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-4 | +00:18 | 4 s |  | [turn_003.json](./views/Tree_0_0/turn_003.json) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
