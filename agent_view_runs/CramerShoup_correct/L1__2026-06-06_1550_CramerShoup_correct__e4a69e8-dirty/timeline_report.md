# Agent-View Timeline — `CramerShoup_correct`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1550_CramerShoup_correct |
| lemma | `CramerShoup_correct` |
| source file | `eval/examples/cramer-shoup/cramer_shoup.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 11 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc; inline *; auto.
  move=> &hr _ x1 _ x2 _ y1 _ y2 _ z1 _ z2 _ w _ k _ /= u _ /=.
  pose v := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}).
  have hd : (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u * (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * v) = DH.G.g ^ u ^ (x1 + v * y1) * DH.G.g ^ w ^ u ^ (x2 + v * y2) by rewrite log_bij !(logg1, logrzM, logDr); ring.
  have hc : (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} / (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2) = m{hr} by rewrite log_bij !(logg1, logrzM, logDr, logrV); ring.
  rewrite hd /=.
  exact hc.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1550_CramerShoup_correct

Run dir: `artifacts/eval_suite/wave1_rerun_l1/l1_goal_projection/d1_cramershoup/r01/2026-06-06_1550_CramerShoup_correct/iteration_1`

t=0: `2026-06-06T22:52:28.700000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc; inline *; auto | hoare / procedure_entry / procedure_frontier, 1 goal, goal 169 chars | accepted commit |  |
| T0.0-2 | +01:32 | [90.9 s](./views/Tree_0_0/thinking/turn_002.md) | 148 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit move=> &hr _ x1 _ x2 _ y1 _ y2 _ z1 _ z2 _ w _ k _ /= u _ /= | ambient / ambient_logic, 1 goal, goal 1498 chars | accepted commit |  |
| T0.0-3 | +02:20 | [47.9 s](./views/Tree_0_0/thinking/turn_003.md) | 139 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit pose v := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w... | ambient / ambient_logic, 1 goal, goal 1311 chars | accepted commit |  |
| T0.0-4 | +02:25 | [4.8 s](./views/Tree_0_0/thinking/turn_004.md) | 159 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit have hd : (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u * (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * v) = D... | ambient / ambient_logic, 1 goal, goal 1117 chars | accepted commit |  |
| T0.0-5 | +02:30 | [5 s](./views/Tree_0_0/thinking/turn_005.md) | 1 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit have hc : (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} / (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z... | ambient / ambient_logic, 1 goal, goal 1271 chars | rejected commit: proof state unchanged |  |
| T0.0-6 | +03:04 | [32.9 s](./views/Tree_0_0/thinking/turn_006.md) | 139 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit have hc : (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} / (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z... | ambient / ambient_logic, 1 goal, goal 1271 chars | accepted commit |  |
| T0.0-7 | +03:17 | [13 s](./views/Tree_0_0/thinking/turn_007.md) | 1 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit by rewrite hd eqxx /= hc | ambient / ambient_logic, 1 goal, goal 1373 chars | rejected commit: proof state unchanged |  |
| T0.0-8 | +03:38 | [19.8 s](./views/Tree_0_0/thinking/turn_008.md) | 157 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit rewrite hd /= | ambient / ambient_logic, 1 goal, goal 1373 chars | accepted commit |  |
| T0.0-9 | +03:44 | [5.8 s](./views/Tree_0_0/thinking/turn_009.md) | 161 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit exact hc | ambient / ambient_logic, 1 goal, goal 1176 chars | accepted commit |  |
| T0.0-10 | +03:48 | [3.8 s](./views/Tree_0_0/thinking/turn_010.md) | 155 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-11 | +03:51 | 3 s |  | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
