# Agent-View Timeline — `PIR_correct`

| field | value |
|---|---|
| commit | `b9952510` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-10_1737_PIR_correct |
| lemma | `PIR_correct` |
| source file | `eval/examples/PIR.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 15 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  move=> hi0.
  byphoare (_ : i = i0 ==> res = a i0) => //.
  proc; inline *; wp.
  while (0 <= j <= N /\ i = i0 /\ big predT a PIR.s +^ big predT a PIR.s' = (if i0 < j then a i0 else zerow)) (N - j).
  move=> z; wp.
  rnd predT; skip => />.
  move=> &hr ge0 leN hinv jltN.
  split; first by smt(dbool_ll).
  move=> _ v _ _; rewrite !big_cons /=.
  rewrite /predT /=.
  move: hinv; rewrite /predT /= => hinv; smt(xorwA xorwC xorw0 xorwK).
  wp; skip => />; smt(big_nil xorw0 xorwK).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_1737_PIR_correct

Run dir: `artifacts/eval_suite/rerun_iclass/l1_goal_projection/pir_correct/r01/2026-06-10_1737_PIR_correct/iteration_1`

t=0: `2026-06-11T00:39:02.800000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> hi0 | probability / pr / probability, 1 goal, goal 181 chars | accepted commit |  |
| T0.0-2 | +00:04 | [2.9 s](./views/Tree_0_0/thinking/turn_002.md) | 150 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit byphoare (_ : i = i0 ==> res = a i0) => // | probability / pr / probability, 1 goal, goal 195 chars | accepted commit |  |
| T0.0-3 | +00:09 | [4.8 s](./views/Tree_0_0/thinking/turn_003.md) | 153 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit proc; inline *; wp | phoare / procedure_entry / procedure_frontier, 1 goal, goal 215 chars | accepted commit |  |
| T0.0-4 | +00:26 | [16.8 s](./views/Tree_0_0/thinking/turn_004.md) | 152 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit while (0 <= j <= N /\ i = i0 /\ big predT a PIR.s +^ big predT a PIR.... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1025 chars | accepted commit |  |
| T0.0-5 | +00:49 | [22.8 s](./views/Tree_0_0/thinking/turn_005.md) | 162 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit move=> z; wp | phoare / procedure_body / procedure_frontier, 2 goals, goal 632 chars | accepted commit |  |
| T0.0-6 | +01:00 | [10.8 s](./views/Tree_0_0/thinking/turn_006.md) | 216 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit rnd predT; skip => /> | phoare / procedure_body / procedure_frontier, 2 goals, goal 1302 chars | accepted commit |  |
| T0.0-7 | +01:40 | [39.8 s](./views/Tree_0_0/thinking/turn_007.md) | 4.2 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit smt(big_cons big_nil xorwA xorwC xorw0 xorwK dbool_ll) | ambient / ambient_logic, 2 goals, goal 1524 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-8 | +02:16 | [31.7 s](./views/Tree_0_0/thinking/turn_008.md) | 4.3 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit move=> &hr ge0 leN hinv jltN; rewrite !big_cons /=; smt(xorwA xorwC xorw0 xorwK dbool_ll) | ambient / ambient_logic, 2 goals, goal 1524 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-9 | +02:26 | [5.8 s](./views/Tree_0_0/thinking/turn_009.md) | 157 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit move=> &hr ge0 leN hinv jltN | ambient / ambient_logic, 2 goals, goal 1524 chars | accepted commit |  |
| T0.0-10 | +02:35 | [8.8 s](./views/Tree_0_0/thinking/turn_010.md) | 206 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit split; first by smt(dbool_ll) | ambient / ambient_logic, 2 goals, goal 1503 chars | accepted commit |  |
| T0.0-11 | +02:41 | [5.9 s](./views/Tree_0_0/thinking/turn_011.md) | 149 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit move=> _ v _ _; rewrite !big_cons /= | ambient / ambient_logic, 2 goals, goal 1453 chars | accepted commit |  |
| T0.0-12 | +02:48 | [6.8 s](./views/Tree_0_0/thinking/turn_012.md) | 171 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit rewrite /predT /= | ambient / ambient_logic, 2 goals, goal 1591 chars | accepted commit |  |
| T0.0-13 | +03:05 | [17 s](./views/Tree_0_0/thinking/turn_013.md) | 3 s | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit move: hinv; rewrite /predT /= => hinv; smt(xorwA xorwC xorw0 xorwK) | ambient / ambient_logic, 2 goals, goal 1453 chars | accepted commit |  |
| T0.0-14 | +03:23 | [14.8 s](./views/Tree_0_0/thinking/turn_014.md) | 169 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit wp; skip => />; smt(big_nil xorw0 xorwK) | phoare / procedure_body / procedure_frontier, 1 goal, goal 870 chars | accepted commit |  |
| T0.0-15 | +03:26 | [2.9 s](./views/Tree_0_0/thinking/turn_015.md) | 142 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
