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
             p, p0 : plaintext, c, c0 : ciphertext}
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

p0 <- p                                            (1)  p0 <- p                                           
nap <- p0                                          (2)  nap <- p0                                         
(n, a, p1) <- nap                                  (3)  (n, a, p1) <- nap                                 
c1 <@ EncRnd.cc(n, p1)                             (4)  c1 <@ EncRnd.cc(n, p1)                            
t <@                                               (5)  t <@                                              
  UFCMA_l.set_bad1(map                             ( )    UFCMA_li.set_bad1(map                           
                     (fun (c2 : ciphertext) =>     ( )                        (fun (c2 : ciphertext) =>   
                        c2.`4)                     ( )                           c2.`4)                   
                     (filter                       ( )                        (filter                     
                        (fun (c2 : ciphertext) =>  ( )                           (fun (c2 : ciphertext) =>
                           c2.`1 = n)              ( )                              c2.`1 = n)            
                        Mem.lc))                   ( )                           Mem.lc))                 
RO.sample(n, C.ofintd 0)                           (6)  RO.sample(n, C.ofintd 0)                          

post =
  ((((n{1}, C.ofintd 0), witness<:poly_out>).`1 =
    ((n{2}, C.ofintd 0), witness<:poly_out>).`1 /\
    ((n{1}, C.ofintd 0), witness<:poly_out>).`2 =
    ((n{2}, C.ofintd 0), witness<:poly_out>).`2) /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}) &&
  forall (result_L result_R : unit) (m_L m_R : (nonce * C.counter,
    poly_out) fmap),
    result_L = result_R /\ m_L = m_R =>
    let c0_R = (n{2}, a{2}, c1{2}, t{2}) in
    let c0_L = (n{1}, a{1}, c1{1}, t{1}) in
    c0_L = c0_R /\
    (p{1}.`1 :: BNR.lenc{1} = p{2}.`1 :: BNR.lenc{2} /\
     BNR.ndec{1} = BNR.ndec{2} /\
     Mem.log{1}.[c0_L <- p0{1}] = Mem.log{2}.[c0_R <- p0{2}] /\
     Mem.lc{1} = Mem.lc{2} /\
     UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] =
     UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
     RO.m{1} = RO.m{2} /\
     m_L = m_R /\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    UFCMA_li.i{2} = nth0 /\
    (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
    (nth0 < size UFCMA_l.lbad1{2} =>
     (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
     (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})
[430|check]>
```

**Last action:** `by auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
