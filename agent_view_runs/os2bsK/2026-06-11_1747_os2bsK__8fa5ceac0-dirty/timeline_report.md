# Agent-View Timeline — `os2bsK`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1747_os2bsK |
| lemma | `os2bsK` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 9 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 3 tactic(s) committed, not closed

```easycrypt
proof.
  move=> dvd16.
  rewrite /bs2os /os2bs -map_comp.
  have ->: map (ofblock \o mkblock) (chunk 16 os) = chunk 16 os.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  move=> dvd16.
  rewrite /bs2os /os2bs -map_comp.
  have ->: map (ofblock \o mkblock) (chunk 16 os) = map idfun (chunk 16 os) by apply/eq_in_map => x xin @/(\o) @/idfun /=; rewrite ofblockK // (@in_chunk_size 16 os).
  by rewrite map_id chunkK.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1747_os2bsK

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_os2bsK/r01/2026-06-11_1747_os2bsK/iteration_1`

t=0: `2026-06-12T00:49:34.600000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:03 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.3 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit move=> dvd16 | ambient / ambient_logic, 1 goal, goal 164 chars | accepted commit |  |
| T0.0-2 | +00:09 | [4.8 s](./views/Tree_0_0/thinking/turn_002.md) | 163 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit rewrite /bs2os /os2bs -map_comp | ambient / ambient_logic, 1 goal, goal 181 chars | accepted commit |  |
| T0.0-3 | +00:15 | 5.9 s | 127 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit have ->: map (ofblock \o mkblock) (chunk 16 os) = chunk 16 os | ambient / ambient_logic, 1 goal, goal 213 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:00 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.4 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit move=> dvd16 | ambient / ambient_logic, 1 goal, goal 164 chars | accepted commit |  |
| T0.1-2 | +00:06 | [4.8 s](./views/Tree_0_1/thinking/turn_002.md) | 154 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit rewrite /bs2os /os2bs -map_comp | ambient / ambient_logic, 1 goal, goal 181 chars | accepted commit |  |
| T0.1-3 | +00:14 | 7.8 s | 156 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit have ->: map (ofblock \o mkblock) (chunk 16 os) = map idfun (chunk 16 os) by apply/eq_in_map... | ambient / ambient_logic, 1 goal, goal 213 chars | accepted commit |  |
| T0.1-4 | +00:20 | [5.8 s](./views/Tree_0_1/thinking/turn_004.md) | 160 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit by rewrite map_id chunkK | ambient / ambient_logic, 1 goal, goal 211 chars | accepted commit |  |
| T0.1-5 | +00:24 | [3.9 s](./views/Tree_0_1/thinking/turn_005.md) | 150 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-6 | +00:29 | 5 s |  | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
