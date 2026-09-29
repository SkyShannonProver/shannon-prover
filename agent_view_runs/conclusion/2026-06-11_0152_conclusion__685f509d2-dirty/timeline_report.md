# Agent-View Timeline — `conclusion`

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-11_0152_conclusion |
| lemma | `conclusion` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-fable-5` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 22 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 7 tactic(s) committed, not closed

```easycrypt
proof.
  have h2 := step2 (BNR_Adv(A)) _ &m.
  move=> O enc_ll dec_ll; proc.
  call (A_ll (<:BNR(O)) _ _).
  proc; sp; if; [wp; call enc_ll; auto | auto].
  proc; sp; if; [wp; call dec_ll; auto | auto].
  inline *; auto.
  have h3 := step3 &m.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  have h2 := step2 (BNR_Adv(A)) _ &m.
  move=> O enc_ll dec_ll; proc; call (A_ll (BNR(O)) _ _).
  by proc; sp; if; [wp; call enc_ll; auto | auto].
  by proc; sp; if; [wp; call dec_ll; auto | auto].
  by inline *; auto.
  have h3 := step3 &m.
  have h41 := step4_1 &m.
  have hb2 := step4_bad2 &m; have hb1 := step4_bad1 &m.
  smt().
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_0152_conclusion

Run dir: `artifacts/eval_suite/night_ccp_fable_l4np/l4_checked_action_surface/cc_conclusion/r01/2026-06-11_0152_conclusion/iteration_1`

t=0: `2026-06-11T08:52:53.735000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +01:04 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | lookup CPA_game | probability / pr / probability, 1 goal, goal 450 chars | lookup result |  |
| T0.0-2 | +01:22 | 16.4 s | 1.6 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit have h2 := step2 (BNR_Adv(A)) _ &m | probability / pr / probability, 1 goal, goal 450 chars | accepted commit |  |
| T0.0-3 | +01:46 | 22.8 s | 187 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit move=> O enc_ll dec_ll; proc | ambient / ambient_logic, 2 goals, goal 257 chars | accepted commit |  |
| T0.0-4 | +01:59 | [12.8 s](./views/Tree_0_0/thinking/turn_004.md) | 198 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit call (A_ll (<:BNR(O)) _ _) | phoare / procedure_body / procedure_frontier, 2 goals, goal 355 chars | accepted commit |  |
| T0.0-5 | +02:15 | 15.8 s | 200 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit proc; sp; if; [wp; call enc_ll; auto \| auto] | phoare / procedure_body / procedure_frontier, 4 goals, goal 277 chars | accepted commit |  |
| T0.0-6 | +02:22 | [6.8 s](./views/Tree_0_0/thinking/turn_006.md) | 187 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit proc; sp; if; [wp; call dec_ll; auto \| auto] | phoare / procedure_body / procedure_frontier, 3 goals, goal 277 chars | accepted commit |  |
| T0.0-7 | +02:33 | [10.3 s](./views/Tree_0_0/thinking/turn_007.md) | 736 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit inline *; auto | phoare / procedure_body / procedure_frontier, 2 goals, goal 324 chars | accepted commit |  |
| T0.0-8 | +02:43 | 9.2 s | 762 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit have h3 := step3 &m | probability / pr / probability, 1 goal, goal 984 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 265 ms | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect lemma_hints | probability / pr / probability, 1 goal, goal 450 chars | read-only inspect |  |
| T0.1-2 | +00:09 | 8.4 s | 1.6 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | lookup step2 | probability / pr / probability, 1 goal, goal 450 chars | lookup result |  |
| T0.1-3 | +00:39 | 28.5 s | 1.5 s | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | lookup CPA_game | probability / pr / probability, 1 goal, goal 450 chars | lookup result |  |
| T0.1-4 | +01:25 | 44.4 s | 1.6 s | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit have h2 := step2 (BNR_Adv(A)) _ &m | probability / pr / probability, 1 goal, goal 450 chars | accepted commit |  |
| T0.1-5 | +01:41 | [14.8 s](./views/Tree_0_1/thinking/turn_005.md) | 186 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit move=> O enc_ll dec_ll; proc; call (A_ll (BNR(O)) _ _) | ambient / ambient_logic, 2 goals, goal 257 chars | accepted commit |  |
| T0.1-6 | +01:54 | [12.8 s](./views/Tree_0_1/thinking/turn_006.md) | 185 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit by proc; sp; if; [wp; call enc_ll; auto \| auto] | phoare / procedure_body / procedure_frontier, 4 goals, goal 277 chars | accepted commit |  |
| T0.1-7 | +02:01 | 6.8 s | 193 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit by proc; sp; if; [wp; call dec_ll; auto \| auto] | phoare / procedure_body / procedure_frontier, 3 goals, goal 277 chars | accepted commit |  |
| T0.1-8 | +02:11 | [9.3 s](./views/Tree_0_1/thinking/turn_008.md) | 718 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit by inline *; auto | phoare / procedure_body / procedure_frontier, 2 goals, goal 324 chars | accepted commit |  |
| T0.1-9 | +02:20 | [8.3 s](./views/Tree_0_1/thinking/turn_009.md) | 714 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit have h3 := step3 &m | probability / pr / probability, 1 goal, goal 984 chars | accepted commit |  |
| T0.1-10 | +02:25 | 4.3 s | 704 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit have h41 := step4_1 &m | probability / pr / probability, 1 goal, goal 1163 chars | accepted commit |  |
| T0.1-11 | +02:32 | 6.2 s | 762 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit have hb2 := step4_bad2 &m; have hb1 := step4_bad1 &m | probability / pr / probability, 1 goal, goal 1388 chars | accepted commit |  |
| T0.1-12 | +02:41 | 8.8 s | 238 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit smt() | probability / pr / probability, 1 goal, goal 1568 chars | accepted commit |  |
| T0.1-13 | +02:48 | [6.8 s](./views/Tree_0_1/thinking/turn_013.md) | 201 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-14 | +02:53 | 5 s |  | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
