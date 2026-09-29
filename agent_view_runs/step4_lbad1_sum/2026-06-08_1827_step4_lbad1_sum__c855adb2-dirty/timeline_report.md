# Agent-View Timeline — `step4_lbad1_sum`

| field | value |
|---|---|
| commit | `c855adb2` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-08_1827_step4_lbad1_sum |
| lemma | `step4_lbad1_sum` |
| source file | `eval/examples/ChaChaPoly/chacha_poly.ec` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 42 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  have HP := LP.list_partitioning UFCMA_l tt.
  have EQ := HP (fun _ (g: glob UFCMA_l) _ => size g.`6 <= qdec /\ exists (p:tag*tag), p \in g.`6 /\ p.`1 = p.`2) (fun _ (g: glob UFCMA_l) _ => find (fun (p:tag*tag) => p.`1 = p.`2) g.`6) (iota_ 0 qdec) &m (iota_uniq 0 qdec).
  move: EQ => /= EQ.
  have R0 : Pr[UFCMA_l.f() @ &m : (size UFCMA_l.lbad1 <= qdec /\ exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\ ! (find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 \in iota_ 0 qdec)] = Pr[UFCMA_l.f() @ &m : false].
  rewrite Pr[mu_eq].
  move=> &hr; split=> [|//]; move=> [[hsz [p [hp hpp]]] hnotin].
  have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by apply/List.hasP; exists p; smt().
  have hf := has_find (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}; have hg := find_ge0 (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}; move: hnotin; rewrite mem_iota; smt().
  trivial.
  rewrite EQ.
  rewrite R0.
  rewrite Pr[mu_false].
  rewrite RField.addr0.
  apply StdBigop.Bigreal.ler_sum.
  move=> a _ /=.
  rewrite Pr[mu_sub].
  move=> &hr [[hsz [p [hp hpp]]] hfind].
  have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by (apply/List.hasP; exists p; smt()); rewrite -hfind; apply (nth_find (w1,w2) (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} hh).
  rewrite -hfind; apply (nth_find (w1,w2) (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} hh).
  trivial.
  qed.
```

### `Tree_0_1` — proved

```easycrypt
proof.
  have HP := LP.list_partitioning UFCMA_l tt.
  have EQ := HP (fun _ (g: glob UFCMA_l) _ => size g.`6 <= qdec /\ exists (p:tag*tag), p \in g.`6 /\ p.`1 = p.`2) (fun _ (g: glob UFCMA_l) _ => find (fun (p:tag*tag) => p.`1 = p.`2) g.`6) (iota_ 0 qdec) &m (iota_uniq 0 qdec).
  move: EQ => /= EQ.
  have R0 : Pr[UFCMA_l.f() @ &m : (size UFCMA_l.lbad1 <= qdec /\ exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\ ! (find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 \in iota_ 0 qdec)] = Pr[UFCMA_l.f() @ &m : false].
  rewrite Pr[mu_eq].
  move=> &hr; split=> [|//]; move=> [[hsz [p [hp hpp]]] hnotin].
  have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by apply/List.hasP; exists p; smt().
  have hf := has_find (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}; have hg := find_ge0 (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}; move: hnotin; rewrite mem_iota; smt().
  trivial.
  rewrite EQ.
  rewrite R0.
  rewrite Pr[mu_false].
  rewrite RField.addr0.
  apply StdBigop.Bigreal.ler_sum.
  move=> a _ /=.
  rewrite Pr[mu_sub].
  move=> &hr [[hsz [p [hp hpp]]] hfind].
  have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by (apply/List.hasP; exists p; smt()); rewrite -hfind; apply (nth_find (w1,w2) (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} hh).
  rewrite -hfind; apply (nth_find (w1,w2) (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} hh).
  trivial.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-08_1827_step4_lbad1_sum

Run dir: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1`

t=0: `2026-06-09T01:29:56.500000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 |  | 3.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit have HP := LP.list_partitioning UFCMA_l tt (fun (_:unit) (g:glob UFCM... | probability / pr / probability, 1 goal, goal 393 chars | rejected commit: [error] This proof-term argument is not a valid formula: |  |
| T0.0-2 | +00:26 | 22.1 s | 1.9 s | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | lookup LP.list_partitioning | probability / pr / probability, 1 goal, goal 393 chars | lookup result |  |
| T0.0-3 | +00:54 | 26 s | 2 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit have HP := LP.list_partitioning UFCMA_l tt (fun _ g _ => size g <= qd... | probability / pr / probability, 1 goal, goal 393 chars | rejected commit: [error] This expression has type |  |
| T0.0-4 | +01:13 | 17.5 s | 476 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | inspect diagnose | probability / pr / probability, 1 goal, goal 393 chars | read-only inspect |  |
| T0.0-5 | +01:58 | 44.4 s | 570 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit have HP := LP.list_partitioning UFCMA_l tt | probability / pr / probability, 1 goal, goal 393 chars | accepted commit |  |
| T0.0-6 | +03:33 | 94.4 s | 609 ms | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | commit have EQ := HP (fun _ (g: glob UFCMA_l) _ => size g.`6 <= qdec /\ exis... | probability / pr / probability, 1 goal, goal 2332 chars | accepted commit |  |
| T0.0-7 | +03:52 | 18.5 s | 540 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit move: EQ => /= EQ | probability / pr / probability, 1 goal, goal 5600 chars | accepted commit |  |
| T0.0-8 | +06:04 | 131 s | 5 s | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit have R0 : Pr[UFCMA_l.f() @ &m : (size UFCMA_l.lbad1 <= qdec /\ exists (p : tag * tag), (p \in... | probability / pr / probability, 1 goal, goal 3010 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-9 | +06:18 | 9.4 s | 560 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit have R0 : Pr[UFCMA_l.f() @ &m : (size UFCMA_l.lbad1 <= qdec /\ exists... | probability / pr / probability, 1 goal, goal 3010 chars | accepted commit |  |
| T0.0-10 | +06:27 | 8.8 s | 219 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit rewrite Pr[mu_eq] | probability / pr / probability, 2 goals, goal 2977 chars | accepted commit |  |
| T0.0-11 | +07:01 | 33.4 s | 4.6 s | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit move=> &hr; rewrite mem_iota; smt(hasP has_find find_ge0) | ambient / ambient_logic, 3 goals, goal 2955 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.0-12 | +08:01 | 55.6 s | 1.4 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit move=> &hr; split=> //; case=> [[hsz hex] hnotin]; move: hex => [p [hp hpp]]; have hh: has (f... | ambient / ambient_logic, 3 goals, goal 2955 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-13 | +09:53 | 110.8 s | 213 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit move=> &hr; split=> [\|//]; move=> [[hsz [p [hp hpp]]] hnotin] | ambient / ambient_logic, 3 goals, goal 2955 chars | accepted commit |  |
| T0.0-14 | +10:09 | 15.8 s | 1.2 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | lookup hasP | ambient / ambient_logic, 3 goals, goal 2955 chars | lookup result |  |
| T0.0-15 | +10:25 | 14.7 s | 267 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by apply/List.hasP; exists... | ambient / ambient_logic, 3 goals, goal 2955 chars | accepted commit |  |
| T0.0-16 | +10:36 | 10.7 s | 262 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit have hf := has_find (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}; have hg := find_ge... | ambient / ambient_logic, 3 goals, goal 3021 chars | accepted commit |  |
| T0.0-17 | +10:42 | 5.4 s | 552 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit trivial | ambient / ambient_logic, 2 goals, goal 2739 chars | accepted commit |  |
| T0.0-18 | +11:29 | 46.2 s | 1.8 s | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit rewrite EQ R0 Pr[mu_false] addr0 | probability / pr / probability, 1 goal, goal 3277 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-19 | +11:47 | 16.8 s | 232 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit rewrite EQ | probability / pr / probability, 1 goal, goal 3277 chars | accepted commit |  |
| T0.0-20 | +11:52 | 4.8 s | 231 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit rewrite R0 | probability / pr / probability, 1 goal, goal 3634 chars | accepted commit |  |
| T0.0-21 | +11:58 | 5.5 s | 1.5 s | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit rewrite Pr[mu_false] addr0 | probability / pr / probability, 1 goal, goal 3451 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-22 | +12:12 | 12.8 s | 228 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit rewrite Pr[mu_false] | probability / pr / probability, 1 goal, goal 3451 chars | accepted commit |  |
| T0.0-23 | +12:21 | 8.5 s | 1.5 s | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | commit rewrite addr0 | probability / pr / probability, 1 goal, goal 3426 chars | rejected commit: [error] nothing to rewrite |  |
| T0.0-24 | +13:04 | 41.8 s | 226 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit rewrite RField.addr0 | probability / pr / probability, 1 goal, goal 3426 chars | accepted commit |  |
| T0.0-25 | +13:16 | 11.8 s | 1.2 s | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | lookup ler_sum | probability / pr / probability, 1 goal, goal 3420 chars | lookup result |  |
| T0.0-26 | +13:44 | 26.5 s | 1.5 s | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit apply ler_sum => a _ | probability / pr / probability, 1 goal, goal 3420 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-27 | +14:18 | 32.4 s | 1.6 s | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | commit apply ler_sum | probability / pr / probability, 1 goal, goal 3420 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.0-28 | +15:02 | 42.5 s | 1.5 s | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit apply (ler_sum _ (fun (a : int) => Pr[UFCMA_l.f() @ &m : (size UFCMA_... | probability / pr / probability, 1 goal, goal 3420 chars | rejected commit: [error] This expression has type |  |
| T0.0-29 | +15:47 | 43.4 s | 1.6 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | commit apply Bigreal.ler_sum | probability / pr / probability, 1 goal, goal 3420 chars | rejected commit: [error] unknown lemma `Bigreal.ler_sum' |  |
| T0.0-30 | +16:28 | 39.8 s | 236 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit apply StdBigop.Bigreal.ler_sum | probability / pr / probability, 1 goal, goal 3420 chars | accepted commit |  |
| T0.0-31 | +16:53 | 24.4 s | 643 ms | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | commit move=> a _ /= | probability / pr / probability, 1 goal, goal 3387 chars | accepted commit |  |
| T0.0-32 | +17:20 | 26.8 s | 238 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | commit rewrite Pr[mu_sub] | probability / pr / probability, 1 goal, goal 3281 chars | accepted commit |  |
| T0.0-33 | +17:49 | 28.7 s | 274 ms | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | commit move=> &hr [[hsz [p [hp hpp]]] hfind] | ambient / ambient_logic, 2 goals, goal 3280 chars | accepted commit |  |
| T0.0-34 | +17:59 | 9.5 s | 1.5 s | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | lookup nth_find | ambient / ambient_logic, 2 goals, goal 3272 chars | lookup result |  |
| T0.0-35 | +18:12 | 11.7 s | 287 ms | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | commit have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by (apply/List.hasP; exist... | ambient / ambient_logic, 2 goals, goal 3272 chars | accepted commit |  |
| T0.0-36 | +19:10 | 57.7 s | 257 ms | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit rewrite -hfind; apply (nth_find (w1,w2) (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}... | ambient / ambient_logic, 2 goals, goal 3338 chars | accepted commit |  |
| T0.0-37 | +19:16 | 5.8 s | 226 ms | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | commit trivial | ambient / ambient_logic, 1 goal, goal 2998 chars | accepted commit |  |
| T0.0-38 | +19:19 | 2.8 s | 208 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-39 | +19:22 | 2 s |  | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +04:32 | [think](./views/Tree_0_1/thinking/turn_001.md) | 202 ms | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | inspect lemma_hints | probability / pr / probability, 1 goal, goal 393 chars | read-only inspect |  |
| T0.1-2 | +04:40 | [7.6 s](./views/Tree_0_1/thinking/turn_002.md) | 1.4 s | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | lookup LP.list_partitioning | probability / pr / probability, 1 goal, goal 393 chars | lookup result |  |
| T0.1-3 | +07:46 | 185 s |  | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | unknown | probability / pr / probability, 1 goal, goal 393 chars | repair / unhealthy |  |
