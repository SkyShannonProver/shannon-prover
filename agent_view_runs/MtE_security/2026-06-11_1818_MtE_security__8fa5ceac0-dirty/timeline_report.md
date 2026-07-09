# Agent-View Timeline — `MtE_security`

| field | value |
|---|---|
| commit | `8fa5ceac0` **(dirty/uncommitted)** |
| branch | `mcp-v0` |
| run time | 2026-06-11_1818_MtE_security |
| lemma | `MtE_security` |
| source file | `eval/examples/MEE-CBC/MAC_then_Pad_then_CBC.eca` |
| model | `claude-fable-5` |
| surface profile | `l1_goal_projection` |
| trees | 2 |
| eval mode | True |
| outcome | proved |
| turns | 22 |

Each row below: the view → the intent the agent submitted → the manager result. The **Decision View** column has TWO links: `turn_NNN.json` is the full projected `ProverWorkspaceView` the framework computed (all panels); `inline read` is the filtered preview the agent ACTUALLY read inline (`./views/<tree>/followups/turn_NNN.md`). They diverge — the preview drops panels — so to see what the agent truly consumed, open `inline read`, not the full view.

---

## Agent's committed proof

The committed script per proof tree (EC-accepted commits only; undos/rewinds applied; a respawned node's replayed prefix included).

### `Tree_0_0` — incomplete — 0 tactic(s) committed, not closed (timeline replay — no session history survived)

```easycrypt
proof.
  (* no tactic committed *)
  (* proof not completed in this run *)
```

### `Tree_0_1` — proved

```easycrypt
proof.
  have RP := RCPA_WUF_RCPA.RCPA_preservation (<: PadThenEncrypt(IV_Wrap(CBC(PseudoRP)))) (<: MAC) (<: RCPA_QueryBounder(A)) &m.
  have Mkg_ll: islossless MAC.keygen by proc; auto=> />; smt(d_mK_uffu).
  have Mtag_ll: islossless MAC.tag by proc; auto.
  rewrite -(RP Mkg_ll Mtag_ll).
  do 2!congr.
  byequiv (: ={glob A} ==> ={res})=> //.
  proc; inline *.
  wp; call (: ={glob RCPA_QueryBounder} /\ RCPA_Wrap.k{1} = Sec.RCPA.RCPA_Wrap.k{2}).
  proc; sp; if=> //; last by sim.
  inline *.
  wp; while (={i0, p3, s, c4, key0} /\ RCPA_QueryBounder.qC{1} = RCPA_QueryBounder.qC{2} /\ RCPA_Wrap.k{1} = Sec.RCPA.RCPA_Wrap.k{2}); auto.
  by auto.
  congr.
  byequiv (: ={glob A} ==> ={res})=> //; proc; inline *.
  wp; call (: ={glob RCPA_QueryBounder}).
  proc; sp; if=> //; last by sim.
  inline *; wp; rnd; auto => />; smt(leak_pad).
  by auto.
  qed.
```

---

# Agent View Timeline Report

每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。

**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview 会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。

`Action time` 从每个 run 第一条 agent `submit_proof_intent` 的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 manager result 到这次提交的间隔；`Manager time` 是本 intent 的 manager/EasyCrypt 处理时间。

`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 `--quality-file` 传入 JSON 覆盖。

## 2026-06-11_1818_MtE_security

Run dir: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_MtE_security/r01/2026-06-11_1818_MtE_security/iteration_1`

t=0: `2026-06-12T01:20:37.200000+00:00`


### Tree-0.0

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.0-1 | +00:00 | [think](./views/Tree_0_0/thinking/turn_001.md) | 4.8 s | [manager_bootstrap_0_0.json](./views/_bootstrap/manager_bootstrap_0_0.json) | commit apply (RCPA_WUF_RCPA.RCPA_preservation (<: PadThenEncrypt(IV_Wrap(CBC... | probability / pr / probability, 1 goal, goal 600 chars | rejected commit: [error] the given proof-term proves: |  |

### Tree-0.1

| View | Action time | Agent think | Manager time | Decision View (full · inline read) | Intent | State Seen | Result | 质量判断 |
|---|---:|---:|---:|---|---|---|---|---|
| T0.1-1 | +00:10 | [think](./views/Tree_0_1/thinking/turn_001.md) | 4.7 s | [manager_bootstrap_0_1.json](./views/_bootstrap/manager_bootstrap_0_1.json) | commit apply (RCPA_WUF_RCPA.RCPA_preservation (<: PadThenEncrypt(IV_Wrap(CBC... | probability / pr / probability, 1 goal, goal 600 chars | rejected commit: [error] the given proof-term proves: |  |
| T0.1-2 | +03:06 | [171.4 s](./views/Tree_0_1/thinking/turn_002.md) | 616 ms | [turn_001.json](./views/Tree_0_1/turn_001.json) · [inline read](./views/Tree_0_1/followups/turn_001.md) | commit have RP := RCPA_WUF_RCPA.RCPA_preservation (<: PadThenEncrypt(IV_Wrap... | probability / pr / probability, 1 goal, goal 600 chars | accepted commit |  |
| T0.1-3 | +05:45 | 158.2 s | 812 ms | [turn_002.json](./views/Tree_0_1/turn_002.json) · [inline read](./views/Tree_0_1/followups/turn_002.md) | commit have Mkg_ll: islossless MAC.keygen by proc; auto=> />; smt(d_mK_uffu) | probability / pr / probability, 1 goal, goal 1259 chars | accepted commit |  |
| T0.1-4 | +05:57 | [11.2 s](./views/Tree_0_1/thinking/turn_004.md) | 755 ms | [turn_003.json](./views/Tree_0_1/turn_003.json) · [inline read](./views/Tree_0_1/followups/turn_003.md) | commit have Mtag_ll: islossless MAC.tag by proc; auto | probability / pr / probability, 1 goal, goal 1289 chars | accepted commit |  |
| T0.1-5 | +06:04 | 6.3 s | 653 ms | [turn_004.json](./views/Tree_0_1/turn_004.json) · [inline read](./views/Tree_0_1/followups/turn_004.md) | commit rewrite -(RP Mkg_ll Mtag_ll) | probability / pr / probability, 1 goal, goal 1317 chars | accepted commit |  |
| T0.1-6 | +06:13 | [8.4 s](./views/Tree_0_1/thinking/turn_006.md) | 617 ms | [turn_005.json](./views/Tree_0_1/turn_005.json) · [inline read](./views/Tree_0_1/followups/turn_005.md) | commit do 2!congr | probability / pr / probability, 1 goal, goal 1280 chars | accepted commit |  |
| T0.1-7 | +07:29 | 74.8 s | 185 ms | [turn_006.json](./views/Tree_0_1/turn_006.json) · [inline read](./views/Tree_0_1/followups/turn_006.md) | commit byequiv (: ={glob A} ==> ={res})=> // | probability / pr / probability, 2 goals, goal 1128 chars | accepted commit |  |
| T0.1-8 | +07:36 | 6.8 s | 242 ms | [turn_007.json](./views/Tree_0_1/turn_007.json) · [inline read](./views/Tree_0_1/followups/turn_007.md) | commit proc; inline * | equiv / prhl_module / relational_program, 2 goals, goal 1317 chars | accepted commit |  |
| T0.1-9 | +07:43 | 6.8 s | 193 ms | [turn_008.json](./views/Tree_0_1/turn_008.json) · [inline read](./views/Tree_0_1/followups/turn_008.md) | commit wp; call (: ={glob RCPA_QueryBounder} /\ RCPA_Wrap.k{1} = Sec.RCPA.RCPA_Wrap.k{2}) | pRHL / call_site / relational_program, 2 goals, goal 2401 chars | accepted commit |  |
| T0.1-10 | +07:53 | [10.7 s](./views/Tree_0_1/thinking/turn_010.md) | 309 ms | [turn_009.json](./views/Tree_0_1/turn_009.json) · [inline read](./views/Tree_0_1/followups/turn_009.md) | commit proc; sp; if=> //; last by sim | equiv / prhl_module / relational_program, 3 goals, goal 1341 chars | accepted commit |  |
| T0.1-11 | +08:02 | [7.7 s](./views/Tree_0_1/thinking/turn_011.md) | 292 ms | [turn_010.json](./views/Tree_0_1/turn_010.json) · [inline read](./views/Tree_0_1/followups/turn_010.md) | commit inline * | pRHL / call_site / relational_program, 3 goals, goal 2089 chars | accepted commit |  |
| T0.1-12 | +08:30 | 28.7 s | 309 ms | [turn_011.json](./views/Tree_0_1/turn_011.json) · [inline read](./views/Tree_0_1/followups/turn_011.md) | commit wp; while (={i0, p3, s, c4, key0} /\ RCPA_QueryBounder.qC{1} = RCPA_QueryBounder.qC{2} /\ RCP... | pRHL / procedure_body / relational_program, 3 goals, goal 4254 chars | accepted commit |  |
| T0.1-13 | +08:39 | [8.7 s](./views/Tree_0_1/thinking/turn_013.md) | 309 ms | [turn_012.json](./views/Tree_0_1/turn_012.json) · [inline read](./views/Tree_0_1/followups/turn_012.md) | commit by auto | pRHL / procedure_body / relational_program, 2 goals, goal 1762 chars | accepted commit |  |
| T0.1-14 | +09:19 | 39.4 s | 624 ms | [turn_013.json](./views/Tree_0_1/turn_013.json) · [inline read](./views/Tree_0_1/followups/turn_013.md) | commit congr | probability / pr / probability, 1 goal, goal 983 chars | accepted commit |  |
| T0.1-15 | +09:27 | 6.7 s | 277 ms | [turn_014.json](./views/Tree_0_1/turn_014.json) · [inline read](./views/Tree_0_1/followups/turn_014.md) | commit byequiv (: ={glob A} ==> ={res})=> //; proc; inline * | probability / pr / probability, 1 goal, goal 974 chars | accepted commit |  |
| T0.1-16 | +09:33 | 5.8 s | 168 ms | [turn_015.json](./views/Tree_0_1/turn_015.json) · [inline read](./views/Tree_0_1/followups/turn_015.md) | commit wp; call (: ={glob RCPA_QueryBounder}) | pRHL / call_site / relational_program, 1 goal, goal 1844 chars | accepted commit |  |
| T0.1-17 | +09:39 | 5.7 s | 277 ms | [turn_016.json](./views/Tree_0_1/turn_016.json) · [inline read](./views/Tree_0_1/followups/turn_016.md) | commit proc; sp; if=> //; last by sim | equiv / prhl_module / relational_program, 2 goals, goal 1239 chars | accepted commit |  |
| T0.1-18 | +09:51 | 12.7 s | 350 ms | [turn_017.json](./views/Tree_0_1/turn_017.json) · [inline read](./views/Tree_0_1/followups/turn_017.md) | commit inline *; wp; rnd; auto => />; smt(leak_pad) | pRHL / call_site / relational_program, 2 goals, goal 1553 chars | accepted commit |  |
| T0.1-19 | +10:02 | [9.8 s](./views/Tree_0_1/thinking/turn_019.md) | 212 ms | [turn_018.json](./views/Tree_0_1/turn_018.json) · [inline read](./views/Tree_0_1/followups/turn_018.md) | commit by auto | pRHL / procedure_body / relational_program, 1 goal, goal 1439 chars | accepted commit |  |
| T0.1-20 | +10:07 | [4.8 s](./views/Tree_0_1/thinking/turn_020.md) | 186 ms | [turn_019.json](./views/Tree_0_1/turn_019.json) · [inline read](./views/Tree_0_1/followups/turn_019.md) | commit qed | ambient / closed_candidate, goal 25 chars | accepted commit |  |
| T0.1-21 | +10:16 | 9 s |  | [turn_020.json](./views/Tree_0_1/turn_020.json) · [inline read](./views/Tree_0_1/followups/turn_020.md) | finish | complete / unknown / closed_candidate, 0 goals, goal 11 chars | finish requested |  |
