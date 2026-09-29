# Agent-View Timeline — `mee_decrypt_correct`

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-10_2153_mee_decrypt_correct |
| lemma | `mee_decrypt_correct` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 12 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 4 tactic(s) committed, not closed

```easycrypt
proof.
  proc; inline PRPc.PseudoRP.fi MAC.verify.
  wp.
  while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ c = behead _c /\ s = nth witness (head witness _c :: c) i /\ padded = cbc_dec AESi _ek (head witness _c) (take i c)) (size c - i).
  auto => />.
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  proc.
  inline *.
  wp.
  while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ p = None /\ c = behead _c /\ s = (if 0 < i then nth witness c (i - 1) else head witness _c) /\ padded = cbc_dec AESi _ek (head witness _c) (take i c)) (size c - i).
  auto=> />; smt(take_nth cats1 cbc_dec_rcons size_take nth_take xorbC size_ge0).
  auto=> />; smt(take_size take0).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_2153_mee_decrypt_correct

Run dir: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_decrypt_correct/r01/2026-06-10_2153_mee_decrypt_correct/iteration_1`

t=0: `2026-06-11T04:57:13.500000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc; inline PRPc.PseudoRP.fi MAC.verify | phoare / procedure_entry / procedure_frontier, 1 goal, goal 312 chars | accepted commit |  |
| T0.0-2 | +00:49 | [47.8 s](./views/Tree_0_0/thinking/turn_002.md) | 204 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1692 chars | accepted commit |  |
| T0.0-3 | +01:03 | [13.8 s](./views/Tree_0_0/thinking/turn_003.md) | 195 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ c = behead _c /\ s... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1499 chars | accepted commit |  |
| T0.0-4 | +01:12 | [8.8 s](./views/Tree_0_0/thinking/turn_004.md) | 176 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit auto => /> | phoare / procedure_body / procedure_frontier, 2 goals, goal 866 chars | accepted commit |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:05 | [think](./views/Tree_0_1/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 312 chars | accepted commit |  |
| T0.1-2 | +00:20 | 13.6 s | 375 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline * | phoare / procedure_body / procedure_frontier, 1 goal, goal 1435 chars | accepted commit |  |
| T0.1-3 | +00:26 | [5.8 s](./views/Tree_0_1/thinking/turn_003.md) | 178 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit wp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1692 chars | accepted commit |  |
| T0.1-4 | +00:37 | 10.8 s | 161 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ p = None /\ c = be... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1499 chars | accepted commit |  |
| T0.1-5 | +00:54 | 16.7 s | 254 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit auto=> />; smt(take_nth cats1 cbc_dec_rcons size_take nth_take xorbC size_ge0) | phoare / procedure_body / procedure_frontier, 2 goals, goal 1025 chars | accepted commit |  |
| T0.1-6 | +01:13 | 18.6 s | 375 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit auto=> />; smt(take_size take0) | phoare / procedure_body / procedure_frontier, 1 goal, goal 1971 chars | accepted commit |  |
| T0.1-7 | +01:20 | [6.9 s](./views/Tree_0_1/thinking/turn_007.md) | 142 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.1-8 | +01:28 | 8 s |  | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
