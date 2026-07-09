## Pure Logic — close with smt / rewrite

**Visible hypotheses:**
- `HP: forall (E : unit ->`
- `hsz: size UFCMA_l.lbad1{hr} <= qdec`
- `hp: p \in UFCMA_l.lbad1{hr}`
- `hpp: p.`1 = p.`2`
- `hnotin: ! (find (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} \in`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 3)

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
&hr: {res : unit}
hsz: size UFCMA_l.lbad1{hr} <= qdec
p: tag * tag
hp: p \in UFCMA_l.lbad1{hr}
hpp: p.`1 = p.`2
hnotin: ! (find (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} \in
           iota_ 0 qdec)
------------------------------------------------------------------------
false
[418|check]>
```

## Status
remaining **3** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `move=> &hr; split=> [|//]; move=> [[hsz [p [hp hpp]]] hnotin].` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
