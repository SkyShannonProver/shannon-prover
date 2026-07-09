# Agent-View Timeline — `PTXT_security`

| field | value |
|---|---|
| commit | `685f509d2` |
| branch | `HEAD` |
| run time | 2026-06-10_2112_PTXT_security |
| lemma | `PTXT_security` |
| source file | `eval/examples/MEE-CBC/RCPA_CMA.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 21 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  byequiv=> //.
  proc; inline *.
  swap{2} 4 -3.
  call (_: ={glob E, glob M} /\ PTXT_Wrap.k{1} = (CMAa.ek, MACa.WUF_CMA.WUF_Wrap.k){2} /\ PTXT_Wrap.s{1} = MACa.WUF_CMA.WUF_Wrap.s{2} /\ PTXT_Wrap.win{1} = MACa.WUF_CMA.WUF_Wrap.win{2}).
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  byequiv=> //=.
  proc; inline *.
  call (_:    ={glob E, glob M}
           /\ PTXT_Wrap.k{1} = (CMAa.ek, MACa.WUF_CMA.WUF_Wrap.k){2}
           /\ PTXT_Wrap.s{1} = MACa.WUF_CMA.WUF_Wrap.s{2}
           /\ PTXT_Wrap.win{1} = MACa.WUF_CMA.WUF_Wrap.win{2}).
  proc; inline *.
  wp; call (_: true).
  wp; call (_: true).
  by auto.
  proc; inline *.
  seq 5 2: (   ={glob E, glob M, pt}
            /\ PTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.WUF_CMA.WUF_Wrap.k{2})
            /\ PTXT_Wrap.s{1} = MACa.WUF_CMA.WUF_Wrap.s{2}
            /\ PTXT_Wrap.win{1} = MACa.WUF_CMA.WUF_Wrap.win{2}
            /\ mk{1} = MACa.WUF_CMA.WUF_Wrap.k{2}
            /\ p0{1} = None
            /\ b{2} = false).
  by wp; call (_: true); auto.
  if=> //.
  by wp; call (_: true); auto=> /#.
  by auto=> /#.
  swap{2} 4 -3.
  by wp; call (_: true); call (_: true); auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_2112_PTXT_security

Run dir: `artifacts/eval_suite/mee_ptxt_fable_l1/l1_goal_projection/mee_PTXT_security/r01/2026-06-10_2112_PTXT_security/iteration_1`

t=0: `2026-06-11T04:15:26+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +01:27 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit byequiv=>// | probability / pr / probability, 1 goal, goal 234 chars | accepted commit |  |
| T0.0-2 | +01:45 | 16.1 s | 1.9 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 489 chars | accepted commit |  |
| T0.0-3 | +01:58 | [11.1 s](./views/Tree_0_0/thinking/turn_003.md) | 1.9 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit swap{2} 4 -3 | pRHL / call_site / relational_program, 1 goal, goal 1131 chars | accepted commit |  |
| T0.0-4 | +02:19 | [18.9 s](./views/Tree_0_0/thinking/turn_004.md) | 150 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit call (_: ={glob E, glob M} /\ PTXT_Wrap.k{1} = (CMAa.ek, MACa.WUF_CMA... | pRHL / call_site / relational_program, 1 goal, goal 1131 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit byequiv=> //= | probability / pr / probability, 1 goal, goal 234 chars | accepted commit |  |
| T0.1-2 | +00:06 | 4.1 s | 1.9 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 489 chars | accepted commit |  |
| T0.1-3 | +00:18 | [9.8 s](./views/Tree_0_1/thinking/turn_003.md) | 201 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit call (_: ={glob E, glob M} /\ PTXT_Wrap.k{1} = (CMAa.ek, MACa.WUF_CMA... | pRHL / call_site / relational_program, 1 goal, goal 1131 chars | accepted commit |  |
| T0.1-4 | +00:23 | [5.1 s](./views/Tree_0_1/thinking/turn_004.md) | 1.9 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit proc; inline * | equiv / prhl_module / relational_program, 3 goals, goal 781 chars | accepted commit |  |
| T0.1-5 | +00:30 | 5.2 s | 1.8 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit wp; call (_: true) | pRHL / call_site / seq_cut, 3 goals, goal 1467 chars | accepted commit |  |
| T0.1-6 | +00:50 | 17.8 s | 203 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp; call (_: true) | pRHL / call_site / relational_program, 3 goals, goal 1442 chars | accepted commit |  |
| T0.1-7 | +00:55 | 4.6 s | 393 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit by auto | pRHL / procedure_body / relational_program, 3 goals, goal 1580 chars | accepted commit |  |
| T0.1-8 | +00:59 | [4.1 s](./views/Tree_0_1/thinking/turn_008.md) | 1.9 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit proc; inline * | equiv / prhl_module / relational_program, 2 goals, goal 790 chars | accepted commit |  |
| T0.1-9 | +01:31 | 30.2 s | 1.8 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit seq 5 2: ( ={glob E, glob M, pt} /\ PTXT_Wrap.k{1} = (CMAa.ek{2}, MAC... | pRHL / call_site / seq_cut, 2 goals, goal 3388 chars | accepted commit |  |
| T0.1-10 | +01:37 | 4.1 s | 1.9 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit by wp; call (_: true); auto | pRHL / call_site / seq_cut, 3 goals, goal 1276 chars | accepted commit |  |
| T0.1-11 | +01:44 | [4.9 s](./views/Tree_0_1/thinking/turn_011.md) | 2.1 s | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit if=> // | pRHL / call_site / relational_program, 2 goals, goal 2675 chars | accepted commit |  |
| T0.1-12 | +01:56 | [9.8 s](./views/Tree_0_1/thinking/turn_012.md) | 220 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit by wp; call (_: true); auto=> /# | pRHL / call_site / seq_cut, 3 goals, goal 2025 chars | accepted commit |  |
| T0.1-13 | +02:03 | 7.1 s | 1.9 s | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit by auto=> /# | pRHL / procedure_body / relational_program, 2 goals, goal 1353 chars | accepted commit |  |
| T0.1-14 | +02:10 | [5 s](./views/Tree_0_1/thinking/turn_014.md) | 2 s | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit swap{2} 4 -3 | pRHL / call_site / relational_program, 1 goal, goal 1422 chars | accepted commit |  |
| T0.1-15 | +02:18 | 5.8 s | 151 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit by wp; call (_: true); call (_: true); auto | pRHL / call_site / relational_program, 1 goal, goal 1422 chars | accepted commit |  |
| T0.1-16 | +02:22 | [3.9 s](./views/Tree_0_1/thinking/turn_016.md) | 130 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-17 | +02:26 | 4 s |  | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
