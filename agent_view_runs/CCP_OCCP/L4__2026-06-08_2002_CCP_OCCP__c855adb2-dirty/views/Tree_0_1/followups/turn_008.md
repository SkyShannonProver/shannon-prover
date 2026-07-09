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
  (n{2}, a{2}, p{2}) = nap{2} /\
  c{2} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{2}) k{2} n{2} 1 p{2} /\
  t{2} = genpoly1305 (cc OCC.gs{2}) k{2} n{2} (topol a{2} c{2}) /\
  (n{1}, a{1}, p{1}) = nap{1} /\
  ((k{1}, nap{1}).`1 = (k{2}, nap{2}).`1 /\
   (k{1}, nap{1}).`2 = (k{2}, nap{2}).`2) /\
  OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}

c <@ ChaCha(OCC(I)).enc(k, n, p)   (1)                           
t <@ Poly(OCC(I)).mac(k, n, a, c)  (2)                           

post =
  (n{1}, a{1}, c{1}, t{1}) = (n{2}, a{2}, c{2}, t{2}) /\
  OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}
[214|check]>
```

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- frontier: left side only at `c <@ ChaCha(OCC(I)).enc(k, n, p)`
- frontier: left side only at `t <@ Poly(OCC(I)).mac(k, n, a, c)`

**Invariant must carry:**
- `={glob I}`
- `={OCC.gs}`

**Frame facts at risk:**
- `={OCC.gs}` needed by current_goal but NOT carried by call #2 → rewind: submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_2_1fd08c73d639ba86"}}`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **3** · phase `relational_program` / `call_site`

### Need more? submit one of these read-only requests
- No fresh recommendation is available for an equivalence goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "equiv_bridge_lemmas"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `sp.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/CCP_OCCP/r01/2026-06-08_2002_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
