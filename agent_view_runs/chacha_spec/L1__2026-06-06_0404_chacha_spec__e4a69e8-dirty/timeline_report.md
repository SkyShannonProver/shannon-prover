# Agent-View Timeline — `chacha_spec`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_0404_chacha_spec |
| lemma | `chacha_spec` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l1_goal_projection` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 30 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — incomplete — 6 tactic(s) committed, not closed

```easycrypt
proof.
  have htake_xor : forall str, take_xor [] str = [].
  by move=> str; rewrite /take_xor take0.
  proc.
  sp.
  while (OCC.gs = gs0 /\ k = k0 /\ n = n0 /\ c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) (size p).
  move=> bnd.
  (* proof not completed in this run *)
```

### `Tree_0_0_0` — proved

```easycrypt
proof.
  have htake_xor : forall str, take_xor [] str = [].
  by move=> str; rewrite /take_xor take0.
  proc.
  sp.
  while (OCC.gs = gs0 /\ k = k0 /\ n = n0 /\ c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) (size p).
  move=> bnd.
  wp.
  exists* OCC.gs, k, n, i.
  elim* => gsv kv nv iv.
  call (_: k = kv /\ n = nv /\ c = C.ofintd iv /\ OCC.gs = gsv ==> res = cc gsv kv nv (C.ofintd iv)).
  proc; auto => /#.
  skip => />.
  move=> &hr Heq Hne; split; last by smt(size_drop gt0_block_size size_eq0 size_ge0).
  rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 iv p{hr} htake_xor) /take_xor //.
  by rewrite catA.
  skip => />.
  move=> c0 i0 p1; split=> [hi hle|]; first by smt(size_eq0 size_ge0).
  by rewrite (gen_CTR_encrypt_bytes0 take_xor (cc gs0) k0 n0 i0 htake_xor) cats0.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_0404_chacha_spec

