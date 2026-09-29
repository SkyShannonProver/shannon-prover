# Agent-View Timeline — `Random_Ideal`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1525_Random_Ideal |
| lemma | `Random_Ideal` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 20 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  transitivity{1} { c <@ LoopSnoc.sample(size p + 1); } (={k, p} ==> ={c}) (size p{1} = size p{2} ==> c{1} = r{2}).
  smt().
  smt().
  inline *; wp.
  while (i{1} = i0{2} /\ c{1} = l{2} /\ n{2} = size p{1} + 1); auto=> /> /#.
  transitivity{2} { r <@ Sample.sample(size p + 1); } (size p{1} = size p{2} ==> c{1} = r{2}) (={k, p} ==> ={r}).
  smt().
  smt().
  symmetry; call Sample_LoopSnoc_eq; auto=> /#.
  inline *; wp; rnd; auto=> />.
  qed.
```

### `Tree_0_1` — incomplete — 7 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  transitivity {1} { c <@ LoopSnoc.sample(size p + 1); } (={k, p} ==> ={c}) (size p{1} = size p{2} ==> c{1} = r{2}).
  by move=> &1 &2 h; exists k{1} p{1}.
  by move=> &1 &m &2 ->.
  inline *; wp.
  while (i{1} = i0{2} /\ n{2} = size p{1} + 1 /\ c{1} = l{2}); by auto=> /#.
  transitivity {1} { c <@ Sample.sample(size p + 1); } (={p} ==> ={c}) (size p{1} = size p{2} ==> c{1} = r{2}).
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1525_Random_Ideal

Run dir: `artifacts/eval_suite/mee_sweep_l1_all/l1_goal_projection/mee_Random_Ideal/r01/2026-06-11_1525_Random_Ideal/iteration_1`

t=0: `2026-06-11T22:28:02.700000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 191 chars | accepted commit |  |
| T0.0-2 | +00:11 | 9.8 s | 182 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit transitivity{1} { c <@ LoopSnoc.sample(size p + 1); } (={k, p} ==> ={c}) (size p{1} = size p{... | pRHL / procedure_body / relational_program, 1 goal, goal 718 chars | accepted commit |  |
| T0.0-3 | +00:20 | [8.7 s](./views/Tree_0_0/thinking/turn_003.md) | 256 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit smt() | ambient / ambient_logic / relational_program, 4 goals, goal 291 chars | accepted commit |  |
| T0.0-4 | +00:26 | 5.8 s | 237 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit smt() | ambient / ambient_logic / relational_program, 3 goals, goal 196 chars | accepted commit |  |
| T0.0-5 | +01:04 | 37.8 s | 216 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline *; wp | pRHL / call_site / relational_program, 2 goals, goal 785 chars | accepted commit |  |
| T0.0-6 | +01:12 | [7.7 s](./views/Tree_0_0/thinking/turn_006.md) | 333 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit while (i{1} = i0{2} /\ c{1} = l{2} /\ n{2} = size p{1} + 1); auto=> /> /# | pRHL / procedure_body / relational_program, 2 goals, goal 1049 chars | accepted commit |  |
| T0.0-7 | +01:32 | [19.8 s](./views/Tree_0_0/thinking/turn_007.md) | 216 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit transitivity{2} { r <@ Sample.sample(size p + 1); } (size p{1} = size p{2} ==> c{1} = r{2}) (... | pRHL / call_site / relational_program, 1 goal, goal 341 chars | accepted commit |  |
| T0.0-8 | +01:38 | [5.7 s](./views/Tree_0_0/thinking/turn_008.md) | 251 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit smt() | ambient / ambient_logic / relational_program, 4 goals, goal 267 chars | accepted commit |  |
| T0.0-9 | +01:43 | 4.7 s | 254 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit smt() | ambient / ambient_logic / relational_program, 3 goals, goal 196 chars | accepted commit |  |
| T0.0-10 | +01:51 | 7.8 s | 222 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit symmetry; call Sample_LoopSnoc_eq; auto=> /# | pRHL / call_site / relational_program, 2 goals, goal 361 chars | accepted commit |  |
| T0.0-11 | +01:59 | [7.8 s](./views/Tree_0_0/thinking/turn_011.md) | 232 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit inline *; wp; rnd; auto=> /> | pRHL / call_site / relational_program, 1 goal, goal 324 chars | accepted commit |  |
| T0.0-12 | +02:04 | [4.8 s](./views/Tree_0_0/thinking/turn_012.md) | 174 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-13 | +02:11 | 7 s |  | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:32 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 191 chars | accepted commit |  |
| T0.1-2 | +00:43 | 9.8 s | 173 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit transitivity {1} { c <@ LoopSnoc.sample(size p + 1); } (={k, p} ==> ={c}) (size p{1} = size p... | pRHL / procedure_body / relational_program, 1 goal, goal 718 chars | accepted commit |  |
| T0.1-3 | +00:55 | [11.8 s](./views/Tree_0_1/thinking/turn_003.md) | 174 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit by move=> &1 &2 h; exists k{1} p{1} | ambient / ambient_logic / relational_program, 4 goals, goal 291 chars | accepted commit |  |
| T0.1-4 | +01:02 | [6.8 s](./views/Tree_0_1/thinking/turn_004.md) | 206 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit by move=> &1 &m &2 -> | ambient / ambient_logic / relational_program, 3 goals, goal 196 chars | accepted commit |  |
| T0.1-5 | +01:09 | [6.8 s](./views/Tree_0_1/thinking/turn_005.md) | 209 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit inline *; wp | pRHL / call_site / relational_program, 2 goals, goal 785 chars | accepted commit |  |
| T0.1-6 | +01:36 | 26.7 s | 278 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit while (i{1} = i0{2} /\ n{2} = size p{1} + 1 /\ c{1} = l{2}); by auto=> /# | pRHL / procedure_body / relational_program, 2 goals, goal 1049 chars | accepted commit |  |
| T0.1-7 | +02:05 | 28.8 s | 172 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit transitivity {1} { c <@ Sample.sample(size p + 1); } (={p} ==> ={c}) (size p{1} = size p{2} =... | pRHL / call_site / relational_program, 1 goal, goal 341 chars | accepted commit |  |
