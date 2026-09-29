## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

E : SKEa.Enc_Scheme{-SKEa.RCPA.RCPA_Wrap, -RCPA_Wrap, -RCPAa}
M : MACa.MAC_Scheme{-SKEa.RCPA.RCPA_Wrap, -RCPA_Wrap, -RCPAa, -E}
A(O : RCPA_Oracles) : RCPA_Adversary{-SKEa.RCPA.RCPA_Wrap, -RCPA_Wrap, -RCPAa, -E, -M}
&m: {}
Mkg_ll: islossless M.keygen
Mtag_ll: islossless M.tag
------------------------------------------------------------------------
&1 (left ) : {p, p0 : ptxt, c, r : ctxt, k : eK * mK}
&2 (right) : {p : ptxt, c, c0, r : ctxt, k : eK, t : tag,
             p0, p1 : ptxt * tag}

pre = p{1} = p{2} /\ true

k <- RCPA_Wrap.k           (1)  c <- witness<:ctxt>       
p0 <- p                    (2)  t <@ M.tag(RCPAa.mk, p)   
r <$ dC (leak p0)          (3)  p0 <- (p, t)              
c <- r                     (4)  k <- SKEa.RCPA.RCPA_Wrap.k
                           (5)  p1 <- p0                  
                           (6)  r <$ dC (leak p1.`1)      
                           (7)  c0 <- r                   
                           (8)  c <- c0                   

post = c{1} = c{2} /\ true
[50|check]>
```

**Last action:** `proc; inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_RCPA_preservation/r01/2026-06-11_1438_RCPA_preservation/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_RCPA_preservation/r01/2026-06-11_1438_RCPA_preservation/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_RCPA_preservation/r01/2026-06-11_1438_RCPA_preservation/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_renamed3_fable_l1/l1_goal_projection/mee_RCPA_preservation/r01/2026-06-11_1438_RCPA_preservation/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
