## Pure Logic — close with smt / rewrite

**Goal operators:**
- `nth`
- `w1`
- `w2`
- `UFCMA_l.lbad1`
- `hr`

**Visible hypotheses:**
- `HP: forall (E : unit ->`
- `hsz: size UFCMA_l.lbad1{hr} <= qdec`
- `hp: p \in UFCMA_l.lbad1{hr}`
- `hpp: p.`1 = p.`2`
- `hfind: find (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} = a`
- `hh: has (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 2)

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
a: int
&hr: {res : unit}
hsz: size UFCMA_l.lbad1{hr} <= qdec
p: tag * tag
hp: p \in UFCMA_l.lbad1{hr}
hpp: p.`1 = p.`2
hfind: find (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} = a
hh: has (fun (p0 : tag * tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr}
------------------------------------------------------------------------
(nth (w1, w2) UFCMA_l.lbad1{hr} a).`1 = (nth (w1, w2) UFCMA_l.lbad1{hr} a).`2
[430|check]>
```

## Status
remaining **2** · phase `ambient_logic` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `have hh: has (fun (p0:tag*tag) => p0.`1 = p0.`2) UFCMA_l.lbad1{hr} by (apply/Li…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
