# Agent-View Timeline — `chacha_spec`

| field | value |
|---|---|
| commit | `e4a69e8` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-06_1533_chacha_spec |
| lemma | `chacha_spec` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 41 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  while (k = k0 /\ n = n0 /\ OCC.gs = gs0 /\ 1 <= i /\ c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) (size p).
  move=> sz; inline OCC(I).cc; wp; skip.
  move=> &hr [[H1 Hne] Hsz]; move: H1 => [eqk [eqn [eqgs [ge1i Heq]]]].
  rewrite eqk eqn eqgs /=.
  have Hnil: forall s, take_xor [] s = [].
  move=> s; rewrite /take_xor /= take0 //.
  split; last by smt(size_drop size_ge0 gt0_block_size size_eq0).
  split; first by smt(). rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 i{hr} p{hr} Hnil) /take_xor catA //.
  wp; skip.
  have Hnil: forall s, take_xor [] s = [].
  move=> s; rewrite /take_xor /= take0 //.
  move=> &hr /= [eqk [eqn [eqp eqgs]]].
  split; first by rewrite eqk eqn eqgs eqp /=. move=> c0 i0 p1; split; first by smt(size_ge0 size_eq0). by move=> ->; rewrite (gen_CTR_encrypt_bytes0 take_xor (cc gs0) k0 n0 i0 Hnil) cats0; smt().
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-06_1533_chacha_spec

