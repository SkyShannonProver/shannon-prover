# Agent-View Timeline — `RCPA_preservation`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1438_RCPA_preservation |
| lemma | `RCPA_preservation` |
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

### `Tree_0_0` — proved

```easycrypt
proof.
  move=> Mkg_ll Mtag_ll.
  rewrite (RCPA_prob E M A &m).
  do 2!congr.
  congr.
  byequiv=> //=.
  proc; inline *.
  wp; call (_: true).
  proc; inline *.
  wp; rnd; wp; call{2} Mtag_ll; auto.
  call{2} Mkg_ll; auto.
  qed.
```

### `Tree_0_1` — incomplete — 7 tactic(s) committed, not closed

```easycrypt
proof.
  move=> Mkg_ll Mtag_ll.
  have ->: Pr[INDR_CPA(MacThenEncrypt(E, M), A).main() @ &m : res] = Pr[SKEa.RCPA.INDR_CPA(E, RCPAa(M, A)).main() @ &m : res] by exact (RCPA_prob E M A &m).
  have ->: Pr[INDR_CPA(Ideal, A).main() @ &m : res] = Pr[SKEa.RCPA.INDR_CPA(SKEa.RCPA.Ideal, RCPAa(M, A)).main() @ &m : res]; last by done.
  byequiv=> //=.
  proc; inline *.
  wp; call (_: true).
  proc; inline *.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1438_RCPA_preservation

Run dir: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_RCPA_preservation/r01/2026-06-11_1438_RCPA_preservation/iteration_1`

t=0: `2026-06-11T21:40:40.600000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 2.4 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> Mkg_ll Mtag_ll | probability / pr / probability, 1 goal, goal 616 chars | accepted commit |  |
| T0.0-2 | +00:10 | [7.5 s](./views/Tree_0_0/thinking/turn_002.md) | 483 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit rewrite (RCPA_prob E M A &m) | probability / pr / probability, 1 goal, goal 639 chars | accepted commit |  |
| T0.0-3 | +00:16 | [5.9 s](./views/Tree_0_0/thinking/turn_003.md) | 128 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit do 2!congr | probability / pr / probability, 1 goal, goal 640 chars | accepted commit |  |
| T0.0-4 | +00:23 | [6.5 s](./views/Tree_0_0/thinking/turn_004.md) | 498 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit congr | probability / pr / probability, 1 goal, goal 516 chars | accepted commit |  |
| T0.0-5 | +00:28 | 4.9 s | 132 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit byequiv=> //= | probability / pr / probability, 1 goal, goal 512 chars | accepted commit |  |
| T0.0-6 | +00:34 | [5.2 s](./views/Tree_0_0/thinking/turn_006.md) | 1.8 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 644 chars | accepted commit |  |
| T0.0-7 | +00:46 | [10.9 s](./views/Tree_0_0/thinking/turn_007.md) | 144 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit wp; call (_: true) | pRHL / call_site / seq_cut, 1 goal, goal 1366 chars | accepted commit |  |
| T0.0-8 | +00:54 | [8.1 s](./views/Tree_0_0/thinking/turn_008.md) | 1.9 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit proc; inline * | equiv / prhl_module / relational_program, 2 goals, goal 562 chars | accepted commit |  |
| T0.0-9 | +01:11 | 14.4 s | 3.6 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit wp; rnd; call{2} Mtag_ll; auto | pRHL / call_site / relational_program, 2 goals, goal 1087 chars | rejected commit: [error] invalid last instruction |  |
| T0.0-10 | +01:30 | [15.9 s](./views/Tree_0_0/thinking/turn_010.md) | 2.1 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit wp; rnd; wp; call{2} Mtag_ll; auto | pRHL / call_site / relational_program, 2 goals, goal 1087 chars | accepted commit |  |
| T0.0-11 | +01:40 | [7.8 s](./views/Tree_0_0/thinking/turn_011.md) | 165 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit call{2} Mkg_ll; auto | pRHL / call_site / relational_program, 1 goal, goal 883 chars | accepted commit |  |
| T0.0-12 | +01:46 | [5.8 s](./views/Tree_0_0/thinking/turn_012.md) | 158 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-13 | +01:53 | 7 s |  | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:26 | [think](./views/Tree_0_1/thinking/turn_001.md) | 2.2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit move=> Mkg_ll Mtag_ll | probability / pr / probability, 1 goal, goal 616 chars | accepted commit |  |
| T0.1-2 | +00:36 | [7.5 s](./views/Tree_0_1/thinking/turn_002.md) | 479 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit have ->: Pr[INDR_CPA(MacThenEncrypt(E, M), A).main() @ &m : res] = Pr... | probability / pr / probability, 1 goal, goal 639 chars | accepted commit |  |
| T0.1-3 | +00:42 | [5.5 s](./views/Tree_0_1/thinking/turn_003.md) | 513 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit have ->: Pr[INDR_CPA(Ideal, A).main() @ &m : res] = Pr[SKEa.RCPA.INDR_CPA(SKEa.RCPA.Ideal, RC... | probability / pr / probability, 1 goal, goal 640 chars | accepted commit |  |
| T0.1-4 | +00:50 | 7.9 s | 149 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit byequiv=> //= | probability / pr / probability, 1 goal, goal 512 chars | accepted commit |  |
| T0.1-5 | +00:59 | 8.2 s | 1.8 s | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit proc; inline * | equiv / prhl_module / relational_program, 1 goal, goal 644 chars | accepted commit |  |
| T0.1-6 | +01:08 | [7.9 s](./views/Tree_0_1/thinking/turn_006.md) | 147 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit wp; call (_: true) | pRHL / call_site / seq_cut, 1 goal, goal 1366 chars | accepted commit |  |
| T0.1-7 | +01:22 | 13.9 s | 2.1 s | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit by proc; inline *; wp; rnd; call{2} Mtag_ll; auto | equiv / prhl_module / relational_program, 2 goals, goal 562 chars | rejected commit: [error] invalid last instruction |  |
| T0.1-8 | +01:37 | 13 s | 2 s | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit proc; inline * | equiv / prhl_module / relational_program, 2 goals, goal 562 chars | accepted commit |  |
