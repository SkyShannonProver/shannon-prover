## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** apply (ler_sum _ (fun (a : int) => Pr[UFCMA_l.f() @ &m : (size UFCMA_l.lbad1 <= qdec /\ exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\ find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 = a]) _ _). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** read your goal's first instruction (after `~`, below the `==>`), then find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Evidence:**
- pure_tail_surface is visible for the current goal
- current proof state has no program-frontier work before the logical residual

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `constructor_projection`, `quantified_residual_logic`
- existential witness sources: `membership_member`, `membership_member`, `membership_member`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (see structural_checkpoints).

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
HP: forall (E : unit ->
                (glob A) * nonce list * int * int * (nonce, associated_data *
                message * tag) fmap * (tag * tag) list * (nonce * C.counter,
                poly_in) fmap * ciphertext list * (ciphertext,
                plaintext) fmap * (nonce * C.counter, poly_out) fmap *
                (nonce * C.counter, block) fmap -> unit -> bool)
      (phi : unit ->
             (glob A) * nonce list * int * int * (nonce, associated_data *
             message * tag) fmap * (tag * tag) list * (nonce * C.counter,
             poly_in) fmap * ciphertext list * (ciphertext, plaintext) fmap *
             (nonce * C.counter, poly_out) fmap * (nonce * C.counter,
             block) fmap -> unit -> int) (P : int list) &m0,
      uniq P =>
      Pr[UFCMA_l.f() @ &m0 :
         E tt
           ((glob A), BNR.lenc, BNR.ndec, UFCMA.cbad1, UFCMA.log,
            UFCMA_l.lbad1, RO.m, Mem.lc, Mem.log, SplitC2.I2.RO.m,
            SplitD.ROF.RO.m) res] =
      BRA.big predT<:int>
        (fun (a : int) =>
           Pr[UFCMA_l.f() @ &m0 :
              E tt
                ((glob A), BNR.lenc, BNR.ndec, UFCMA.cbad1, UFCMA.log,
                 UFCMA_l.lbad1, RO.m, Mem.lc, Mem.log, SplitC2.I2.RO.m,
                 SplitD.ROF.RO.m) res /\
              phi tt
                ((glob A), BNR.lenc, BNR.ndec, UFCMA.cbad1, UFCMA.log,
                 UFCMA_l.lbad1, RO.m, Mem.lc, Mem.log, SplitC2.I2.RO.m,
                 SplitD.ROF.RO.m) res =
              a]) P +
      Pr[UFCMA_l.f() @ &m0 :
         E tt
           ((glob A), BNR.lenc, BNR.ndec, UFCMA.cbad1, UFCMA.log,
            UFCMA_l.lbad1, RO.m, Mem.lc, Mem.log, SplitC2.I2.RO.m,
            SplitD.ROF.RO.m) res /\
         ! (phi tt
              ((glob A), BNR.lenc, BNR.ndec, UFCMA.cbad1, UFCMA.log,
               UFCMA_l.lbad1, RO.m, Mem.lc, Mem.log, SplitC2.I2.RO.m,
               SplitD.ROF.RO.m) res \in
            P)]
EQ: Pr[UFCMA_l.f() @ &m :
       size UFCMA_l.lbad1 <= qdec /\
       exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2] =
    BRA.big predT<:int>
      (fun (a : int) =>
         Pr[UFCMA_l.f() @ &m :
            (size UFCMA_l.lbad1 <= qdec /\
             exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\
            find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 = a])
      (iota_ 0 qdec) +
    Pr[UFCMA_l.f() @ &m :
       (size UFCMA_l.lbad1 <= qdec /\
        exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\
       ! (find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 \in
          iota_ 0 qdec)]
R0: Pr[UFCMA_l.f() @ &m :
       (size UFCMA_l.lbad1 <= qdec /\
        exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\
       ! (find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 \in
          iota_ 0 qdec)] =
    Pr[UFCMA_l.f() @ &m : false]
------------------------------------------------------------------------
BRA.big predT<:int>
  (fun (a : int) =>
     Pr[UFCMA_l.f() @ &m :
        (size UFCMA_l.lbad1 <= qdec /\
         exists (p : tag * tag), (p \in UFCMA_l.lbad1) /\ p.`1 = p.`2) /\
        find (fun (p : tag * tag) => p.`1 = p.`2) UFCMA_l.lbad1 = a])
  (iota_ 0 qdec) <=
BRA.big predT<:int>
  (fun (i : int) =>
     Pr[UFCMA_l.f() @ &m :
        (nth (w1, w2) UFCMA_l.lbad1 i).`1 = (nth (w1, w2) UFCMA_l.lbad1 i).`2])
  (iota_ 0 qdec)
[425|check]>
```

## Status
remaining **1** · phase `probability` / `pr`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Current Pr equality may need a manager-verified bridge route (game-hop or scheme/endpoint normalization) before direct …
  submit `{"intent": "inspect_context", "payload": {"topic": "pr_bridge_routes"}}`
- Need pRHL/procedure-equivalence bridge lemma names or context after checking pr_bridge_routes.
  submit `{"intent": "inspect_context", "payload": {"topic": "equiv_bridge_lemmas"}}`
- Need local lemma hints before choosing a Pr-level proof route.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need exact byphoare/phoare-loop tactic syntax before choosing the probability route.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "while"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `apply (ler_sum _ (fun (a : int) => Pr[UFCMA_l.f() @ &m : (size UFCMA_l.lbad1 <=…` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] This expression has type`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `rewrite RField.addr0.` → accepted
- commit `apply ler_sum => a _.` → REJECTED: [error] the given proof-term proves:
- commit `apply ler_sum.` → REJECTED: [error] the given proof-term proves:

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
