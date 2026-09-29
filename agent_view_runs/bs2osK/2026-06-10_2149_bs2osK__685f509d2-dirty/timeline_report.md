# Agent-View Timeline — `bs2osK`

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-10_2149_bs2osK |
| lemma | `bs2osK` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 5 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  rewrite /os2bs /bs2os flattenK //.
  by move=> b /mapP [x [_ ->]]; rewrite size_block.
  by rewrite -map_comp id_map // => x; rewrite /(\o) mkblockK.
  qed.
```

### `Tree_0_1` — incomplete — 0 tactic(s) committed, not closed (timeline replay — no session history survived)

```easycrypt
proof.
  (* no tactic committed *)
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_2149_bs2osK

Run dir: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_bs2osK/r01/2026-06-10_2149_bs2osK/iteration_1`

t=0: `2026-06-11T04:52:19.600000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.4 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit rewrite /os2bs /bs2os flattenK // | ambient / ambient_logic, 1 goal, goal 147 chars | accepted commit |  |
| T0.0-2 | +00:07 | [5.8 s](./views/Tree_0_0/thinking/turn_002.md) | 154 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit by move=> b /mapP [x [_ ->]]; rewrite size_block | ambient / ambient_logic, 2 goals, goal 213 chars | accepted commit |  |
| T0.0-3 | +00:13 | 5.8 s | 150 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit by rewrite -map_comp id_map // => x; rewrite /(\o) mkblockK | ambient / ambient_logic, 1 goal, goal 171 chars | accepted commit |  |
| T0.0-4 | +00:18 | [4.6 s](./views/Tree_0_0/thinking/turn_004.md) | 1.4 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.0-5 | +00:25 | 6 s |  | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
