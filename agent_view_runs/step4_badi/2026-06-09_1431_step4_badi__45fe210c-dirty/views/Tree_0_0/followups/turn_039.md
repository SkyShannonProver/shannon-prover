## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
nth0: int
h0nth0: 0 <= nth0
hnth0q: nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {n : nonce, c1 : bytes, t : poly_out, a : associated_data,
             p1 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext} [programs are in sync]
&2 (right) : {n : nonce, c1 : bytes, t : poly_out, a : associated_data,
             p1 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext}

pre =
  (c{2} = witness<:ciphertext> /\
   c{1} = witness<:ciphertext> /\
   p{1} = p{2} /\
   (BNR.lenc{1} = BNR.lenc{2} /\
    BNR.ndec{1} = BNR.ndec{2} /\
    Mem.log{1} = Mem.log{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    UFCMA.log{1} = UFCMA.log{2} /\
    UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
    UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
    RO.m{1} = RO.m{2} /\
    SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
    SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
   UFCMA_li.i{2} = nth0 /\
   (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
   (nth0 < size UFCMA_l.lbad1{2} =>
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})) /\
  check_plaintext BNR.lenc{1} p{1}

(1)  p0 <- p                  
(2)  nap <- p0                
(3)  (n, a, p1) <- nap        

post =
  (((n{1}, p1{1}).`1 = (n{2}, p1{2}).`1 /\
    (n{1}, p1{1}).`2 = (n{2}, p1{2}).`2) /\
   RO.m{1} = RO.m{2}) &&
  forall (result_L result_R : bytes),
    result_L = result_R /\ RO.m{1} = RO.m{2} =>
    (map (fun (c2 : ciphertext) => c2.`4)
       (filter (fun (c2 : ciphertext) => c2.`1 = n{1}) Mem.lc{1}) =
     map (fun (c2 : ciphertext) => c2.`4)
       (filter (fun (c2 : ciphertext) => c2.`1 = n{2}) Mem.lc{2}) /\
     (UFCMA.cbad1{1} = UFCMA.cbad1{2} /\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2}) /\
     UFCMA_li.i{2} = nth0 /\
     (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
     (nth0 < size UFCMA_l.lbad1{2} =>
      (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
      (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})) &&
    forall (result_L0 result_R0 : poly_out) (cbad1_L : int) (lbad1_L : (tag *
      tag) list) (cbad1_R : int) (lbad1_R : (tag * tag) list) (badi_R : bool)
      (cbadi_R : int),
      result_L0 = result_R0 /\
      (cbad1_L = cbad1_R /\ lbad1_L = lbad1_R) /\
      UFCMA_li.i{2} = nth0 /\
      (cbadi_R = if nth0 < size lbad1_R then 1 else 0) /\
      (nth0 < size lbad1_R =>
       (nth (w1, w2) lbad1_R nth0).`1 = (nth (w1, w2) lbad1_R nth0).`2 =>
       badi_R) =>
      ((n{1}, C.ofintd 0) = (n{2}, C.ofintd 0) /\ RO.m{1} = RO.m{2}) &&
      forall (result_L1 result_R1 : unit) (m_L m_R : (nonce * C.counter,
        poly_in) fmap),
        result_L1 = result_R1 /\ m_L = m_R =>
        ((((n{1}, C.ofintd 0), witness<:poly_out>).`1 =
          ((n{2}, C.ofintd 0), witness<:poly_out>).`1 /\
          ((n{1}, C.ofintd 0), witness<:poly_out>).`2 =
          ((n{2}, C.ofintd 0), witness<:poly_out>).`2) /\
         SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}) &&
        forall (result_L2 result_R2 : unit) (m_L0 m_R0 : (nonce * C.counter,
          poly_out) fmap),
          result_L2 = result_R2 /\ m_L0 = m_R0 =>
          let c0_R = (n{2}, a{2}, result_R, result_R0) in
          let c0_L = (n{1}, a{1}, result_L, result_L0) in
          c0_L = c0_R /\
          (p{1}.`1 :: BNR.lenc{1} = p{2}.`1 :: BNR.lenc{2} /\
           BNR.ndec{1} = BNR.ndec{2} /\
           Mem.log{1}.[c0_L <- p0{1}] = Mem.log{2}.[c0_R <- p0{2}] /\
           Mem.lc{1} = Mem.lc{2} /\
           UFCMA.log{1}.[n{1} <- (a{1}, result_L, result_L0)] =
           UFCMA.log{2}.[n{2} <- (a{2}, result_R, result_R0)] /\
           cbad1_L = cbad1_R /\
           lbad1_L = lbad1_R /\
           m_L = m_R /\
           m_L0 = m_R0 /\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
          UFCMA_li.i{2} = nth0 /\
          (cbadi_R = if nth0 < size lbad1_R then 1 else 0) /\
          (nth0 < size lbad1_R =>
           (nth (w1, w2) lbad1_R nth0).`1 = (nth (w1, w2) lbad1_R nth0).`2 =>
           badi_R)
[448|check]>
```

**Last action:** `by sim.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
