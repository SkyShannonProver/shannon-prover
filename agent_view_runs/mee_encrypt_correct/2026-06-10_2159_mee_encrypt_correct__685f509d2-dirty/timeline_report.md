# Agent-View Timeline — `mee_encrypt_correct`

| field | value |
|---|---|
| commit | `685f509d2` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-10_2159_mee_encrypt_correct |
| lemma | `mee_encrypt_correct` |
| source file | `eval/examples/MEE-CBC/FunctionalSpec.ec` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 34 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — proved

```easycrypt
proof.
  proc.
  inline *.
  seq 8 : (s :: cbc_enc AES _ek s p' = _c) (mu1 (dmap dblock (fun iv => iv :: mee_enc AES hmac_sha256 _ek _mk iv _p)) _c) 1%r _ 0%r (ek = _ek /\ p' = pad _p (hmac_sha256 _mk _p) /\ c = [s] /\ i = 0).
  auto => />.
  wp; rnd (fun v => v :: cbc_enc AES _ek v p' = _c); wp; skip => />.
  by rewrite dmap1E /(\o) /pred1 /mee_enc /=.
  conseq (_: true ==> true) (_: _ ==> _) => //=.
  while (0 <= i <= size p' /\ ek = _ek /\ size c = i + 1 /\ c = head witness c :: cbc_enc AES _ek (head witness c) (take i p') /\ s = nth witness c i /\ head witness c :: cbc_enc AES _ek (head witness c) p' = _c).
  auto => />.
  smt(cbc_enc_rcons take_nth size_take cats1 cat_cons size_cat nth_rcons size_cbc_enc).
  auto => />; smt(take0 take_size size_ge0).
  while true (size p' - i); auto => /#.
  hoare.
  while (0 <= i <= size p' /\ ek = _ek /\ size c = i + 1 /\ c = head witness c :: cbc_enc AES _ek (head witness c) (take i p') /\ s = nth witness c i /\ head witness c :: cbc_enc AES _ek (head witness c) p' <> _c).
  auto => />; smt(cbc_enc_rcons take_nth size_take cats1 cat_cons size_cat nth_rcons size_cbc_enc).
  auto => />; smt(take0 take_size size_ge0).
  done.
  qed.
```

### `Tree_0_1` — incomplete — 9 tactic(s) committed, not closed

```easycrypt
proof.
  proc.
  inline MAC.tag PRPc.PseudoRP.f.
  seq 6: (s :: cbc_enc AES _ek s p' = _c) (mu1 (dmap dblock (fun (iv : block) => iv :: mee_enc AES hmac_sha256 _ek _mk iv _p)) _c) 1%r _ 0%r (ek = _ek /\ p' = pad _p (hmac_sha256 _mk _p)).
  auto => />.
  rnd; auto => />.
  by rewrite dmap1E; apply mu_eq => x; rewrite /(\o) /pred1 /mee_enc /=.
  conseq (_: true ==> true) (_: _ ==> _) => //=.
  wp; while (0 <= i <= size p' /\ ek = _ek /\ head witness _c :: cbc_enc AES _ek (head witness _c) p' = _c /\ c = head witness _c :: cbc_enc AES _ek (head witness _c) (take i p') /\ s = nth witness c i).
  auto => />.
  (* proof not completed in this run *)
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-10_2159_mee_encrypt_correct

Run dir: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_encrypt_correct/r01/2026-06-10_2159_mee_encrypt_correct/iteration_1`

