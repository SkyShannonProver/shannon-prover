## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {k : key, n : nonce, c : bytes, a : associated_data,
             p : message, nap : nonce * associated_data * message, t : tag}
&2 (right) : {k : key, n : nonce, c : bytes, t : poly_out,
             a : associated_data, p : message,
             nap : nonce * associated_data * message}

pre =
  n{1} = n{2} /\
  a{1} = a{2} /\
  p{1} = p{2} /\
  k{1} = k{2} /\ (glob I){1} = (glob I){2} /\ OCC.gs{1} = OCC.gs{2}

c <@ ChaCha(OCC(I)).enc(k, n, p)   (1)  c <-                            
                                   ( )    gen_CTR_encrypt_bytes take_xor
                                   ( )      (cc OCC.gs) k n 1 p         
t <@ Poly(OCC(I)).mac(k, n, a, c)  (2)  t <-                            
                                   ( )    genpoly1305 (cc OCC.gs) k n   
                                   ( )      (topol a c)                 

post =
  (n{1}, a{1}, c{1}, t{1}) = (n{2}, a{2}, c{2}, t{2}) /\
  (glob I){1} = (glob I){2} /\ OCC.gs{1} = OCC.gs{2}
[216|check]>
```

**Last action:** `auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
