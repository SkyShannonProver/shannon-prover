# Agent-View Timeline — `cpa_ddh0`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-08_1737_cpa_ddh0 |
| lemma | `cpa_ddh0` |
| source file | `eval/examples/elgamal.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 24 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  byequiv => //.
  proc.
  inline *.
  swap{1} 7 -5.
  wp.
  call (_: true).
  wp.
  rnd.
  call (_: true).
  wp.
  auto.
  smt(expM).
  qed.
```

### `Tree_0_1` — incomplete — 9 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv=> //.
  proc.
  inline *.
  swap{1} 7 -5.
  wp.
  call (_: true).
  wp.
  rnd.
  call (_: true).
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_1737_cpa_ddh0

Run dir: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1`

t=0: `2026-06-09T00:38:24.022000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:03 | [think](./views/Tree_0_0/thinking/turn_001.md) | 965 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 195 chars | accepted commit |  |
| T0.0-2 | +00:09 | [5.1 s](./views/Tree_0_0/thinking/turn_002.md) | 935 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 264 chars | accepted commit |  |
| T0.0-3 | +00:13 | [3.0 s](./views/Tree_0_0/thinking/turn_003.md) | 959 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 963 chars | accepted commit |  |
| T0.0-4 | +00:48 | [34.1 s](./views/Tree_0_0/thinking/turn_004.md) | 923 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit swap{1} 7 -5 | pRHL / call_site / relational_program, 1 goal, goal 1158 chars | accepted commit |  |
| T0.0-5 | +01:18 | [29 s](./views/Tree_0_0/thinking/turn_005.md) | 1 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit wp | pRHL / call_site / relational_program, 1 goal, goal 1158 chars | accepted commit |  |
| T0.0-6 | +01:23 | [4.0 s](./views/Tree_0_0/thinking/turn_006.md) | 959 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit call true | pRHL / call_site / seq_cut, 1 goal, goal 1169 chars | accepted commit |  |
| T0.0-7 | +01:32 | [8.1 s](./views/Tree_0_0/thinking/turn_007.md) | 934 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 1144 chars | accepted commit |  |
| T0.0-8 | +01:39 | [6.0 s](./views/Tree_0_0/thinking/turn_008.md) | 957 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit rnd | pRHL / call_site / seq_cut, 1 goal, goal 1140 chars | accepted commit |  |
| T0.0-9 | +01:52 | [12.1 s](./views/Tree_0_0/thinking/turn_009.md) | 935 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit call true | pRHL / call_site / seq_cut, 1 goal, goal 1195 chars | accepted commit |  |
| T0.0-10 | +01:59 | [5.8 s](./views/Tree_0_0/thinking/turn_010.md) | 162 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit wp | pRHL / procedure_body / seq_cut, 1 goal, goal 1345 chars | accepted commit |  |
| T0.0-11 | +02:10 | [10.8 s](./views/Tree_0_0/thinking/turn_011.md) | 166 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit auto | pRHL / procedure_body / relational_program, 1 goal, goal 1209 chars | accepted commit |  |
| T0.0-12 | +02:28 | [18.1 s](./views/Tree_0_0/thinking/turn_012.md) | 881 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | lookup expM | ambient / ambient_logic / relational_program, 1 goal, goal 1042 chars | lookup result |  |
| T0.0-13 | +02:33 | [3.7 s](./views/Tree_0_0/thinking/turn_013.md) | 332 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit smt(expM) | ambient / ambient_logic / relational_program, 1 goal, goal 1042 chars | accepted commit |  |
| T0.0-14 | +02:36 | [2.9 s](./views/Tree_0_0/thinking/turn_014.md) | 142 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 978 ms | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 195 chars | accepted commit |  |
| T0.1-2 | +00:06 | [5.1 s](./views/Tree_0_1/thinking/turn_002.md) | 930 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 264 chars | accepted commit |  |
| T0.1-3 | +00:21 | [14.0 s](./views/Tree_0_1/thinking/turn_003.md) | 963 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit inline * | pRHL / call_site / relational_program, 1 goal, goal 963 chars | accepted commit |  |
| T0.1-4 | +01:45 | [83.1 s](./views/Tree_0_1/thinking/turn_004.md) | 913 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit swap{1} 7 -5 | pRHL / call_site / relational_program, 1 goal, goal 1158 chars | accepted commit |  |
| T0.1-5 | +01:50 | [4.3 s](./views/Tree_0_1/thinking/turn_005.md) | 1.7 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit call true | pRHL / call_site / relational_program, 1 goal, goal 1158 chars | rejected commit: [error] invalid last instruction |  |
| T0.1-6 | +01:59 | [7.1 s](./views/Tree_0_1/thinking/turn_006.md) | 921 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp | pRHL / call_site / failure_diagnostic, 1 goal, goal 1158 chars | accepted commit |  |
| T0.1-7 | +02:05 | [4.8 s](./views/Tree_0_1/thinking/turn_007.md) | 1.2 s | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit call true | pRHL / call_site / seq_cut, 1 goal, goal 1169 chars | accepted commit |  |
| T0.1-8 | +02:14 | [8 s](./views/Tree_0_1/thinking/turn_008.md) | 1 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit wp | pRHL / call_site / seq_cut, 1 goal, goal 1144 chars | accepted commit |  |
| T0.1-9 | +02:23 | [8 s](./views/Tree_0_1/thinking/turn_009.md) | 1 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit rnd | pRHL / call_site / seq_cut, 1 goal, goal 1140 chars | accepted commit |  |
| T0.1-10 | +02:28 | [4.0 s](./views/Tree_0_1/thinking/turn_010.md) | 968 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit call true | pRHL / call_site / seq_cut, 1 goal, goal 1195 chars | accepted commit |  |
