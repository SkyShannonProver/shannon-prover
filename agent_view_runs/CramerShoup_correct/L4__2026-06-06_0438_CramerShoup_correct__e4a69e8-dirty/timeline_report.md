# Agent-View Timeline — `CramerShoup_correct`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_0438_CramerShoup_correct |
| lemma | `CramerShoup_correct` |
| source file | `eval/examples/cramer-shoup/cramer_shoup.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 22 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  inline *; auto.
  move=> &hr _ x1 hx1 x2 hx2 y1 hy1 y2 hy2 z1 hz1 z2 hz2 w hw k hk /= u hu /=.
  pose V := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}); have hc: (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u * (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * V) = DH.G.g ^ u ^ (x1 + V * y1) * DH.G.g ^ w ^ u ^ (x2 + V * y2); first by rewrite log_bij !(logg1, logrzM, logDr); ring.
  rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2; first by rewrite log_bij !(logg1, logrzM, logDr); ring. rewrite -hD log_bij !(logg1, logrzM, logDr) -expN !(logg1, logrzM, logDr); ring.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_0438_CramerShoup_correct

Run dir: `artifacts/eval_suite/wave1_ablation/l4_checked_action_surface/d1_cramershoup/r01/2026-06-06_0438_CramerShoup_correct/iteration_1`

t=0: `2026-06-06T11:39:36+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | probe proc | hoare / procedure_entry / procedure_frontier, 1 goal, goal 169 chars | accepted probe |  |
| T0.0-2 | +00:09 | [6.8 s](./views/Tree_0_0/thinking/turn_002.md) | 152 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | hoare / procedure_entry / procedure_frontier, 1 goal, goal 169 chars | accepted commit |  |
| T0.0-3 | +00:16 | [7 s](./views/Tree_0_0/thinking/turn_003.md) | 1 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | probe inline *; auto | hoare / procedure_body / procedure_frontier, 1 goal, goal 388 chars | accepted probe |  |
| T0.0-4 | +01:11 | [53.9 s](./views/Tree_0_0/thinking/turn_004.md) | 139 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit inline *; auto | hoare / procedure_body / procedure_frontier, 1 goal, goal 388 chars | accepted commit |  |
| T0.0-5 | +01:27 | [16 s](./views/Tree_0_0/thinking/turn_005.md) | 1 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | probe move=> &hr _ x1 hx1 x2 hx2 y1 hy1 y2 hy2 z1 hz1 z2 hz2 w hw k hk /= u... | ambient / ambient_logic, 1 goal, goal 1498 chars | accepted probe |  |
| T0.0-6 | +02:11 | [42.8 s](./views/Tree_0_0/thinking/turn_006.md) | 157 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit move=> &hr _ x1 hx1 x2 hx2 y1 hy1 y2 hy2 z1 hz1 z2 hz2 w hw k hk /= u... | ambient / ambient_logic, 1 goal, goal 1498 chars | accepted commit |  |
| T0.0-7 | +02:28 | [17.0 s](./views/Tree_0_0/thinking/turn_007.md) | 960 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | lookup log_bij | ambient / ambient_logic, 1 goal, goal 1453 chars | lookup result |  |
| T0.0-8 | +02:41 | [12 s](./views/Tree_0_0/thinking/turn_008.md) | 1 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | probe pose V := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}); have... | ambient / ambient_logic, 1 goal, goal 1453 chars | accepted probe |  |
| T0.0-9 | +03:02 | [19.9 s](./views/Tree_0_0/thinking/turn_009.md) | 149 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit pose V := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}); have... | ambient / ambient_logic, 1 goal, goal 1453 chars | accepted commit |  |
| T0.0-10 | +03:11 | [9 s](./views/Tree_0_0/thinking/turn_010.md) | 1 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | probe rewrite hc /= | ambient / ambient_logic, 1 goal, goal 1413 chars | accepted probe |  |
| T0.0-11 | +03:21 | [8.8 s](./views/Tree_0_0/thinking/turn_011.md) | 168 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | probe rewrite hc /=; rewrite log_bij !(logg1, logrzM, logDr); ring | ambient / ambient_logic, 1 goal, goal 1413 chars | accepted probe |  |
| T0.0-12 | +03:42 | [21.0 s](./views/Tree_0_0/thinking/turn_012.md) | 954 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | lookup logVr | ambient / ambient_logic, 1 goal, goal 1413 chars | lookup result |  |
| T0.0-13 | +04:30 | [46.9 s](./views/Tree_0_0/thinking/turn_013.md) | 109 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | inspect lemma_hints | ambient / ambient_logic, 1 goal, goal 1413 chars | read-only inspect |  |
| T0.0-14 | +04:59 | [28.8 s](./views/Tree_0_0/thinking/turn_014.md) | 165 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | probe rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^... | ambient / ambient_logic, 1 goal, goal 1413 chars | accepted probe |  |
| T0.0-15 | +05:10 | [11.1 s](./views/Tree_0_0/thinking/turn_015.md) | 933 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | lookup mulrK | ambient / ambient_logic, 1 goal, goal 1413 chars | lookup result |  |
| T0.0-16 | +05:38 | [27.0 s](./views/Tree_0_0/thinking/turn_016.md) | 957 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | lookup logDr | ambient / ambient_logic, 1 goal, goal 1413 chars | lookup result |  |
| T0.0-17 | +06:29 | [49.6 s](./views/Tree_0_0/thinking/turn_017.md) | 3.4 s | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | probe rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^... | ambient / ambient_logic, 1 goal, goal 1413 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-18 | +07:06 | [34.1 s](./views/Tree_0_0/thinking/turn_018.md) | 938 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | lookup expN | ambient / ambient_logic, 1 goal, goal 1413 chars | lookup result |  |
| T0.0-19 | +08:00 | [52.8 s](./views/Tree_0_0/thinking/turn_019.md) | 154 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | probe rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^... | ambient / ambient_logic, 1 goal, goal 1413 chars | accepted probe |  |
| T0.0-20 | +08:14 | [13.8 s](./views/Tree_0_0/thinking/turn_020.md) | 168 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^... | ambient / ambient_logic, 1 goal, goal 1413 chars | accepted commit |  |
| T0.0-21 | +08:17 | [2.8 s](./views/Tree_0_0/thinking/turn_021.md) | 164 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-22 | +08:23 | 6 s |  | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
