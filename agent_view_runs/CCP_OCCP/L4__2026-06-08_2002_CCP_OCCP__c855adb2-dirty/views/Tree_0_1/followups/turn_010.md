## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

gs0: globS
k0: key
n0: nonce
a0: associated_data
c0: bytes
gs1: globS
k1: key
n1: nonce
p1: message
------------------------------------------------------------------------
&1 (left ) : {k : key, n : nonce, c : bytes, a : associated_data,
             p : message, nap : nonce * associated_data * message, t : tag}
&2 (right) : {k : key, n : nonce, c : bytes, t : poly_out,
             a : associated_data, p : message,
             nap : nonce * associated_data * message}

pre =
  (gs1 = OCC.gs{1} /\ k1 = k{1} /\ n1 = n{1} /\ p1 = p{1}) /\
  (gs0 = OCC.gs{1} /\ k0 = k{1} /\ n0 = n{1} /\ a0 = a{1} /\ c0 = c{1}) /\
  (n{2}, a{2}, p{2}) = nap{2} /\
  c{2} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{2}) k{2} n{2} 1 p{2} /\
  t{2} = genpoly1305 (cc OCC.gs{2}) k{2} n{2} (topol a{2} c{2}) /\
  (n{1}, a{1}, p{1}) = nap{1} /\
  ((k{1}, nap{1}).`1 = (k{2}, nap{2}).`1 /\
   (k{1}, nap{1}).`2 = (k{2}, nap{2}).`2) /\
  OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}


post =
  ((k{1}, n{1}, p{1}).`1 = k1 /\
   (k{1}, n{1}, p{1}).`2 = n1 /\
   (k{1}, n{1}, p{1}).`3 = p1 /\ OCC.gs{1} = gs1) &&
  forall (result : bytes),
    result = gen_CTR_encrypt_bytes take_xor (cc gs1) k1 n1 1 p1 =>
    ((k{1}, n{1}, a{1}, result).`1 = k0 /\
     (k{1}, n{1}, a{1}, result).`2 = n0 /\
     (k{1}, n{1}, a{1}, result).`3 = a0 /\
     (k{1}, n{1}, a{1}, result).`4 = c0 /\ OCC.gs{1} = gs0) &&
    forall (result0 : tag),
      result0 = genpoly1305 (cc gs0) k0 n0 (topol a0 c0) =>
      (n{1}, a{1}, result, result0) = (n{2}, a{2}, c{2}, t{2}) /\
      OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}
[216|check]>
```

## Status
remaining **3** · phase `relational_program` / `prhl_module`

_Need richer context? `inspect_context` topics: `equiv_bridge_lemmas` · `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `exists* OCC.gs{1}, k{1}, n{1}, p{1}; elim* => gs1 k1 n1 p1; call{1} (chacha_spe…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
