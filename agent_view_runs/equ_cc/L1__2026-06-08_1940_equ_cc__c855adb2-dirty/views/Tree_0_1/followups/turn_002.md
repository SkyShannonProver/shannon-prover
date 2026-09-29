## 🎯 Current Goal
```
Current goal

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
&1 (left ) : {i : int, c : byte list, k, k0 : key, n, n0 : nonce,
             c0 : C.counter, x, x0, x1, x2, x3, x4, x5 : nonce * C.counter,
             r10, r4 : poly_in, r20, r5 : poly_out, r1 : poly,
             r2, r3 : extra_block, z, result, r, r0 : block, p : message}
&2 (right) : {i : int, c : byte list, n : nonce, z : block, p : message}

pre =
  (n{2}, p{2}) = ((k{1}, n{1}, p{1}).`2, (k{1}, n{1}, p{1}).`3) /\
  (n{2}, p{2}).`1 = n0 /\
  size (k{1}, n{1}, p{1}).`3 <= max_cipher_size /\
  ! (n0 \in BNR.lenc{1}) /\
  (forall (n1 : nonce) (c1 : C.counter),
     (n1, c1) \in ROF.m{1} => n1 \in BNR.lenc{1}) /\
  mr0 = ROin.m{1} /\ ms0 = ROout.m{1}

c <- []                                 (1--------)  p <-                                     
                                        (  -------)    map                                    
                                        (  -------)      (fun (_ : byte) => witness<:byte>)   
                                        (  -------)      p                                    
i <- 1                                  (2--------)  c <- []                                  
while (p <> []) {                       (3--------)  i <- 1                                   
  k0 <- k                               (3. 1-----)                                           
  n0 <- n                               (3. 2-----)                                           
  c0 <- C.ofintd i                      (3. 3-----)                                           
  x <- (n0{!1}, c0)                     (3. 4-----)                                           
  if (SplitD.test x) {                  (3. 5-----)                                           
    x0 <- x                             (3. 5. 1--)                                           
    x2 <- x0                            (3. 5. 2--)                                           
    x4 <- x2                            (3. 5. 3--)                                           
    r4 <$ dpoly_in                      (3. 5. 4--)                                           
    if (x4 \notin SplitC2.I1.RO.m) {    (3. 5. 5--)                                           
      SplitC2.I1.RO.m <-                (3. 5. 5.1)                                           
        SplitC2.I1.RO.m.[x4 <- r4]      (         )                                           
    }                                   (3. 5. 5--)                                           
    r10 <- oget SplitC2.I1.RO.m.[x4]    (3. 5. 6--)                                           
    x5 <- x2                            (3. 5. 7--)                                           
    r5 <$ dpoly_out                     (3. 5. 8--)                                           
    if (x5 \notin SplitC2.I2.RO.m) {    (3. 5. 9--)                                           
      SplitC2.I2.RO.m <-                (3. 5. 9.1)                                           
        SplitC2.I2.RO.m.[x5 <- r5]      (         )                                           
    }                                   (3. 5. 9--)                                           
    r20 <- oget SplitC2.I2.RO.m.[x5]    (3. 5.10--)                                           
    r1 <- SplitC2.ofpair (r10, r20)     (3. 5.11--)                                           
    x3 <- x0                            (3. 5.12--)                                           
    r3 <$ dextra_block                  (3. 5.13--)                                           
    if (x3 \notin SplitC1.I2.RO.m) {    (3. 5.14--)                                           
      SplitC1.I2.RO.m <-                (3. 5.14.1)                                           
        SplitC1.I2.RO.m.[x3 <- r3]      (         )                                           
    }                                   (3. 5.14--)                                           
    r2 <- oget SplitC1.I2.RO.m.[x3]     (3. 5.15--)                                           
    r <- SplitC1.ofpair (r1, r2)        (3. 5.16--)                                           
  } else {                              (3. 5-----)                                           
    x1 <- x                             (3. 5? 1--)                                           
    r0 <$ dblock                        (3. 5? 2--)                                           
    if (x1 \notin SplitD.ROF.RO.m) {    (3. 5? 3--)                                           
      SplitD.ROF.RO.m <-                (3. 5? 3.1)                                           
        SplitD.ROF.RO.m.[x1 <- r0]      (         )                                           
    }                                   (3. 5? 3--)                                           
    r <- oget SplitD.ROF.RO.m.[x1]      (3. 5? 4--)                                           
  }                                     (3. 5-----)                                           
  result <- r                           (3. 6-----)                                           
  z <- result                           (3. 7-----)                                           
  c <-                                  (3. 8-----)                                           
    c ++                                (     ----)                                           
    take (size p)                       (     ----)                                           
      (bytes_of_block (extend p +^ z))  (     ----)                                           
  p <- drop block_size p                (3. 9-----)                                           
  i <- i + 1                            (3.10-----)                                           
}                                       (3--------)                                           
                                        (4--------)  while (p <> []) {                        
                                        (4. 1-----)    z <$ dblock                            
                                        (4. 2-----)    c <-                                   
                                        (     ----)      c ++ take (size p) (bytes_of_block z)
                                        (4. 3-----)    p <- drop block_size p                 
                                        (4. 4-----)    i <- i + 1                             
                                        (4--------)  }                                        

post =
  c{1} = c{2} /\
  size c{1} <= max_cipher_size /\
  mr0 = ROin.m{1} /\
  ms0 = ROout.m{1} /\
  forall (n1 : nonce) (c1 : C.counter),
    (n1, c1) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}
[357|check]>
```

**Last action:** `inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
