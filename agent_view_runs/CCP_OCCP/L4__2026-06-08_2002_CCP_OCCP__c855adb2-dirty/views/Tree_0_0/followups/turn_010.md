## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {k : key, n : nonce, c : bytes, a : associated_data,
             p : message, nap : nonce * associated_data * message, t : tag}
&2 (right) : {k : key, n : nonce, c : bytes, t : poly_out,
             a : associated_data, p : message,
             nap : nonce * associated_data * message}

pre =
  ((k{1}, nap{1}).`1 = (k{2}, nap{2}).`1 /\
   (k{1}, nap{1}).`2 = (k{2}, nap{2}).`2) /\
  OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}

(n, a, p) <- nap                   (1)  (n, a, p) <- nap                
c <@ ChaCha(OCC(I)).enc(k, n, p)   (2)  c <-                            
                                   ( )    gen_CTR_encrypt_bytes take_xor
                                   ( )      (cc OCC.gs) k n 1 p         
t <@ Poly(OCC(I)).mac(k, n, a, c)  (3)  t <-                            
                                   ( )    genpoly1305 (cc OCC.gs) k n   
                                   ( )      (topol a c)                 

post =
  (n{1}, a{1}, c{1}, t{1}) = (n{2}, a{2}, c{2}, t{2}) /\
  OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}
[213|check]>
```

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: (n, a, p) <- nap
- frontier: left side only at `c <@ ChaCha(OCC(I)).enc(k, n, p)`
- frontier: left side only at `t <@ Poly(OCC(I)).mac(k, n, a, c)`

**Invariant must carry:**
- `={glob I}`
- `={OCC.gs}`

**Frame facts at risk:**
- `={OCC.gs}` needed by current_goal but NOT carried by call #2 → rewind: submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_2_81d65872e8491dce"}}`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **3** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `proc.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)
**⚠️ I could not read a proof intent from the last message. Please reply with exactly one JSON object like: {"intent": "probe_tactic", "payload": {"tactic": "..."}} or {"intent": "inspect_context", "payload": {"topic": "goal_info"}}**
**health: `agent_protocol_stuck`**

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