Run dir: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d0_chacha_spec/r01/2026-06-06_0404_chacha_spec/iteration_1`

t=0: `2026-06-06T11:09:15.800000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.2 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit have htake_xor : forall str, take_xor [] str = [] | phoare / procedure_entry / procedure_frontier, 1 goal, goal 302 chars | accepted commit |  |
| T0.0-2 | +00:06 | [4.8 s](./views/Tree_0_0/thinking/turn_002.md) | 204 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit by move=> str; rewrite /take_xor take0 | ambient / ambient_logic, 2 goals, goal 222 chars | accepted commit |  |
| T0.0-3 | +00:10 | [3.8 s](./views/Tree_0_0/thinking/turn_003.md) | 193 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 369 chars | accepted commit |  |
| T0.0-4 | +00:17 | [6.8 s](./views/Tree_0_0/thinking/turn_004.md) | 209 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit inline OCC(I).cc | phoare / procedure_body / procedure_frontier, 1 goal, goal 1010 chars | rejected commit: manager reported rejection |  |
| T0.0-5 | +00:25 | [7.9 s](./views/Tree_0_0/thinking/turn_005.md) | 1.1 s | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit inline | phoare / procedure_body / procedure_frontier, 1 goal, goal 1010 chars | rejected commit: manager reported rejection |  |
| T0.0-6 | +00:43 | [16.9 s](./views/Tree_0_0/thinking/turn_006.md) | 1.1 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit sp | phoare / procedure_body / procedure_frontier, 1 goal, goal 1010 chars | accepted commit |  |
| T0.0-7 | +00:53 | [8.8 s](./views/Tree_0_0/thinking/turn_007.md) | 185 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit while (OCC.gs = gs0 /\ k = k0 /\ n = n0 /\ c ++ gen_CTR_encrypt_bytes... | phoare / procedure_body / procedure_frontier, 1 goal, goal 901 chars | accepted commit |  |
| T0.0-8 | +01:14 | [20.8 s](./views/Tree_0_0/thinking/turn_008.md) | 206 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit move=> bnd | phoare / procedure_body / procedure_frontier, 2 goals, goal 814 chars | accepted commit |  |
| T0.0-9 | +01:18 | [3.8 s](./views/Tree_0_0/thinking/turn_009.md) | 203 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit inline OCC(I).cc | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: manager reported rejection |  |
| T0.0-10 | +01:37 | [18.9 s](./views/Tree_0_0/thinking/turn_010.md) | 1.1 s | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit inline | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: manager reported rejection |  |
| T0.0-11 | +02:18 | [40 s](./views/Tree_0_0/thinking/turn_011.md) | 1 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit inline (1) | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: manager reported rejection |  |
| T0.0-12 | +03:44 | [85.1 s](./views/Tree_0_0/thinking/turn_012.md) | 1.9 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit call true | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: proof state unchanged |  |
| T0.0-13 | +04:09 | [22.9 s](./views/Tree_0_0/thinking/turn_013.md) | 1.1 s | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit have cc_spec: phoare[OCC(I).cc : true ==> res = cc OCC.gs k n c] = 1%r | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: proof state unchanged |  |

### Tree-0.0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0.0-1 | +10:38 | [think](./views/Tree_0_0_0/thinking/turn_001.md) | 181 ms | [manager_bootstrap_0_0_0.json](./views/_bootstrap/manager_bootstrap_0_0_0.json) | commit inline OCC(I).cc | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: manager reported rejection |  |
| T0.0.0-2 | +10:46 | [8 s](./views/Tree_0_0_0/thinking/turn_002.md) | 1 s | [turn_001.json](./views/Tree_0_0_0/turn_001.json) · [inline read](./views/Tree_0_0_0/followups/turn_001.md) | commit inline | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | rejected commit: manager reported rejection |  |
| T0.0.0-3 | +11:07 | [20 s](./views/Tree_0_0_0/thinking/turn_003.md) | 1 s | [turn_002.json](./views/Tree_0_0_0/turn_002.json) · [inline read](./views/Tree_0_0_0/followups/turn_002.md) | commit wp | phoare / procedure_body / procedure_frontier, 2 goals, goal 997 chars | accepted commit |  |
| T0.0.0-4 | +11:20 | [11.8 s](./views/Tree_0_0_0/thinking/turn_004.md) | 196 ms | [turn_003.json](./views/Tree_0_0_0/turn_003.json) · [inline read](./views/Tree_0_0_0/followups/turn_003.md) | commit inline * | phoare / procedure_body / procedure_frontier, 2 goals, goal 880 chars | rejected commit: manager reported rejection |  |
| T0.0.0-5 | +12:49 | [88.9 s](./views/Tree_0_0_0/thinking/turn_005.md) | 1.1 s | [turn_004.json](./views/Tree_0_0_0/turn_004.json) · [inline read](./views/Tree_0_0_0/followups/turn_004.md) | commit exists* OCC.gs, k, n, i | phoare / procedure_body / procedure_frontier, 2 goals, goal 880 chars | accepted commit |  |
| T0.0.0-6 | +12:55 | [4.8 s](./views/Tree_0_0_0/thinking/turn_006.md) | 185 ms | [turn_005.json](./views/Tree_0_0_0/turn_005.json) · [inline read](./views/Tree_0_0_0/followups/turn_005.md) | commit elim* => gsv kv nv iv | phoare / procedure_body / procedure_frontier, 2 goals, goal 1003 chars | accepted commit |  |
| T0.0.0-7 | +13:07 | [11.8 s](./views/Tree_0_0_0/thinking/turn_007.md) | 185 ms | [turn_006.json](./views/Tree_0_0_0/turn_006.json) · [inline read](./views/Tree_0_0_0/followups/turn_006.md) | commit call k | phoare / procedure_body / procedure_frontier, 2 goals, goal 967 chars | accepted commit |  |
| T0.0.0-8 | +13:28 | [20.8 s](./views/Tree_0_0_0/thinking/turn_008.md) | 178 ms | [turn_007.json](./views/Tree_0_0_0/turn_007.json) · [inline read](./views/Tree_0_0_0/followups/turn_007.md) | commit proc; auto => /# | phoare / procedure_body / procedure_frontier, 3 goals, goal 406 chars | accepted commit |  |
| T0.0.0-9 | +13:49 | [20.8 s](./views/Tree_0_0_0/thinking/turn_009.md) | 201 ms | [turn_008.json](./views/Tree_0_0_0/turn_008.json) · [inline read](./views/Tree_0_0_0/followups/turn_008.md) | commit skip => /> | phoare / procedure_body / procedure_frontier, 2 goals, goal 1145 chars | accepted commit |  |
| T0.0.0-10 | +14:38 | [48.8 s](./views/Tree_0_0_0/thinking/turn_010.md) | 233 ms | [turn_009.json](./views/Tree_0_0_0/turn_009.json) · [inline read](./views/Tree_0_0_0/followups/turn_009.md) | commit move=> &hr Heq Hne; split; last by smt(size_drop gt0_block_size size_eq0 size_ge0) | ambient / ambient_logic, 2 goals, goal 719 chars | accepted commit |  |
| T0.0.0-11 | +15:06 | [27.8 s](./views/Tree_0_0_0/thinking/turn_011.md) | 244 ms | [turn_010.json](./views/Tree_0_0_0/turn_010.json) · [inline read](./views/Tree_0_0_0/followups/turn_010.md) | commit rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 iv p... | ambient / ambient_logic, 2 goals, goal 725 chars | accepted commit |  |
| T0.0.0-12 | +15:18 | [11.8 s](./views/Tree_0_0_0/thinking/turn_012.md) | 182 ms | [turn_011.json](./views/Tree_0_0_0/turn_011.json) · [inline read](./views/Tree_0_0_0/followups/turn_011.md) | commit by rewrite catA | ambient / ambient_logic, 2 goals, goal 1032 chars | accepted commit |  |
| T0.0.0-13 | +15:41 | [22.8 s](./views/Tree_0_0_0/thinking/turn_013.md) | 186 ms | [turn_012.json](./views/Tree_0_0_0/turn_012.json) · [inline read](./views/Tree_0_0_0/followups/turn_012.md) | commit skip => /> | phoare / procedure_body / procedure_frontier, 1 goal, goal 1127 chars | accepted commit |  |
| T0.0.0-14 | +16:12 | [30.8 s](./views/Tree_0_0_0/thinking/turn_014.md) | 236 ms | [turn_013.json](./views/Tree_0_0_0/turn_013.json) · [inline read](./views/Tree_0_0_0/followups/turn_013.md) | commit move=> c0 i0 p1; split=> [hi hle\|]; first by smt(size_eq0 size_ge0) | ambient / ambient_logic, 1 goal, goal 600 chars | accepted commit |  |
| T0.0.0-15 | +16:22 | [9.8 s](./views/Tree_0_0_0/thinking/turn_015.md) | 204 ms | [turn_014.json](./views/Tree_0_0_0/turn_014.json) · [inline read](./views/Tree_0_0_0/followups/turn_014.md) | commit by rewrite (gen_CTR_encrypt_bytes0 take_xor (cc gs0) k0 n0 i0 htake_x... | ambient / ambient_logic, 1 goal, goal 422 chars | accepted commit |  |
| T0.0.0-16 | +16:26 | [3.8 s](./views/Tree_0_0_0/thinking/turn_016.md) | 193 ms | [turn_015.json](./views/Tree_0_0_0/turn_015.json) · [inline read](./views/Tree_0_0_0/followups/turn_015.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0.0-17 | +16:36 | 10 s |  | [turn_016.json](./views/Tree_0_0_0/turn_016.json) · [inline read](./views/Tree_0_0_0/followups/turn_016.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