t=0: `2026-06-11T05:05:26.500000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.5 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 425 chars | accepted commit |  |
| T0.0-2 | +00:25 | 23.8 s | 158 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | commit inline * | phoare / procedure_body / procedure_frontier, 1 goal, goal 1190 chars | accepted commit |  |
| T0.0-3 | +00:39 | 13.8 s | 178 ms | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | commit seq 8 : (s :: cbc_enc AES _ek s p' = _c) (mu1 (dmap dblock (fun iv =>... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1243 chars | accepted commit |  |
| T0.0-4 | +00:51 | [11.8 s](./views/Tree_0_0/thinking/turn_004.md) | 184 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit auto => /> | hoare / procedure_body / procedure_frontier, 5 goals, goal 722 chars | accepted commit |  |
| T0.0-5 | +01:05 | 13.8 s | 207 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit auto => /> | phoare / procedure_body / procedure_frontier, 4 goals, goal 845 chars | accepted commit |  |
| T0.0-6 | +01:26 | 20.6 s | 1.4 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | undo_last_step | ambient / ambient_logic, 4 goals, goal 523 chars | undo result |  |
| T0.0-7 | +01:44 | [16.4 s](./views/Tree_0_0/thinking/turn_007.md) | 2.6 s | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit wp; rnd (fun v => v :: cbc_enc AES _ek v p' = _c); skip => /> | phoare / procedure_body / procedure_frontier, 4 goals, goal 832 chars | rejected commit: [error] instruction list is not empty |  |
| T0.0-8 | +01:56 | [9.8 s](./views/Tree_0_0/thinking/turn_008.md) | 194 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | commit wp; rnd (fun v => v :: cbc_enc AES _ek v p' = _c); wp; skip => /> | phoare / procedure_body / procedure_frontier, 4 goals, goal 832 chars | accepted commit |  |
| T0.0-9 | +02:09 | [12.8 s](./views/Tree_0_0/thinking/turn_009.md) | 160 ms | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | commit by rewrite dmap1E /(\o) /pred1 /mee_enc /= | ambient / ambient_logic, 4 goals, goal 372 chars | accepted commit |  |
| T0.0-10 | +02:19 | [9.8 s](./views/Tree_0_0/thinking/turn_010.md) | 174 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | commit conseq (_: true ==> true) (_: _ ==> _) => //= | phoare / procedure_body / procedure_frontier, 3 goals, goal 781 chars | accepted commit |  |
| T0.0-11 | +02:35 | [15.8 s](./views/Tree_0_0/thinking/turn_011.md) | 157 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | commit while (0 <= i <= size p' /\ ek = _ek /\ size c = i + 1 /\ c = head wi... | hoare / procedure_body / procedure_frontier, 4 goals, goal 764 chars | accepted commit |  |
| T0.0-12 | +02:58 | [22.8 s](./views/Tree_0_0/thinking/turn_012.md) | 220 ms | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit auto => /> | hoare / procedure_body / procedure_frontier, 5 goals, goal 1148 chars | accepted commit |  |
| T0.0-13 | +03:20 | 21 s | 3 s | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | commit smt(cbc_enc_rcons take_nth size_take cats1 rcons_cons size_cat nth_rcons size_cbc_enc) | ambient / ambient_logic, 5 goals, goal 2679 chars | rejected commit: [error] cannot find lemma `rcons_cons' |  |
| T0.0-14 | +03:35 | [12.8 s](./views/Tree_0_0/thinking/turn_014.md) | 227 ms | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | commit smt(cbc_enc_rcons take_nth size_take cats1 cat_cons size_cat nth_rcons size_cbc_enc) | ambient / ambient_logic, 5 goals, goal 2679 chars | accepted commit |  |
| T0.0-15 | +03:50 | [14.2 s](./views/Tree_0_0/thinking/turn_015.md) | 1.8 s | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | commit auto => />; smt(take0 take_size size_ge0) | hoare / procedure_body / procedure_frontier, 4 goals, goal 1141 chars | accepted commit |  |
| T0.0-16 | +04:00 | [8.8 s](./views/Tree_0_0/thinking/turn_016.md) | 214 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit while true (size p' - i); auto => /# | phoare / procedure_body / procedure_frontier, 3 goals, goal 679 chars | accepted commit |  |
| T0.0-17 | +04:14 | [13.8 s](./views/Tree_0_0/thinking/turn_017.md) | 170 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit hoare | phoare / procedure_body / procedure_frontier, 2 goals, goal 782 chars | accepted commit |  |
| T0.0-18 | +04:22 | [7.8 s](./views/Tree_0_0/thinking/turn_018.md) | 171 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | commit while (0 <= i <= size p' /\ ek = _ek /\ size c = i + 1 /\ c = head wi... | hoare / procedure_body / procedure_frontier, 2 goals, goal 766 chars | accepted commit |  |
| T0.0-19 | +04:29 | 6.8 s | 211 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | commit auto => />; smt(cbc_enc_rcons take_nth size_take cats1 cat_cons size_cat nth_rcons size_cbc_enc) | hoare / procedure_body / procedure_frontier, 3 goals, goal 1153 chars | accepted commit |  |
| T0.0-20 | +04:43 | 13.7 s | 349 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | commit auto => />; smt(take0 take_size size_ge0) | hoare / procedure_body / procedure_frontier, 2 goals, goal 1148 chars | accepted commit |  |
| T0.0-21 | +04:59 | [15.8 s](./views/Tree_0_0/thinking/turn_021.md) | 162 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit done | ambient / ambient_logic, 1 goal, goal 498 chars | accepted commit |  |
| T0.0-22 | +05:05 | [5.8 s](./views/Tree_0_0/thinking/turn_022.md) | 168 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-23 | +05:12 | 7 s |  | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:23 |  | 1.4 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit proc | phoare / procedure_entry / procedure_frontier, 1 goal, goal 425 chars | accepted commit |  |
| T0.1-2 | +00:34 | 9.9 s | 148 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit inline MAC.tag PRPc.PseudoRP.f | phoare / procedure_body / procedure_frontier, 1 goal, goal 1190 chars | accepted commit |  |
| T0.1-3 | +00:52 | 18 s |  | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | unknown | phoare / procedure_body / procedure_frontier, 1 goal, goal 1243 chars | repair / unhealthy |  |
| T0.1-4 | +01:22 | 29.8 s | 160 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit seq 6: (s :: cbc_enc AES _ek s p' = _c) (mu1 (dmap dblock (fun (iv :... | phoare / procedure_body / procedure_frontier, 1 goal, goal 1243 chars | accepted commit |  |
| T0.1-5 | +01:42 | 19.9 s | 146 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit auto => /> | hoare / procedure_body / procedure_frontier, 5 goals, goal 632 chars | accepted commit |  |
| T0.1-6 | +02:10 | 27.8 s | 160 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit rnd; auto => /> | phoare / procedure_body / procedure_frontier, 4 goals, goal 775 chars | accepted commit |  |
| T0.1-7 | +02:30 | 19.8 s | 171 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit by rewrite dmap1E; apply mu_eq => x; rewrite /(\o) /pred1 /mee_enc /= | ambient / ambient_logic, 4 goals, goal 372 chars | accepted commit |  |
| T0.1-8 | +02:41 | 10.8 s | 172 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit conseq (_: true ==> true) (_: _ ==> _) => //= | phoare / procedure_body / procedure_frontier, 3 goals, goal 841 chars | accepted commit |  |
| T0.1-9 | +03:31 | 49.4 s | 1.6 s | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit wp; while (0 <= i <= size p' /\ ek = _ek /\ head witness _c :: cbc_enc AES _ek (head witness... | hoare / procedure_body / procedure_frontier, 4 goals, goal 824 chars | accepted commit |  |
| T0.1-10 | +03:54 | 22 s | 6 s | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit auto => />; smt(cbc_enc_rcons take_nth take0 take_size size_take size_cbc_enc nth_rcons cats1... | hoare / procedure_body / procedure_frontier, 5 goals, goal 1122 chars | rejected commit: [error] cannot prove goal (strict) |  |
| T0.1-11 | +04:49 | 48.8 s | 167 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit auto => /> | hoare / procedure_body / procedure_frontier, 5 goals, goal 1122 chars | accepted commit |  |
