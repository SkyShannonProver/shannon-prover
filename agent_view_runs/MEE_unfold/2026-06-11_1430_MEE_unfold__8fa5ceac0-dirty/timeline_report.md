# Agent-View Timeline — `MEE_unfold`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1430_MEE_unfold |
| lemma | `MEE_unfold` |
| source file | `eval/examples/MEE-CBC/MAC_then_Pad_then_CBC.eca` |
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

### `Tree_0_0` — incomplete — 5 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv=> //.
  proc; inline *.
  wp; call (_: ={RCPA_Wrap.k, RCPA_QueryBounder.qC}).
  proc; sp; if=> //.
  inline *.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  byequiv=> //=.
  proc; inline *.
  wp; call (_: ={RCPA_Wrap.k, RCPA_QueryBounder.qC}); last by auto.
  proc; sp; if=> //=; last by sim.
  wp; inline *.
  wp; while (={i0, s} /\ c1{1} = c4{2} /\ p'{1} = p3{2} /\ ek{1} = key0{2}); auto=> />.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1430_MEE_unfold

Run dir: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1`

t=0: `2026-06-11T21:31:13.300000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +02:50 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 314 chars | accepted commit |  |
| T0.0-2 | +02:59 | 6.8 s | 201 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 911 chars | accepted commit |  |
| T0.0-3 | +03:09 | [8.8 s](./views/Tree_0_0/thinking/turn_003.md) | 181 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit wp; call (_: ={RCPA_Wrap.k, RCPA_QueryBounder.qC}) | pRHL / call_site / relational_program, 1 goal, goal 1788 chars | accepted commit |  |
| T0.0-4 | +03:18 | [9.8 s](./views/Tree_0_0/thinking/turn_004.md) | 205 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit proc; sp; if=> // | equiv / prhl_module / relational_program, 2 goals, goal 1093 chars | accepted commit |  |
| T0.0-5 | +03:26 | 7.8 s | 6.2 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline * | pRHL / call_site / relational_program, 3 goals, goal 1251 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 4.7 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit by byequiv=> //=; proc; inline *; sim | probability / pr / probability, 1 goal, goal 314 chars | rejected commit: [by]: cannot close goals |  |
| T0.1-2 | +00:12 | [6.8 s](./views/Tree_0_1/thinking/turn_002.md) | 173 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit byequiv=> //= | probability / pr / probability, 1 goal, goal 314 chars | accepted commit |  |
| T0.1-3 | +02:57 | [165.7 s](./views/Tree_0_1/thinking/turn_003.md) | 264 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 911 chars | accepted commit |  |
| T0.1-4 | +03:10 | 12.8 s | 217 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit wp; call (_: ={RCPA_Wrap.k, RCPA_QueryBounder.qC}); last by auto | pRHL / call_site / relational_program, 1 goal, goal 1788 chars | accepted commit |  |
| T0.1-5 | +03:19 | [8.8 s](./views/Tree_0_1/thinking/turn_005.md) | 207 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit proc; sp; if=> //=; last by sim | equiv / prhl_module / relational_program, 1 goal, goal 1078 chars | accepted commit |  |
| T0.1-6 | +03:29 | [9.6 s](./views/Tree_0_1/thinking/turn_006.md) | 6.4 s | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp; inline * | pRHL / call_site / relational_program, 1 goal, goal 1236 chars | accepted commit |  |
| T0.1-7 | +03:57 | 21.8 s | 223 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit wp; while (={i0, s} /\ c1{1} = c4{2} /\ p'{1} = p3{2} /\ ek{1} = key0{2}); auto=> /> | pRHL / procedure_body / seq_cut, 1 goal, goal 3841 chars | accepted commit |  |
| T0.1-8 | +04:04 | [5.8 s](./views/Tree_0_1/thinking/turn_008.md) | 152 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-9 | +04:09 | 5 s |  | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
