## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {i, i0 : int, ek, k0 : eK, s, pi, x : block, mk, k : mK,
             t : tag, p, p0, p1, m : msg, c, c0, p', c1 : block list,
             key : eK * mK}
&2 (right) : {i, i0 : int, ek, k1, key, key0, k2 : eK,
             iv, iv0, s, pi, x : block, mk, k0 : mK, t : tag,
             p, p0, p1, m : msg, m0 : msg * tag,
             c, c0, c1, c2, p2, c3, p3, c4 : block list, k : eK * mK}

pre =
  (c{2} = witness<:block list> /\
   c{1} = witness<:block list> /\
   p{1} = p{2} /\
   RCPA_Wrap.k{1} = RCPA_Wrap.k{2} /\
   RCPA_QueryBounder.qC{1} = RCPA_QueryBounder.qC{2}) /\
  RCPA_QueryBounder.qC{1} < q /\ size (pad (p{1}, witness<:tag>)) <= n

p0 <- p                            ( 1--)  p0 <- p                          
key <- RCPA_Wrap.k                 ( 2--)  k <- RCPA_Wrap.k                 
p1 <- p0                           ( 3--)  p1 <- p0                         
(ek, mk) <- key                    ( 4--)  (ek, mk) <- k                    
k <- mk                            ( 5--)  k0 <- mk                         
m <- p1                            ( 6--)  m <- p1                          
t <- mac k m                       ( 7--)  t <- mac k0 m                    
p' <- pad (p1, t)                  ( 8--)  k1 <- ek                         
s <$ d_block                       ( 9--)  m0 <- (p1, t)                    
c1 <- [s]                          (10--)  key <- k1                        
i0 <- 0                            (11--)  p2 <- pad m0                     
while (i0 < size p') {             (12--)  iv <$ d_block                    
  pi <- nth witness<:block> p' i0  (12.1)                                   
  k0 <- ek                         (12.2)                                   
  x <- Block.(-) s pi              (12.3)                                   
  s <- P k0 x                      (12.4)                                   
  c1 <- c1 ++ [s]                  (12.5)                                   
  i0 <- i0 + 1                     (12.6)                                   
}                                  (12--)                                   
c0 <- c1                           (13--)  key0 <- key                      
c <- c0                            (14--)  iv0 <- iv                        
                                   (15--)  p3 <- p2                         
                                   (16--)  s <- iv0                         
                                   (17--)  c4 <- [s]                        
                                   (18--)  i0 <- 0                          
                                   (19--)  while (i0 < size p3) {           
                                   (19.1)    pi <- nth witness<:block> p3 i0
                                   (19.2)    k2 <- key0                     
                                   (19.3)    x <- Block.(-) s pi            
                                   (19.4)    s <- P k2 x                    
                                   (19.5)    c4 <- c4 ++ [s]                
                                   (19.6)    i0 <- i0 + 1                   
                                   (19--)  }                                
                                   (20--)  c3 <- c4                         
                                   (21--)  c2 <- c3                         
                                   (22--)  c1 <- c2                         
                                   (23--)  c0 <- c1                         
                                   (24--)  c <- c0                          

post =
  c{1} = c{2} /\
  RCPA_Wrap.k{1} = RCPA_Wrap.k{2} /\
  RCPA_QueryBounder.qC{1} + 1 = RCPA_QueryBounder.qC{2} + 1
[68|check]>
```

**Last action:** `wp; inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_MEE_unfold/r01/2026-06-11_1430_MEE_unfold/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