Run dir: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1`

t=0: `2026-06-06T22:34:21.901000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 99 ms | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect lemma_index | phoare / procedure_entry / procedure_frontier, 1 goal, goal 302 chars | read-only inspect |  |
| T0.0-2 | +00:40 | [39.9 s](./views/Tree_0_0/thinking/turn_002.md) | 102 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | inspect tactic_forms | phoare / procedure_entry / procedure_frontier, 1 goal, goal 302 chars | read-only inspect |  |
| T0.0-3 | +00:47 | [6.9 s](./views/Tree_0_0/thinking/turn_003.md) | 1.1 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 302 chars | accepted commit |  |
| T0.0-4 | +00:56 | [7.9 s](./views/Tree_0_0/thinking/turn_004.md) | 1.1 s | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | probe inline OCC(I).cc | phoare / procedure_body / procedure_frontier, 1 goal, goal 956 chars | rejected probe: manager reported rejection |  |
| T0.0-5 | +01:02 | [4.8 s](./views/Tree_0_0/thinking/turn_005.md) | 181 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | probe inline | phoare / procedure_body / procedure_frontier, 1 goal, goal 956 chars | rejected probe: manager reported rejection |  |
| T0.0-6 | +01:17 | [14.9 s](./views/Tree_0_0/thinking/turn_006.md) | 101 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | inspect diagnose | phoare / procedure_body / procedure_frontier, 1 goal, goal 956 chars | read-only inspect |  |
| T0.0-7 | +01:47 | [29.8 s](./views/Tree_0_0/thinking/turn_007.md) | 178 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | probe while (k = k0 /\ n = n0 /\ OCC.gs = gs0 /\ 1 <= i /\ c ++ gen_CTR_enc... | phoare / procedure_body / procedure_frontier, 1 goal, goal 956 chars | accepted probe |  |
| T0.0-8 | +01:57 | [9.8 s](./views/Tree_0_0/thinking/turn_008.md) | 201 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit while (k = k0 /\ n = n0 /\ OCC.gs = gs0 /\ 1 <= i /\ c ++ gen_CTR_enc... | phoare / procedure_body / procedure_frontier, 1 goal, goal 956 chars | accepted commit |  |
| T0.0-9 | +02:25 | [28 s](./views/Tree_0_0/thinking/turn_009.md) | 1 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | probe move=> sz; inline OCC(I).cc | phoare / procedure_body / procedure_frontier, 2 goals, goal 805 chars | accepted probe |  |
| T0.0-10 | +02:49 | [22.8 s](./views/Tree_0_0/thinking/turn_010.md) | 194 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | probe move=> sz; inline OCC(I).cc; wp; skip | phoare / procedure_body / procedure_frontier, 2 goals, goal 805 chars | accepted probe |  |
| T0.0-11 | +03:53 | [63.8 s](./views/Tree_0_0/thinking/turn_011.md) | 188 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit move=> sz; inline OCC(I).cc; wp; skip | phoare / procedure_body / procedure_frontier, 2 goals, goal 805 chars | accepted commit |  |
| T0.0-12 | +04:13 | [20 s](./views/Tree_0_0/thinking/turn_012.md) | 1 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | probe move=> &hr [[[eqk eqn eqgs ge1i Heq] Hne] Hsz]; rewrite eqk eqn eqgs /= | ambient / ambient_logic, 2 goals, goal 837 chars | rejected probe: nothing to introduce |  |
| T0.0-13 | +04:43 | [28.8 s](./views/Tree_0_0/thinking/turn_013.md) | 189 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | probe move=> &hr Hpre | ambient / ambient_logic, 2 goals, goal 837 chars | accepted probe |  |
| T0.0-14 | +05:16 | [32.8 s](./views/Tree_0_0/thinking/turn_014.md) | 207 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | probe move=> &hr [[[eqk eqn eqgs ge1i Heq] Hne] Hsz] | ambient / ambient_logic, 2 goals, goal 837 chars | rejected probe: nothing to introduce |  |
| T0.0-15 | +05:36 | [19.8 s](./views/Tree_0_0/thinking/turn_015.md) | 190 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | probe move=> &hr [[H1 Hne] Hsz] | ambient / ambient_logic, 2 goals, goal 837 chars | accepted probe |  |
| T0.0-16 | +05:56 | [19.8 s](./views/Tree_0_0/thinking/turn_016.md) | 204 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | probe move=> &hr [[H1 Hne] Hsz]; case: H1 => eqk eqn eqgs ge1i Heq | ambient / ambient_logic, 2 goals, goal 837 chars | rejected probe: nothing to introduce |  |
| T0.0-17 | +06:31 | [34.8 s](./views/Tree_0_0/thinking/turn_017.md) | 209 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | probe move=> &hr [[[eqk eqn eqgs Hrest] Hne] Hsz] | ambient / ambient_logic, 2 goals, goal 837 chars | accepted probe |  |
| T0.0-18 | +07:35 | [63.8 s](./views/Tree_0_0/thinking/turn_018.md) | 223 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | probe move=> &hr [[H1 Hne] Hsz]; move: H1 => [eqk [eqn [eqgs [ge1i Heq]]]] | ambient / ambient_logic, 2 goals, goal 837 chars | accepted probe |  |
| T0.0-19 | +07:41 | [5.8 s](./views/Tree_0_0/thinking/turn_019.md) | 209 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit move=> &hr [[H1 Hne] Hsz]; move: H1 => [eqk [eqn [eqgs [ge1i Heq]]]] | ambient / ambient_logic, 2 goals, goal 837 chars | accepted commit |  |
| T0.0-20 | +07:51 | [10 s](./views/Tree_0_0/thinking/turn_020.md) | 1 s | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | probe rewrite eqk eqn eqgs /= | ambient / ambient_logic, 2 goals, goal 892 chars | accepted probe |  |
| T0.0-21 | +08:34 | [41.8 s](./views/Tree_0_0/thinking/turn_021.md) | 205 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit rewrite eqk eqn eqgs /= | ambient / ambient_logic, 2 goals, goal 892 chars | accepted commit |  |
| T0.0-22 | +09:20 | [46 s](./views/Tree_0_0/thinking/turn_022.md) | 1 s | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | probe have Hnil: forall (s:block), take_xor [] s = [] by move=> s; rewrite /take_xor /= | ambient / ambient_logic, 2 goals, goal 827 chars | rejected probe: manager reported rejection |  |
| T0.0-23 | +09:38 | [16.8 s](./views/Tree_0_0/thinking/turn_023.md) | 209 ms | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | probe have Hnil: forall s, take_xor [] s = [] by move=> s; rewrite /take_xor /= | ambient / ambient_logic, 2 goals, goal 827 chars | rejected probe: manager reported rejection |  |
| T0.0-24 | +09:44 | [5.9 s](./views/Tree_0_0/thinking/turn_024.md) | 73 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | inspect diagnose | ambient / ambient_logic, 2 goals, goal 827 chars | read-only inspect |  |
| T0.0-25 | +10:00 | [15.8 s](./views/Tree_0_0/thinking/turn_025.md) | 205 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit have Hnil: forall s, take_xor [] s = [] | ambient / ambient_logic, 2 goals, goal 827 chars | accepted commit |  |
| T0.0-26 | +10:04 | [4 s](./views/Tree_0_0/thinking/turn_026.md) | 1 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | probe move=> s; rewrite /take_xor /= | ambient / ambient_logic, 3 goals, goal 569 chars | accepted probe |  |
| T0.0-27 | +10:12 | [6.8 s](./views/Tree_0_0/thinking/turn_027.md) | 204 ms | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | probe move=> s; rewrite /take_xor /= take0 | ambient / ambient_logic, 3 goals, goal 569 chars | accepted probe |  |
| T0.0-28 | +10:16 | [3.8 s](./views/Tree_0_0/thinking/turn_028.md) | 188 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit move=> s; rewrite /take_xor /= take0 // | ambient / ambient_logic, 3 goals, goal 569 chars | accepted commit |  |
| T0.0-29 | +10:29 | [12.9 s](./views/Tree_0_0/thinking/turn_029.md) | 1.1 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | probe split; last by smt(size_drop size_ge0 gt0_block_size size_eq0) | ambient / ambient_logic, 2 goals, goal 872 chars | accepted probe |  |
| T0.0-30 | +10:38 | [7.8 s](./views/Tree_0_0/thinking/turn_030.md) | 243 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit split; last by smt(size_drop size_ge0 gt0_block_size size_eq0) | ambient / ambient_logic, 2 goals, goal 872 chars | accepted commit |  |
| T0.0-31 | +10:54 | [15.8 s](./views/Tree_0_0/thinking/turn_031.md) | 1.2 s | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | probe split; first by smt(). rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 i{hr}... | ambient / ambient_logic, 2 goals, goal 827 chars | accepted probe |  |
| T0.0-32 | +11:09 | [13.7 s](./views/Tree_0_0/thinking/turn_032.md) | 256 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit split; first by smt(). rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 i{hr}... | ambient / ambient_logic, 2 goals, goal 827 chars | accepted commit |  |
| T0.0-33 | +11:27 | [17.8 s](./views/Tree_0_0/thinking/turn_033.md) | 1.2 s | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | probe wp; skip | phoare / procedure_body / procedure_frontier, 1 goal, goal 1157 chars | accepted probe |  |
| T0.0-34 | +11:59 | [30.8 s](./views/Tree_0_0/thinking/turn_034.md) | 196 ms | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | commit wp; skip | phoare / procedure_body / procedure_frontier, 1 goal, goal 1157 chars | accepted commit |  |
| T0.0-35 | +12:04 | [4.8 s](./views/Tree_0_0/thinking/turn_035.md) | 205 ms | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | commit have Hnil: forall s, take_xor [] s = [] | ambient / ambient_logic, 1 goal, goal 1064 chars | accepted commit |  |
| T0.0-36 | +12:08 | 3.8 s | 208 ms | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit move=> s; rewrite /take_xor /= take0 // | ambient / ambient_logic, 2 goals, goal 218 chars | accepted commit |  |
| T0.0-37 | +12:37 | [28.8 s](./views/Tree_0_0/thinking/turn_037.md) | 1.2 s | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | probe move=> &hr /= [eqk [eqn [eqp eqgs]]] | ambient / ambient_logic, 1 goal, goal 1109 chars | accepted probe |  |
| T0.0-38 | +13:20 | [41.8 s](./views/Tree_0_0/thinking/turn_038.md) | 199 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit move=> &hr /= [eqk [eqn [eqp eqgs]]] | ambient / ambient_logic, 1 goal, goal 1109 chars | accepted commit |  |
| T0.0-39 | +13:26 | [5.7 s](./views/Tree_0_0/thinking/turn_039.md) | 1.3 s | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | probe split; first by rewrite eqk eqn eqgs eqp /=. move=> c0 i0 p1; split; first by smt(size_ge0 si... | ambient / ambient_logic, 1 goal, goal 1056 chars | accepted probe |  |
| T0.0-40 | +13:50 | [22.7 s](./views/Tree_0_0/thinking/turn_040.md) | 329 ms | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | commit split; first by rewrite eqk eqn eqgs eqp /=. move=> c0 i0 p1; split; first by smt(size_ge0 si... | ambient / ambient_logic, 1 goal, goal 1056 chars | accepted commit |  |
| T0.0-41 | +13:55 | [4.8 s](./views/Tree_0_0/thinking/turn_041.md) | 210 ms | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
