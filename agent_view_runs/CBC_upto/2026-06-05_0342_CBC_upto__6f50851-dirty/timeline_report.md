# Agent-View Timeline — `CBC_upto`

| field | value |
|---|---|
| commit | `6f50851` **(dirty/uncommitted)** |
| branch | `HEAD` |
| run time | 2026-06-05_0342_CBC_upto |
| lemma | `CBC_upto` |
| source file | `eval/examples/MEE-CBC/CBC.eca` |
| model | `claude-opus-4-8` |
| surface profile | `l4_checked_action_surface` |
| trees | 1 |
| eval mode | True |
| outcome | proved |
| turns | 114 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

Reconstructed from the committed tactics in the timeline (one block per proof tree).

### `Tree_0_0` — proved

```easycrypt
proof.
  rewrite (doublequery_eq PRFi &m).
  rewrite (doublequery_eq Sample &m).
  rewrite -(DQ_Sample_Compute_pr &m).
  byequiv: DoubleQuery.bad => //=; 2: by smt().
  proc.
  call (_: DoubleQuery.bad, ={DoubleQuery.qs} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ fdom PRFi.m{1} = DoubleQuery.qs{1}, DoubleQuery.bad{1} <=> DoubleQuery.bad{2}).
  exact A_distinguish_ll.
  have f_eq : equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => ={arg} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}) ==> (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => ={res} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})].
  proc.
  case (DoubleQuery.bad{2}).
  conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}); first by smt().
  inline *; auto.
  if{1}; sp; if{1}; auto; smt(dBlock_uffu).
  if=> //=.
  smt().
  conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}); first by smt().
  inline*; auto; sp; if{1}; auto; smt(dBlock_uffu).
  inline*; sp; rcondt{1} 1.
  auto; smt(mem_fdom).
  auto; smt(fdom_set get_set_sameE oget_some).
  proc.
  seq 3 3 : (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => c{1} = c{2} /\ s{1} = s{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})).
  auto; smt(size_ge0).
  while (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => c{1} = c{2} /\ s{1} = s{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})).
  have f_eqM : forall (B : bool), equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : DoubleQuery.bad{2} = B /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => arg{1} = arg{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}) ==> (B => DoubleQuery.bad{2}) /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\ (!DoubleQuery.bad{2} => res{1} = res{2} /\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})].
  move=> B; conseq f_eq (_: true ==> true) (_: DoubleQuery.bad = B ==> B => DoubleQuery.bad).
  smt().
  smt().
  proc; inline*; auto.
  proc; inline*; if; auto; smt().
  sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0).
  auto; smt().
  move=> &2 bad.
  conseq (_: true ==> true: =1%r) (_: DoubleQuery.bad <=> DoubleQuery.bad{2} ==> DoubleQuery.bad <=> DoubleQuery.bad{2}).
  smt().
  proc; while (DoubleQuery.bad <=> DoubleQuery.bad{2}); inline*; auto.
  sp; if; auto; smt().
  proc; while (0 <= i <= size p) (size p - i).
  move=> z; inline*; auto.
  conseq (_: _ ==> true: =1%r) (_: _ ==> 0 <= i + 1 <= size p /\ size p - (i + 1) < z).
  smt().
  smt().
  sp; if; auto; smt().
  sp; if; auto; smt(dBlock_uffu).
  auto; smt(size_ge0 dBlock_uffu).
  move=> &1.
  conseq (_: true ==> true: =1%r) (_: DoubleQuery.bad /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad) ==> DoubleQuery.bad /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad)).
  smt().
  proc; while (DoubleQuery.bad /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad)); inline*; auto; sp; if; auto; smt().
  proc; while (0 <= i <= size p) (size p - i).
  move=> z; inline*; auto.
  smt(dBlock_uffu size_ge0).
  auto; smt(size_ge0 dBlock_uffu).
  inline*; auto; smt(fdom0).
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-05_0342_CBC_upto

Run dir: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1`

