## Opener — reduce the probability goal

**Goal shape:** a Pr-difference / distinguishing-advantage bound relating 11 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

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
  (iota_ 0 qdec) +
Pr[UFCMA_l.f() @ &m : false] <=
BRA.big predT<:int>
  (fun (i : int) =>
     Pr[UFCMA_l.f() @ &m :
        (nth (w1, w2) UFCMA_l.lbad1 i).`1 = (nth (w1, w2) UFCMA_l.lbad1 i).`2])
  (iota_ 0 qdec)
[423|check]>
```

## Status
remaining **1** · phase `probability` / `pr`

_Need richer context? `inspect_context` topics: `goal_info` · `pr_bridge_routes` · `equiv_bridge_lemmas` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `rewrite R0.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium2_more/l4_checked_action_surface/chacha_step4_lbad1_sum/r01/2026-06-08_1827_step4_lbad1_sum/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
