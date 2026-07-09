## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
nth0: int
h0nth0: 0 <= nth0
hnth0q: nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {t : poly_out, lt : tag list}
&2 (right) : {t, t0 : poly_out, ti : tag, lt : tag list}

pre =
  (lt{1} = lt{2} /\
   (UFCMA.cbad1{1} = UFCMA.cbad1{2} /\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2}) /\
   UFCMA_li.i{2} = nth0 /\
   (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
   (nth0 < size UFCMA_l.lbad1{2} =>
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})) /\
  UFCMA.cbad1{2} < qenc /\
  size lt{2} <= qdec /\
  size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}

t <$ dpoly_out                          (1------)  t <$ dpoly_out                            
if (UFCMA.cbad1 < qenc /\               (2------)  if (UFCMA.cbad1 < qenc /\                 
    size lt <= qdec) {                  (  -----)      size lt <= qdec) {                    
  UFCMA_l.lbad1 <-                      (2.1----)    if (size UFCMA_l.lbad1 <= UFCMA_li.i <  
    UFCMA_l.lbad1 ++                    (    ---)        size UFCMA_l.lbad1 + size lt) {     
    map (fun (t' : tag) => (t, t')) lt  (    ---)                                            
                                        (2.1.1--)      ti <-                                 
                                        (      -)        nth witness<:tag> lt                
                                        (      -)          (UFCMA_li.i - size UFCMA_l.lbad1) 
                                        (2.1.2--)      t0 <$ dpoly_out                       
                                        (2.1.3--)      if (UFCMA_li.cbadi < 1) {             
                                        (2.1.3.1)        UFCMA_li.badi <-                    
                                        (       )          UFCMA_li.badi || t0 = ti          
                                        (2.1.3.2)        UFCMA_li.cbadi <- UFCMA_li.cbadi + 1
                                        (2.1.3--)      }                                     
                                        (2.1.4--)      t <- t0                               
                                        (2.1----)    }                                       
  UFCMA.cbad1 <- UFCMA.cbad1 + 1        (2.2----)    UFCMA_l.lbad1 <-                        
                                        (    ---)      UFCMA_l.lbad1 ++                      
                                        (    ---)      map (fun (t' : tag) => (t, t')) lt    
                                        (2.3----)    UFCMA.cbad1 <- UFCMA.cbad1 + 1          
}                                       (2------)  }                                         

post =
  t{1} = t{2} /\
  (UFCMA.cbad1{1} = UFCMA.cbad1{2} /\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2}) /\
  UFCMA_li.i{2} = nth0 /\
  (UFCMA_li.cbadi{2} = if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) /\
  (nth0 < size UFCMA_l.lbad1{2} =>
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2})
[435|check]>
```

**Last action:** `case (UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec /\ size UFCMA_l.lbad1{2} <= U…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