t=0: `2026-06-05T10:43:43.600000+00:00`

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 1.4 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | inspect pr_bridge_routes | probability / pr / probability, 1 goal, goal 305 chars | read-only inspect |  |
| T0.0-2 | +00:05 | [3.8 s](./views/Tree_0_0/thinking/turn_002.md) | 189 ms | [turn_001.json](./views/Tree_0_0/turn_001.json) · [inline read](./views/Tree_0_0/followups/turn_001.md) | inspect lemma_index | probability / pr / probability, 1 goal, goal 305 chars | read-only inspect |  |
| T0.0-3 | +00:38 | [32.6 s](./views/Tree_0_0/thinking/turn_003.md) | 1.4 s | [turn_002.json](./views/Tree_0_0/turn_002.json) · [inline read](./views/Tree_0_0/followups/turn_002.md) | probe rewrite (doublequery_eq PRFi &m) | probability / pr / probability, 1 goal, goal 305 chars | accepted probe |  |
| T0.0-4 | +03:36 | [176.5 s](./views/Tree_0_0/thinking/turn_004.md) | 518 ms | [turn_003.json](./views/Tree_0_0/turn_003.json) · [inline read](./views/Tree_0_0/followups/turn_003.md) | commit rewrite (doublequery_eq PRFi &m) | probability / pr / probability, 1 goal, goal 305 chars | accepted commit |  |
| T0.0-5 | +03:39 | [2.5 s](./views/Tree_0_0/thinking/turn_005.md) | 525 ms | [turn_004.json](./views/Tree_0_0/turn_004.json) · [inline read](./views/Tree_0_0/followups/turn_004.md) | commit rewrite (doublequery_eq Sample &m) | probability / pr / probability, 1 goal, goal 331 chars | accepted commit |  |
| T0.0-6 | +03:44 | [4.6 s](./views/Tree_0_0/thinking/turn_006.md) | 1.4 s | [turn_005.json](./views/Tree_0_0/turn_005.json) · [inline read](./views/Tree_0_0/followups/turn_005.md) | probe rewrite -(DQ_Sample_Compute_pr &m) | probability / pr / probability, 1 goal, goal 344 chars | accepted probe |  |
| T0.0-7 | +03:50 | [4.5 s](./views/Tree_0_0/thinking/turn_007.md) | 532 ms | [turn_006.json](./views/Tree_0_0/turn_006.json) · [inline read](./views/Tree_0_0/followups/turn_006.md) | commit rewrite -(DQ_Sample_Compute_pr &m) | probability / pr / probability, 1 goal, goal 344 chars | accepted commit |  |
| T0.0-8 | +04:04 | [13.8 s](./views/Tree_0_0/thinking/turn_008.md) | 207 ms | [turn_007.json](./views/Tree_0_0/turn_007.json) · [inline read](./views/Tree_0_0/followups/turn_007.md) | inspect tactic_forms | probability / pr / probability, 1 goal, goal 375 chars | read-only inspect |  |
| T0.0-9 | +04:33 | [28.6 s](./views/Tree_0_0/thinking/turn_009.md) | 1.4 s | [turn_008.json](./views/Tree_0_0/turn_008.json) · [inline read](./views/Tree_0_0/followups/turn_008.md) | probe byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2}... | probability / pr / probability, 1 goal, goal 375 chars | rejected probe: invalid goal shape |  |
| T0.0-10 | +06:27 | [112.7 s](./views/Tree_0_0/thinking/turn_010.md) | 342 ms | [turn_009.json](./views/Tree_0_0/turn_009.json) · [inline read](./views/Tree_0_0/followups/turn_009.md) | inspect diagnose | probability / pr / probability, 1 goal, goal 375 chars | read-only inspect |  |
| T0.0-11 | +06:48 | [20.5 s](./views/Tree_0_0/thinking/turn_011.md) | 534 ms | [turn_010.json](./views/Tree_0_0/turn_010.json) · [inline read](./views/Tree_0_0/followups/turn_010.md) | probe byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2}... | probability / pr / probability, 1 goal, goal 375 chars | rejected probe: invalid goal shape |  |
| T0.0-12 | +07:11 | [22.6 s](./views/Tree_0_0/thinking/turn_012.md) | 1.4 s | [turn_011.json](./views/Tree_0_0/turn_011.json) · [inline read](./views/Tree_0_0/followups/turn_011.md) | commit byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2}... | probability / pr / probability, 1 goal, goal 375 chars | rejected commit: proof state unchanged |  |
| T0.0-13 | +07:34 | [21.6 s](./views/Tree_0_0/thinking/turn_013.md) | 385 ms | [turn_012.json](./views/Tree_0_0/turn_012.json) · [inline read](./views/Tree_0_0/followups/turn_012.md) | inspect diagnose | probability / pr / failure_diagnostic, 1 goal, goal 375 chars | read-only inspect |  |
| T0.0-14 | +10:16 | [161.6 s](./views/Tree_0_0/thinking/turn_014.md) | 1.4 s | [turn_013.json](./views/Tree_0_0/turn_013.json) · [inline read](./views/Tree_0_0/followups/turn_013.md) | probe byequiv: DoubleQuery.bad => //= | probability / pr / failure_diagnostic, 1 goal, goal 375 chars | accepted probe |  |
| T0.0-15 | +10:46 | [28.4 s](./views/Tree_0_0/thinking/turn_015.md) | 552 ms | [turn_014.json](./views/Tree_0_0/turn_014.json) · [inline read](./views/Tree_0_0/followups/turn_014.md) | probe byequiv: DoubleQuery.bad => //=; 2: by smt() | probability / pr / failure_diagnostic, 1 goal, goal 375 chars | accepted probe |  |
| T0.0-16 | +10:59 | [12.8 s](./views/Tree_0_0/thinking/turn_016.md) | 200 ms | [turn_015.json](./views/Tree_0_0/turn_015.json) · [inline read](./views/Tree_0_0/followups/turn_015.md) | commit byequiv: DoubleQuery.bad => //=; 2: by smt() | probability / pr / failure_diagnostic, 1 goal, goal 375 chars | accepted commit |  |
| T0.0-17 | +11:56 | [56.8 s](./views/Tree_0_0/thinking/turn_017.md) | 203 ms | [turn_016.json](./views/Tree_0_0/turn_016.json) · [inline read](./views/Tree_0_0/followups/turn_016.md) | commit proc | equiv / prhl_module / relational_program, 1 goal, goal 672 chars | accepted commit |  |
| T0.0-18 | +12:31 | [35.0 s](./views/Tree_0_0/thinking/turn_018.md) | 970 ms | [turn_017.json](./views/Tree_0_0/turn_017.json) · [inline read](./views/Tree_0_0/followups/turn_017.md) | inspect call_invariant_skeleton | pRHL / call_site / relational_program, 1 goal, goal 655 chars | read-only inspect |  |
| T0.0-19 | +13:12 | [39.9 s](./views/Tree_0_0/thinking/turn_019.md) | 91 ms | [turn_018.json](./views/Tree_0_0/turn_018.json) · [inline read](./views/Tree_0_0/followups/turn_018.md) | inspect tactic_forms | pRHL / call_site / relational_program, 1 goal, goal 655 chars | read-only inspect |  |
| T0.0-20 | +14:45 | [92.8 s](./views/Tree_0_0/thinking/turn_020.md) | 170 ms | [turn_019.json](./views/Tree_0_0/turn_019.json) · [inline read](./views/Tree_0_0/followups/turn_019.md) | probe call DoubleQuery.bad | pRHL / call_site / relational_program, 1 goal, goal 655 chars | accepted probe |  |
| T0.0-21 | +15:04 | [18.8 s](./views/Tree_0_0/thinking/turn_021.md) | 186 ms | [turn_020.json](./views/Tree_0_0/turn_020.json) · [inline read](./views/Tree_0_0/followups/turn_020.md) | commit call DoubleQuery.bad | pRHL / call_site / relational_program, 1 goal, goal 655 chars | accepted commit |  |
| T0.0-22 | +15:14 | [9.8 s](./views/Tree_0_0/thinking/turn_022.md) | 156 ms | [turn_021.json](./views/Tree_0_0/turn_021.json) · [inline read](./views/Tree_0_0/followups/turn_021.md) | commit exact A_distinguish_ll | ambient / ambient_logic, 5 goals, goal 227 chars | accepted commit |  |
| T0.0-23 | +22:03 | [409 s](./views/Tree_0_0/thinking/turn_023.md) | 1 s | [turn_022.json](./views/Tree_0_0/turn_022.json) · [inline read](./views/Tree_0_0/followups/turn_022.md) | probe have f_eq : equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : (Doub... | equiv / prhl_module / relational_program, 4 goals, goal 648 chars | accepted probe |  |
| T0.0-24 | +22:11 | [6.8 s](./views/Tree_0_0/thinking/turn_024.md) | 156 ms | [turn_023.json](./views/Tree_0_0/turn_023.json) · [inline read](./views/Tree_0_0/followups/turn_023.md) | commit have f_eq : equiv[DoubleQuery(PRFi).f ~ DoubleQuery(Sample).f : (Doub... | equiv / prhl_module / relational_program, 4 goals, goal 648 chars | accepted commit |  |
| T0.0-25 | +23:13 | [61.8 s](./views/Tree_0_0/thinking/turn_025.md) | 213 ms | [turn_024.json](./views/Tree_0_0/turn_024.json) · [inline read](./views/Tree_0_0/followups/turn_024.md) | commit proc | equiv / prhl_module / relational_program, 5 goals, goal 569 chars | accepted commit |  |
| T0.0-26 | +24:35 | [81.8 s](./views/Tree_0_0/thinking/turn_026.md) | 219 ms | [turn_025.json](./views/Tree_0_0/turn_025.json) · [inline read](./views/Tree_0_0/followups/turn_025.md) | commit case (DoubleQuery.bad{2}) | pRHL / call_site / relational_program, 5 goals, goal 965 chars | accepted commit |  |
| T0.0-27 | +25:35 | [59.9 s](./views/Tree_0_0/thinking/turn_027.md) | 1.1 s | [turn_026.json](./views/Tree_0_0/turn_026.json) · [inline read](./views/Tree_0_0/followups/turn_026.md) | probe conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}) | pRHL / call_site / relational_program, 6 goals, goal 995 chars | accepted probe |  |
| T0.0-28 | +25:55 | [18.8 s](./views/Tree_0_0/thinking/turn_028.md) | 225 ms | [turn_027.json](./views/Tree_0_0/turn_027.json) · [inline read](./views/Tree_0_0/followups/turn_027.md) | commit conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}); first by smt() | pRHL / call_site / seq_cut, 6 goals, goal 995 chars | accepted commit |  |
| T0.0-29 | +27:06 | [70.9 s](./views/Tree_0_0/thinking/turn_029.md) | 1.1 s | [turn_028.json](./views/Tree_0_0/turn_028.json) · [inline read](./views/Tree_0_0/followups/turn_028.md) | probe inline *; auto | pRHL / call_site / relational_program, 6 goals, goal 860 chars | accepted probe |  |
| T0.0-30 | +27:54 | [46.8 s](./views/Tree_0_0/thinking/turn_030.md) | 226 ms | [turn_029.json](./views/Tree_0_0/turn_029.json) · [inline read](./views/Tree_0_0/followups/turn_029.md) | commit inline *; auto | pRHL / call_site / relational_program, 6 goals, goal 860 chars | accepted commit |  |
| T0.0-31 | +28:43 | [48.9 s](./views/Tree_0_0/thinking/turn_031.md) | 4.1 s | [turn_030.json](./views/Tree_0_0/turn_030.json) · [inline read](./views/Tree_0_0/followups/turn_030.md) | probe if{1}; auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 6 goals, goal 1213 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-32 | +29:41 | [53.8 s](./views/Tree_0_0/thinking/turn_032.md) | 152 ms | [turn_031.json](./views/Tree_0_0/turn_031.json) · [inline read](./views/Tree_0_0/followups/turn_031.md) | probe if{1}; auto | pRHL / procedure_body / relational_program, 6 goals, goal 1213 chars | accepted probe |  |
| T0.0-33 | +31:23 | [101.7 s](./views/Tree_0_0/thinking/turn_033.md) | 293 ms | [turn_032.json](./views/Tree_0_0/turn_032.json) · [inline read](./views/Tree_0_0/followups/turn_032.md) | probe if{1}; sp; if{1}; auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 6 goals, goal 1213 chars | accepted probe |  |
| T0.0-34 | +31:35 | [11.7 s](./views/Tree_0_0/thinking/turn_034.md) | 344 ms | [turn_033.json](./views/Tree_0_0/turn_033.json) · [inline read](./views/Tree_0_0/followups/turn_033.md) | commit if{1}; sp; if{1}; auto; smt(dBlock_uffu) | pRHL / procedure_body / relational_program, 6 goals, goal 1213 chars | accepted commit |  |
| T0.0-35 | +32:16 | [40.8 s](./views/Tree_0_0/thinking/turn_035.md) | 1.2 s | [turn_034.json](./views/Tree_0_0/turn_034.json) · [inline read](./views/Tree_0_0/followups/turn_034.md) | probe if=> //= | pRHL / call_site / relational_program, 5 goals, goal 996 chars | accepted probe |  |
| T0.0-36 | +32:40 | [22.8 s](./views/Tree_0_0/thinking/turn_036.md) | 220 ms | [turn_035.json](./views/Tree_0_0/turn_035.json) · [inline read](./views/Tree_0_0/followups/turn_035.md) | commit if=> //= | pRHL / call_site / relational_program, 5 goals, goal 996 chars | accepted commit |  |
| T0.0-37 | +32:46 | [5.8 s](./views/Tree_0_0/thinking/turn_037.md) | 224 ms | [turn_036.json](./views/Tree_0_0/turn_036.json) · [inline read](./views/Tree_0_0/followups/turn_036.md) | commit smt() | ambient / ambient_logic / relational_program, 7 goals, goal 429 chars | accepted commit |  |
| T0.0-38 | +33:25 | [38.8 s](./views/Tree_0_0/thinking/turn_038.md) | 223 ms | [turn_037.json](./views/Tree_0_0/turn_037.json) · [inline read](./views/Tree_0_0/followups/turn_037.md) | commit conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}); first by smt() | pRHL / call_site / relational_program, 6 goals, goal 897 chars | accepted commit |  |
| T0.0-39 | +33:52 | [26.7 s](./views/Tree_0_0/thinking/turn_039.md) | 1.3 s | [turn_038.json](./views/Tree_0_0/turn_038.json) · [inline read](./views/Tree_0_0/followups/turn_038.md) | probe inline*; auto; if{1}; auto; smt(dBlock_uffu) | pRHL / call_site / relational_program, 6 goals, goal 762 chars | rejected probe: invalid first instruction |  |
| T0.0-40 | +34:00 | [6.8 s](./views/Tree_0_0/thinking/turn_040.md) | 183 ms | [turn_039.json](./views/Tree_0_0/turn_039.json) · [inline read](./views/Tree_0_0/followups/turn_039.md) | probe inline*; auto | pRHL / call_site / relational_program, 6 goals, goal 762 chars | accepted probe |  |
| T0.0-41 | +34:16 | [15.7 s](./views/Tree_0_0/thinking/turn_041.md) | 268 ms | [turn_040.json](./views/Tree_0_0/turn_040.json) · [inline read](./views/Tree_0_0/followups/turn_040.md) | probe inline*; auto; sp; if{1}; auto; smt(dBlock_uffu) | pRHL / call_site / relational_program, 6 goals, goal 762 chars | accepted probe |  |
| T0.0-42 | +34:26 | [9.7 s](./views/Tree_0_0/thinking/turn_042.md) | 301 ms | [turn_041.json](./views/Tree_0_0/turn_041.json) · [inline read](./views/Tree_0_0/followups/turn_041.md) | commit inline*; auto; sp; if{1}; auto; smt(dBlock_uffu) | pRHL / call_site / relational_program, 6 goals, goal 762 chars | accepted commit |  |
| T0.0-43 | +34:57 | [30.7 s](./views/Tree_0_0/thinking/turn_043.md) | 1.3 s | [turn_042.json](./views/Tree_0_0/turn_042.json) · [inline read](./views/Tree_0_0/followups/turn_042.md) | probe inline*; sp; rcondt{1} 1 | pRHL / call_site / relational_program, 5 goals, goal 836 chars | accepted probe |  |
| T0.0-44 | +35:30 | [31.8 s](./views/Tree_0_0/thinking/turn_044.md) | 153 ms | [turn_043.json](./views/Tree_0_0/turn_043.json) · [inline read](./views/Tree_0_0/followups/turn_043.md) | commit inline*; sp; rcondt{1} 1 | pRHL / call_site / relational_program, 5 goals, goal 836 chars | accepted commit |  |
| T0.0-45 | +35:46 | [15.6 s](./views/Tree_0_0/thinking/turn_045.md) | 1.4 s | [turn_044.json](./views/Tree_0_0/turn_044.json) · [inline read](./views/Tree_0_0/followups/turn_044.md) | probe auto; smt(mem_fdom) | ambient / ambient_logic, 6 goals, goal 537 chars | accepted probe |  |
| T0.0-46 | +35:53 | [5.5 s](./views/Tree_0_0/thinking/turn_046.md) | 1.5 s | [turn_045.json](./views/Tree_0_0/turn_045.json) · [inline read](./views/Tree_0_0/followups/turn_045.md) | commit auto; smt(mem_fdom) | ambient / ambient_logic, 6 goals, goal 537 chars | accepted commit |  |
| T0.0-47 | +36:12 | [17.7 s](./views/Tree_0_0/thinking/turn_047.md) | 3.3 s | [turn_046.json](./views/Tree_0_0/turn_046.json) · [inline read](./views/Tree_0_0/followups/turn_046.md) | probe auto; smt(fdom_set get_set_sameE) | pRHL / procedure_body / seq_cut, 5 goals, goal 1080 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-48 | +36:31 | [15.8 s](./views/Tree_0_0/thinking/turn_048.md) | 202 ms | [turn_047.json](./views/Tree_0_0/turn_047.json) · [inline read](./views/Tree_0_0/followups/turn_047.md) | probe auto | pRHL / procedure_body / seq_cut, 5 goals, goal 1080 chars | accepted probe |  |
| T0.0-49 | +37:14 | [43.1 s](./views/Tree_0_0/thinking/turn_049.md) | 944 ms | [turn_048.json](./views/Tree_0_0/turn_048.json) · [inline read](./views/Tree_0_0/followups/turn_048.md) | lookup fdom_set | pRHL / procedure_body / seq_cut, 5 goals, goal 1080 chars | lookup result |  |
| T0.0-50 | +37:28 | [12.8 s](./views/Tree_0_0/thinking/turn_050.md) | 220 ms | [turn_049.json](./views/Tree_0_0/turn_049.json) · [inline read](./views/Tree_0_0/followups/turn_049.md) | probe auto; smt(fdom_set get_set_sameE oget_some) | pRHL / procedure_body / seq_cut, 5 goals, goal 1080 chars | accepted probe |  |
| T0.0-51 | +37:36 | [7.7 s](./views/Tree_0_0/thinking/turn_051.md) | 270 ms | [turn_050.json](./views/Tree_0_0/turn_050.json) · [inline read](./views/Tree_0_0/followups/turn_050.md) | commit auto; smt(fdom_set get_set_sameE oget_some) | pRHL / procedure_body / seq_cut, 5 goals, goal 1080 chars | accepted commit |  |
| T0.0-52 | +37:59 | [22.8 s](./views/Tree_0_0/thinking/turn_052.md) | 231 ms | [turn_051.json](./views/Tree_0_0/turn_051.json) · [inline read](./views/Tree_0_0/followups/turn_051.md) | commit proc | equiv / prhl_module / relational_program, 4 goals, goal 1193 chars | accepted commit |  |
| T0.0-53 | +38:23 | [23.6 s](./views/Tree_0_0/thinking/turn_053.md) | 1.4 s | [turn_052.json](./views/Tree_0_0/turn_052.json) · [inline read](./views/Tree_0_0/followups/turn_052.md) | probe seq 3 3 : (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <... | pRHL / call_site / relational_program, 4 goals, goal 2123 chars | accepted probe |  |
| T0.0-54 | +38:33 | [8.8 s](./views/Tree_0_0/thinking/turn_054.md) | 208 ms | [turn_053.json](./views/Tree_0_0/turn_053.json) · [inline read](./views/Tree_0_0/followups/turn_053.md) | commit seq 3 3 : (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <... | pRHL / call_site / relational_program, 4 goals, goal 2123 chars | accepted commit |  |
| T0.0-55 | +38:41 | [7.7 s](./views/Tree_0_0/thinking/turn_055.md) | 281 ms | [turn_054.json](./views/Tree_0_0/turn_054.json) · [inline read](./views/Tree_0_0/followups/turn_054.md) | commit auto; smt(size_ge0) | pRHL / verification_residue / relational_program, 5 goals, goal 1363 chars | accepted commit |  |
| T0.0-56 | +39:09 | [27.8 s](./views/Tree_0_0/thinking/turn_056.md) | 230 ms | [turn_055.json](./views/Tree_0_0/turn_055.json) · [inline read](./views/Tree_0_0/followups/turn_055.md) | commit while (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <=> D... | pRHL / call_site / relational_program, 4 goals, goal 1938 chars | accepted commit |  |
| T0.0-57 | +39:33 | [23.5 s](./views/Tree_0_0/thinking/turn_057.md) | 1.5 s | [turn_056.json](./views/Tree_0_0/turn_056.json) · [inline read](./views/Tree_0_0/followups/turn_056.md) | probe sp 1 1; wp; call f_eq; auto | pRHL / call_site / relational_program, 5 goals, goal 1857 chars | accepted probe |  |
| T0.0-58 | +40:03 | [28.7 s](./views/Tree_0_0/thinking/turn_058.md) | 3.3 s | [turn_057.json](./views/Tree_0_0/turn_057.json) · [inline read](./views/Tree_0_0/followups/turn_057.md) | probe sp 1 1; wp; call f_eq; auto; smt(size_ge0) | pRHL / call_site / relational_program, 5 goals, goal 1857 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-59 | +40:33 | [26.8 s](./views/Tree_0_0/thinking/turn_059.md) | 235 ms | [turn_058.json](./views/Tree_0_0/turn_058.json) · [inline read](./views/Tree_0_0/followups/turn_058.md) | commit sp 1 1; wp; call f_eq; auto | pRHL / call_site / relational_program, 5 goals, goal 1857 chars | accepted commit |  |
| T0.0-60 | +53:28 | 774.5 s | 1.5 s | [turn_059.json](./views/Tree_0_0/turn_059.json) · [inline read](./views/Tree_0_0/followups/turn_059.md) | undo_last_step | ambient / ambient_logic / relational_program, 5 goals, goal 1827 chars | undo result |  |
| T0.0-61 | +54:07 | [37.2 s](./views/Tree_0_0/thinking/turn_061.md) | 2.8 s | [turn_060.json](./views/Tree_0_0/turn_060.json) · [inline read](./views/Tree_0_0/followups/turn_060.md) | probe have f_eqM : forall (B : bool), equiv[DoubleQuery(PRFi).f ~ DoubleQue... | pRHL / call_site / relational_program, 5 goals, goal 1844 chars | accepted probe |  |
| T0.0-62 | +54:17 | [7.8 s](./views/Tree_0_0/thinking/turn_062.md) | 216 ms | [turn_061.json](./views/Tree_0_0/turn_061.json) · [inline read](./views/Tree_0_0/followups/turn_061.md) | commit have f_eqM : forall (B : bool), equiv[DoubleQuery(PRFi).f ~ DoubleQue... | pRHL / call_site / relational_program, 5 goals, goal 1844 chars | accepted commit |  |
| T0.0-63 | +54:34 | [16.5 s](./views/Tree_0_0/thinking/turn_063.md) | 1.5 s | [turn_062.json](./views/Tree_0_0/turn_062.json) · [inline read](./views/Tree_0_0/followups/turn_062.md) | probe move=> B; conseq f_eq (_: true ==> true) (_: DoubleQuery.bad = B ==> B => DoubleQuery.bad) | ambient / ambient_logic / relational_program, 6 goals, goal 1285 chars | accepted probe |  |
| T0.0-64 | +54:43 | [7.8 s](./views/Tree_0_0/thinking/turn_064.md) | 219 ms | [turn_063.json](./views/Tree_0_0/turn_063.json) · [inline read](./views/Tree_0_0/followups/turn_063.md) | commit move=> B; conseq f_eq (_: true ==> true) (_: DoubleQuery.bad = B ==> B => DoubleQuery.bad) | ambient / ambient_logic / seq_cut, 6 goals, goal 1285 chars | accepted commit |  |
| T0.0-65 | +54:55 | [11.7 s](./views/Tree_0_0/thinking/turn_065.md) | 258 ms | [turn_064.json](./views/Tree_0_0/turn_064.json) · [inline read](./views/Tree_0_0/followups/turn_064.md) | commit smt() | ambient / ambient_logic / relational_program, 9 goals, goal 1145 chars | accepted commit |  |
| T0.0-66 | +55:03 | [7.8 s](./views/Tree_0_0/thinking/turn_066.md) | 241 ms | [turn_065.json](./views/Tree_0_0/turn_065.json) · [inline read](./views/Tree_0_0/followups/turn_065.md) | commit smt() | ambient / ambient_logic / relational_program, 8 goals, goal 1307 chars | accepted commit |  |
| T0.0-67 | +55:18 | [14.8 s](./views/Tree_0_0/thinking/turn_067.md) | 220 ms | [turn_066.json](./views/Tree_0_0/turn_066.json) · [inline read](./views/Tree_0_0/followups/turn_066.md) | commit proc; inline*; auto | hoare / procedure_body / relational_program, 7 goals, goal 753 chars | accepted commit |  |
| T0.0-68 | +55:44 | [25.4 s](./views/Tree_0_0/thinking/turn_068.md) | 1.6 s | [turn_067.json](./views/Tree_0_0/turn_067.json) · [inline read](./views/Tree_0_0/followups/turn_067.md) | probe proc; inline*; if; auto; smt() | hoare / procedure_body / relational_program, 6 goals, goal 786 chars | accepted probe |  |
| T0.0-69 | +55:59 | [13.8 s](./views/Tree_0_0/thinking/turn_069.md) | 237 ms | [turn_068.json](./views/Tree_0_0/turn_068.json) · [inline read](./views/Tree_0_0/followups/turn_068.md) | commit proc; inline*; if; auto; smt() | hoare / procedure_body / relational_program, 6 goals, goal 786 chars | accepted commit |  |
| T0.0-70 | +56:15 | [15.4 s](./views/Tree_0_0/thinking/turn_070.md) | 1.6 s | [turn_069.json](./views/Tree_0_0/turn_069.json) · [inline read](./views/Tree_0_0/followups/turn_069.md) | probe sp 1 1; wp; call (f_eqM DoubleQuery.bad{2}); auto; smt(size_ge0) | pRHL / call_site / relational_program, 5 goals, goal 2550 chars | rejected probe: This proof-term argument is not a valid formula: |  |
| T0.0-71 | +56:42 | [25.8 s](./views/Tree_0_0/thinking/turn_071.md) | 220 ms | [turn_070.json](./views/Tree_0_0/turn_070.json) · [inline read](./views/Tree_0_0/followups/turn_070.md) | probe sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0) | pRHL / call_site / relational_program, 5 goals, goal 2550 chars | accepted probe |  |
| T0.0-72 | +56:53 | [10.7 s](./views/Tree_0_0/thinking/turn_072.md) | 290 ms | [turn_071.json](./views/Tree_0_0/turn_071.json) · [inline read](./views/Tree_0_0/followups/turn_071.md) | commit sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0) | pRHL / call_site / relational_program, 5 goals, goal 2550 chars | accepted commit |  |
| T0.0-73 | +57:10 | [16.4 s](./views/Tree_0_0/thinking/turn_073.md) | 1.6 s | [turn_072.json](./views/Tree_0_0/turn_072.json) · [inline read](./views/Tree_0_0/followups/turn_072.md) | probe auto; smt() | pRHL / verification_residue / relational_program, 4 goals, goal 1950 chars | accepted probe |  |
| T0.0-74 | +57:22 | [10.7 s](./views/Tree_0_0/thinking/turn_074.md) | 259 ms | [turn_073.json](./views/Tree_0_0/turn_073.json) · [inline read](./views/Tree_0_0/followups/turn_073.md) | commit auto; smt() | pRHL / verification_residue / relational_program, 4 goals, goal 1950 chars | accepted commit |  |
| T0.0-75 | +58:01 | [38.8 s](./views/Tree_0_0/thinking/turn_075.md) | 235 ms | [turn_074.json](./views/Tree_0_0/turn_074.json) · [inline read](./views/Tree_0_0/followups/turn_074.md) | commit move=> &2 bad | ambient / ambient_logic, 3 goals, goal 341 chars | accepted commit |  |
| T0.0-76 | +58:14 | [12.4 s](./views/Tree_0_0/thinking/turn_076.md) | 1.6 s | [turn_075.json](./views/Tree_0_0/turn_075.json) · [inline read](./views/Tree_0_0/followups/turn_075.md) | probe conseq (_: true ==> true: =1%r) (_: DoubleQuery.bad <=> DoubleQuery.b... | phoare / procedure_body / procedure_frontier, 3 goals, goal 324 chars | accepted probe |  |
| T0.0-77 | +58:21 | [5.8 s](./views/Tree_0_0/thinking/turn_077.md) | 239 ms | [turn_076.json](./views/Tree_0_0/turn_076.json) · [inline read](./views/Tree_0_0/followups/turn_076.md) | commit conseq (_: true ==> true: =1%r) (_: DoubleQuery.bad <=> DoubleQuery.b... | phoare / procedure_body / procedure_frontier, 3 goals, goal 324 chars | accepted commit |  |
| T0.0-78 | +58:28 | [6.8 s](./views/Tree_0_0/thinking/turn_078.md) | 246 ms | [turn_077.json](./views/Tree_0_0/turn_077.json) · [inline read](./views/Tree_0_0/followups/turn_077.md) | commit smt() | ambient / ambient_logic / relational_program, 5 goals, goal 371 chars | accepted commit |  |
| T0.0-79 | +59:20 | [51.4 s](./views/Tree_0_0/thinking/turn_079.md) | 1.6 s | [turn_078.json](./views/Tree_0_0/turn_078.json) · [inline read](./views/Tree_0_0/followups/turn_078.md) | probe proc; while (DoubleQuery.bad <=> DoubleQuery.bad{2}); inline*; auto; smt() | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-80 | +59:45 | [23.8 s](./views/Tree_0_0/thinking/turn_080.md) | 180 ms | [turn_079.json](./views/Tree_0_0/turn_079.json) · [inline read](./views/Tree_0_0/followups/turn_079.md) | probe proc; while (DoubleQuery.bad <=> DoubleQuery.bad{2}); inline*; auto | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | accepted probe |  |
| T0.0-81 | +1:00:38 | [52.8 s](./views/Tree_0_0/thinking/turn_081.md) | 202 ms | [turn_080.json](./views/Tree_0_0/turn_080.json) · [inline read](./views/Tree_0_0/followups/turn_080.md) | commit proc; while (DoubleQuery.bad <=> DoubleQuery.bad{2}); inline*; auto | hoare / procedure_body / procedure_frontier, 4 goals, goal 313 chars | accepted commit |  |
| T0.0-82 | +1:01:01 | [22.3 s](./views/Tree_0_0/thinking/turn_082.md) | 1.7 s | [turn_081.json](./views/Tree_0_0/turn_081.json) · [inline read](./views/Tree_0_0/followups/turn_081.md) | probe sp; if; auto; smt() | hoare / procedure_body / procedure_frontier, 4 goals, goal 728 chars | accepted probe |  |
| T0.0-83 | +1:01:11 | [8.7 s](./views/Tree_0_0/thinking/turn_083.md) | 299 ms | [turn_082.json](./views/Tree_0_0/turn_082.json) · [inline read](./views/Tree_0_0/followups/turn_082.md) | commit sp; if; auto; smt() | hoare / procedure_body / procedure_frontier, 4 goals, goal 728 chars | accepted commit |  |
| T0.0-84 | +1:01:27 | [15.9 s](./views/Tree_0_0/thinking/turn_084.md) | 85 ms | [turn_083.json](./views/Tree_0_0/turn_083.json) · [inline read](./views/Tree_0_0/followups/turn_083.md) | inspect tactic_forms | phoare / procedure_body / procedure_frontier, 3 goals, goal 256 chars | read-only inspect |  |
| T0.0-85 | +1:02:03 | [35.3 s](./views/Tree_0_0/thinking/turn_085.md) | 1.7 s | [turn_084.json](./views/Tree_0_0/turn_084.json) · [inline read](./views/Tree_0_0/followups/turn_084.md) | probe proc; while (0 <= i <= size p) (size p - i) | phoare / procedure_body / procedure_frontier, 3 goals, goal 256 chars | accepted probe |  |
| T0.0-86 | +1:02:09 | [4.8 s](./views/Tree_0_0/thinking/turn_086.md) | 243 ms | [turn_085.json](./views/Tree_0_0/turn_085.json) · [inline read](./views/Tree_0_0/followups/turn_085.md) | commit proc; while (0 <= i <= size p) (size p - i) | phoare / procedure_body / procedure_frontier, 3 goals, goal 256 chars | accepted commit |  |
| T0.0-87 | +1:02:29 | [19.3 s](./views/Tree_0_0/thinking/turn_087.md) | 4.7 s | [turn_086.json](./views/Tree_0_0/turn_086.json) · [inline read](./views/Tree_0_0/followups/turn_086.md) | probe move=> z; inline*; auto; smt(dBlock_uffu) | ambient / ambient_logic, 4 goals, goal 369 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-88 | +1:02:49 | [15.8 s](./views/Tree_0_0/thinking/turn_088.md) | 211 ms | [turn_087.json](./views/Tree_0_0/turn_087.json) · [inline read](./views/Tree_0_0/followups/turn_087.md) | commit move=> z; inline*; auto | ambient / ambient_logic, 4 goals, goal 369 chars | accepted commit |  |
| T0.0-89 | +1:03:50 | [60.3 s](./views/Tree_0_0/thinking/turn_089.md) | 1.7 s | [turn_088.json](./views/Tree_0_0/turn_088.json) · [inline read](./views/Tree_0_0/followups/turn_088.md) | probe conseq (_: _ ==> true: =1%r) (_: _ ==> 0 <= i + 1 <= size p /\ size p... | phoare / procedure_body / procedure_frontier, 4 goals, goal 764 chars | accepted probe |  |
| T0.0-90 | +1:04:06 | [14.8 s](./views/Tree_0_0/thinking/turn_090.md) | 245 ms | [turn_089.json](./views/Tree_0_0/turn_089.json) · [inline read](./views/Tree_0_0/followups/turn_089.md) | commit conseq (_: _ ==> true: =1%r) (_: _ ==> 0 <= i + 1 <= size p /\ size p... | phoare / procedure_body / seq_cut, 4 goals, goal 764 chars | accepted commit |  |
| T0.0-91 | +1:04:12 | [5.7 s](./views/Tree_0_0/thinking/turn_091.md) | 274 ms | [turn_090.json](./views/Tree_0_0/turn_090.json) · [inline read](./views/Tree_0_0/followups/turn_090.md) | commit smt() | ambient / ambient_logic / relational_program, 7 goals, goal 415 chars | accepted commit |  |
| T0.0-92 | +1:04:16 | [3.8 s](./views/Tree_0_0/thinking/turn_092.md) | 220 ms | [turn_091.json](./views/Tree_0_0/turn_091.json) · [inline read](./views/Tree_0_0/followups/turn_091.md) | commit smt() | ambient / ambient_logic / relational_program, 6 goals, goal 469 chars | accepted commit |  |
| T0.0-93 | +1:04:34 | [17.3 s](./views/Tree_0_0/thinking/turn_093.md) | 4.7 s | [turn_092.json](./views/Tree_0_0/turn_092.json) · [inline read](./views/Tree_0_0/followups/turn_092.md) | probe auto; smt(size_ge0) | hoare / procedure_body / procedure_frontier, 5 goals, goal 737 chars | rejected probe: cannot prove goal (strict) |  |
| T0.0-94 | +1:04:55 | [16.8 s](./views/Tree_0_0/thinking/turn_094.md) | 248 ms | [turn_093.json](./views/Tree_0_0/turn_093.json) · [inline read](./views/Tree_0_0/followups/turn_093.md) | probe sp; if; auto; smt() | hoare / procedure_body / procedure_frontier, 5 goals, goal 737 chars | accepted probe |  |
| T0.0-95 | +1:05:06 | [10.7 s](./views/Tree_0_0/thinking/turn_095.md) | 253 ms | [turn_094.json](./views/Tree_0_0/turn_094.json) · [inline read](./views/Tree_0_0/followups/turn_094.md) | commit sp; if; auto; smt() | hoare / procedure_body / procedure_frontier, 5 goals, goal 737 chars | accepted commit |  |
| T0.0-96 | +1:05:23 | [16.2 s](./views/Tree_0_0/thinking/turn_096.md) | 1.8 s | [turn_095.json](./views/Tree_0_0/turn_095.json) · [inline read](./views/Tree_0_0/followups/turn_095.md) | probe sp; if; auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 4 goals, goal 714 chars | accepted probe |  |
| T0.0-97 | +1:05:36 | [11.8 s](./views/Tree_0_0/thinking/turn_097.md) | 220 ms | [turn_096.json](./views/Tree_0_0/turn_096.json) · [inline read](./views/Tree_0_0/followups/turn_096.md) | commit sp; if; auto; smt(dBlock_uffu) | phoare / procedure_body / procedure_frontier, 4 goals, goal 714 chars | accepted commit |  |
| T0.0-98 | +1:05:48 | [12.1 s](./views/Tree_0_0/thinking/turn_098.md) | 1.9 s | [turn_097.json](./views/Tree_0_0/turn_097.json) · [inline read](./views/Tree_0_0/followups/turn_097.md) | probe auto; smt(size_ge0 dBlock_uffu) | phoare / procedure_body / procedure_frontier, 3 goals, goal 477 chars | accepted probe |  |
| T0.0-99 | +1:05:56 | [5.7 s](./views/Tree_0_0/thinking/turn_099.md) | 279 ms | [turn_098.json](./views/Tree_0_0/turn_098.json) · [inline read](./views/Tree_0_0/followups/turn_098.md) | commit auto; smt(size_ge0 dBlock_uffu) | phoare / procedure_body / procedure_frontier, 3 goals, goal 477 chars | accepted commit |  |
| T0.0-100 | +1:06:20 | [23.8 s](./views/Tree_0_0/thinking/turn_100.md) | 238 ms | [turn_099.json](./views/Tree_0_0/turn_099.json) · [inline read](./views/Tree_0_0/followups/turn_099.md) | commit move=> &1 | ambient / ambient_logic, 2 goals, goal 361 chars | accepted commit |  |
| T0.0-101 | +1:06:37 | [16.8 s](./views/Tree_0_0/thinking/turn_101.md) | 233 ms | [turn_100.json](./views/Tree_0_0/turn_100.json) · [inline read](./views/Tree_0_0/followups/turn_100.md) | commit conseq (_: true ==> true: =1%r) (_: DoubleQuery.bad /\ (DoubleQuery.b... | phoare / procedure_body / procedure_frontier, 2 goals, goal 344 chars | accepted commit |  |
| T0.0-102 | +1:06:42 | [4.7 s](./views/Tree_0_0/thinking/turn_102.md) | 251 ms | [turn_101.json](./views/Tree_0_0/turn_101.json) · [inline read](./views/Tree_0_0/followups/turn_101.md) | commit smt() | ambient / ambient_logic / relational_program, 4 goals, goal 394 chars | accepted commit |  |
| T0.0-103 | +1:07:04 | [21.2 s](./views/Tree_0_0/thinking/turn_103.md) | 1.8 s | [turn_102.json](./views/Tree_0_0/turn_102.json) · [inline read](./views/Tree_0_0/followups/turn_102.md) | probe proc; while (DoubleQuery.bad /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad)); inline*; auto; sp;... | hoare / procedure_body / procedure_frontier, 3 goals, goal 333 chars | accepted probe |  |
| T0.0-104 | +1:07:14 | [8.7 s](./views/Tree_0_0/thinking/turn_104.md) | 266 ms | [turn_103.json](./views/Tree_0_0/turn_103.json) · [inline read](./views/Tree_0_0/followups/turn_103.md) | commit proc; while (DoubleQuery.bad /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad)); inline*; auto; sp;... | hoare / procedure_body / procedure_frontier, 3 goals, goal 333 chars | accepted commit |  |
| T0.0-105 | +1:07:32 | [17.7 s](./views/Tree_0_0/thinking/turn_105.md) | 256 ms | [turn_104.json](./views/Tree_0_0/turn_104.json) · [inline read](./views/Tree_0_0/followups/turn_104.md) | commit proc; while (0 <= i <= size p) (size p - i) | phoare / procedure_body / procedure_frontier, 2 goals, goal 234 chars | accepted commit |  |
| T0.0-106 | +1:07:44 | [12.1 s](./views/Tree_0_0/thinking/turn_106.md) | 1.9 s | [turn_105.json](./views/Tree_0_0/turn_105.json) · [inline read](./views/Tree_0_0/followups/turn_105.md) | probe move=> z; inline*; sp; if; auto; smt(dBlock_uffu size_ge0) | ambient / ambient_logic, 3 goals, goal 345 chars | rejected probe: invalid first instruction |  |
| T0.0-107 | +1:08:02 | [15.7 s](./views/Tree_0_0/thinking/turn_107.md) | 262 ms | [turn_106.json](./views/Tree_0_0/turn_106.json) · [inline read](./views/Tree_0_0/followups/turn_106.md) | commit move=> z; inline*; auto | ambient / ambient_logic, 3 goals, goal 345 chars | accepted commit |  |
| T0.0-108 | +1:08:18 | [16.1 s](./views/Tree_0_0/thinking/turn_108.md) | 1.9 s | [turn_107.json](./views/Tree_0_0/turn_107.json) · [inline read](./views/Tree_0_0/followups/turn_107.md) | probe smt(dBlock_uffu size_ge0) | ambient / ambient_logic, 3 goals, goal 656 chars | accepted probe |  |
| T0.0-109 | +1:08:25 | [4.8 s](./views/Tree_0_0/thinking/turn_109.md) | 243 ms | [turn_108.json](./views/Tree_0_0/turn_108.json) · [inline read](./views/Tree_0_0/followups/turn_108.md) | commit smt(dBlock_uffu size_ge0) | ambient / ambient_logic, 3 goals, goal 656 chars | accepted commit |  |
| T0.0-110 | +1:08:32 | [6.7 s](./views/Tree_0_0/thinking/turn_110.md) | 277 ms | [turn_109.json](./views/Tree_0_0/turn_109.json) · [inline read](./views/Tree_0_0/followups/turn_109.md) | commit auto; smt(size_ge0 dBlock_uffu) | phoare / procedure_body / procedure_frontier, 2 goals, goal 453 chars | accepted commit |  |
| T0.0-111 | +1:08:50 | [18 s](./views/Tree_0_0/thinking/turn_111.md) | 2 s | [turn_110.json](./views/Tree_0_0/turn_110.json) · [inline read](./views/Tree_0_0/followups/turn_110.md) | probe inline*; auto; smt(fdom0) | pRHL / procedure_body / relational_program, 1 goal, goal 985 chars | accepted probe |  |
| T0.0-112 | +1:09:07 | [14.8 s](./views/Tree_0_0/thinking/turn_112.md) | 204 ms | [turn_111.json](./views/Tree_0_0/turn_111.json) · [inline read](./views/Tree_0_0/followups/turn_111.md) | commit inline*; auto; smt(fdom0) | pRHL / procedure_body / relational_program, 1 goal, goal 985 chars | accepted commit |  |
| T0.0-113 | +1:09:12 | [4.8 s](./views/Tree_0_0/thinking/turn_113.md) | 209 ms | [turn_112.json](./views/Tree_0_0/turn_112.json) · [inline read](./views/Tree_0_0/followups/turn_112.md) | commit qed | ambient / closed_candidate, goal 26 chars | accepted commit |  |
| T0.0-114 | +1:09:19 | 7 s |  | [turn_113.json](./views/Tree_0_0/turn_113.json) · [inline read](./views/Tree_0_0/followups/turn_113.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 12 chars | finish requested |  |
