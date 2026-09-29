## Pure Logic — close with smt / rewrite

**Goal shape:** map membership tail

**Obligation families:**
- `sampling_bijection` — The remaining pure goal may include invertibility or lossless side conditions from an ear… (seen: distribution or lossless token remains visible; add/sub expression remains visible) (NOT: No distribution lemma is selected by this surface.)
- `map_update_projection` — The pure goal contains finite-map update or lookup structure whose key/projection equalit… (NOT: The surface does not rewrite any map expression.)
- `constructor_projection` — The pure goal exposes tuple/record projections or constructor equalities that can connect… (NOT: Projection equalities are reported only when visible in the current t…)
- `map_membership_preservation` — The remaining membership obligation relates an updated map key to a list or set membershi… (NOT: The surface reports the alignment facts currently visible; it does no…)
- `quantified_residual_logic` — The current proof point is dominated by local logical obligations rather than program-fro… (seen: universal quantifier visible; implication residual visible) (NOT: Quantifier names are not normalized across EasyCrypt pretty-printer v…)

**Alignment gap to feed smt:** [{"signal": "map_key_membership_head_alignment", "confidence": "medium", "gap": "Map update key head and membership/list head are both visible, but no equality path between them is visible.", "evidence": ["map update ke…

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &1 &2,
  (c2{1} = c1{2} /\
   n{1} = n{2} /\
   a{1} = a{2} /\
   p0{1} = p0{2} /\
   p{1}.`1 = n{1} /\
   p{2}.`1 = n{2} /\
   Mem.log{1} = Mem.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   BNR.lenc{1} = BNR.lenc{2} /\
   BNR.ndec{1} = BNR.ndec{2} /\
   ! (n{1} \in BNR.lenc{1}) /\
   (forall (nn : nonce) (ci : C.counter),
      (nn, ci) \in SplitC2.I1.RO.m{1} => nn \in BNR.lenc{1}) /\
   (forall (nn : nonce) (ci : C.counter),
      (nn, ci) \in SplitC2.I2.RO.m{1} => nn \in BNR.lenc{1}) /\
   forall (nn : nonce) (ci : C.counter),
     (nn, ci) \in SplitD.ROF.RO.m{1} => nn = n{1} \/ (nn \in BNR.lenc{1})) =>
  let x0_L = (n{1}, C.ofintd 0) in
  forall (r5_0 : poly_in),
    r5_0 \in dpoly_in =>
    (forall (tR : poly_out),
       tR \in dpoly_out =>
       tR =
       tR - poly1305_eval r5_0 (topol a{1} c2{1}) +
       poly1305_eval r5_0 (topol a{1} c2{1})) &&
    forall (r6L : poly_out),
      r6L \in dpoly_out =>
      r6L =
      r6L + poly1305_eval r5_0 (topol a{1} c2{1}) -
      poly1305_eval r5_0 (topol a{1} c2{1}) &&
      forall (r4_0 : extra_block),
        r4_0 \in dextra_block =>
        if x0_L \notin SplitC1.I2.RO.m{1} then
          (n{1} = n{2} /\
           a{1} = a{2} /\
           c2{1} = c1{2} /\
           poly1305
             (mk_rs
                (SplitC1.ofpair
                   (SplitC2.ofpair
                      (oget SplitC2.I1.RO.m{1}.[x0_L <- r5_0].[x0_L],
                       oget SplitC2.I2.RO.m{1}.[x0_L <- r6L].[x0_L]),
                    oget SplitC1.I2.RO.m{1}.[x0_L <- r4_0].[x0_L]))).`1
             (mk_rs
                (SplitC1.ofpair
                   (SplitC2.ofpair
                      (oget SplitC2.I1.RO.m{1}.[x0_L <- r5_0].[x0_L],
                       oget SplitC2.I2.RO.m{1}.[x0_L <- r6L].[x0_L]),
                    oget SplitC1.I2.RO.m{1}.[x0_L <- r4_0].[x0_L]))).`2
             (topol a{1} c2{1}) =
           r6L + poly1305_eval r5_0 (topol a{1} c2{1})) /\
          inv_cpa SplitC2.I1.RO.m{1}.[x0_L <- r5_0]
            SplitC2.I2.RO.m{1}.[x0_L <- r6L]
            Mem.
              log{1}.[n{1}, a{1}, c2{1}, poly1305
                                           (mk_rs
                                              (SplitC1.ofpair
                                                 (SplitC2.ofpair
                                                    (oget
                                                       SplitC2.I1.RO.
                                                         m{1}.[x0_L <- r5_0].[x0_L],
                                                     oget
                                                       SplitC2.I2.RO.
                                                         m{1}.[x0_L <- r6L].[x0_L]),
                                                  oget
                                                    SplitC1.I2.RO.
                                                      m{1}.[x0_L <- r4_0].[x0_L]))).`1
                                           (mk_rs
                                              (SplitC1.ofpair
                                                 (SplitC2.ofpair
                                                    (oget
                                                       SplitC2.I1.RO.
                                                         m{1}.[x0_L <- r5_0].[x0_L],
                                                     oget
                                                       SplitC2.I2.RO.
                                                         m{1}.[x0_L <- r6L].[x0_L]),
                                                  oget
                                                    SplitC1.I2.RO.
                                                      m{1}.[x0_L <- r4_0].[x0_L]))).`2
                                           (topol a{1} c2{1}) <- p0{1}]
            Mem.
              log{2}.[n{2}, a{2}, c1{2}, r6L +
                                         poly1305_eval r5_0
                                           (topol a{1} c2{1}) <- p0{2}] Mem.
            lc{1} Mem.lc{2} (p{1}.`1 :: BNR.lenc{1}) (p{2}.`1 :: BNR.lenc{2})
            BNR.ndec{1} BNR.ndec{2} /\
          forall (n2 : nonce) (c5 : C.counter),
            (n2, c5) \in SplitD.ROF.RO.m{1} =>
            n2 = p{1}.`1 \/ (n2 \in BNR.lenc{1})
        else
          (n{1} = n{2} /\
           a{1} = a{2} /\
           c2{1} = c1{2} /\
           poly1305
             (mk_rs
                (SplitC1.ofpair
                   (SplitC2.ofpair
                      (oget SplitC2.I1.RO.m{1}.[x0_L <- r5_0].[x0_L],
                       oget SplitC2.I2.RO.m{1}.[x0_L <- r6L].[x0_L]),
                    oget SplitC1.I2.RO.m{1}.[x0_L]))).`1
             (mk_rs
                (SplitC1.ofpair
                   (SplitC2.ofpair
                      (oget SplitC2.I1.RO.m{1}.[x0_L <- r5_0].[x0_L],
                       oget SplitC2.I2.RO.m{1}.[x0_L <- r6L].[x0_L]),
                    oget SplitC1.I2.RO.m{1}.[x0_L]))).`2 (topol a{1} c2{1}) =
           r6L + poly1305_eval r5_0 (topol a{1} c2{1})) /\
          inv_cpa SplitC2.I1.RO.m{1}.[x0_L <- r5_0]
            SplitC2.I2.RO.m{1}.[x0_L <- r6L]
            Mem.
              log{1}.[n{1}, a{1}, c2{1}, poly1305
                                           (mk_rs
                                              (SplitC1.ofpair
                                                 (SplitC2.ofpair
                                                    (oget
                                                       SplitC2.I1.RO.
                                                         m{1}.[x0_L <- r5_0].[x0_L],
                                                     oget
                                                       SplitC2.I2.RO.
                                                         m{1}.[x0_L <- r6L].[x0_L]),
                                                  oget
                                                    SplitC1.I2.RO.m{1}.[x0_L]))).`1
                                           (mk_rs
                                              (SplitC1.ofpair
                                                 (SplitC2.ofpair
                                                    (oget
                                                       SplitC2.I1.RO.
                                                         m{1}.[x0_L <- r5_0].[x0_L],
                                                     oget
                                                       SplitC2.I2.RO.
                                                         m{1}.[x0_L <- r6L].[x0_L]),
                                                  oget
                                                    SplitC1.I2.RO.m{1}.[x0_L]))).`2
                                           (topol a{1} c2{1}) <- p0{1}]
            Mem.
              log{2}.[n{2}, a{2}, c1{2}, r6L +
                                         poly1305_eval r5_0
                                           (topol a{1} c2{1}) <- p0{2}] Mem.
            lc{1} Mem.lc{2} (p{1}.`1 :: BNR.lenc{1}) (p{2}.`1 :: BNR.lenc{2})
            BNR.ndec{1} BNR.ndec{2} /\
          forall (n2 : nonce) (c5 : C.counter),
            (n2, c5) \in SplitD.ROF.RO.m{1} =>
            n2 = p{1}.`1 \/ (n2 \in BNR.lenc{1})
[380|check]>
```

## Status
remaining **4** · phase `relational_program` / `ambient_logic`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `probe_tactic` `rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_set…`
- result: Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.

```json
{"turn":56,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_set_sameE oget_some mem_set)."}},"ok":true,"manager_note":"Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed.","timing":"809 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
