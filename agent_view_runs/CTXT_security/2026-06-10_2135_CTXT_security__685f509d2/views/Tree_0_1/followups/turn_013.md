## 🎯 Current Goal
```
Current goal (remaining: 6)

Type variables: <none>

&m: {}
dec: eK -> ctxt -> ptxt option
dec_sem: forall (ge : (glob E)) (_k : eK) (_c : ctxt),
           hoare[ E.dec :
                   (glob E) = ge /\ k = _k /\ c = _c ==>
                   (glob E) = ge /\ res = dec _k _c ]
enc_corr: forall (_k : eK) (_p : ptxt),
            hoare[ E.enc : k = _k /\ p = _p ==> dec _k res = Some _p ]
dec_ph: forall (ge : (glob E)) (k0 : eK) (c0 : ctxt),
          phoare[ E.dec :
                   (glob E) = ge /\ k = k0 /\ c = c0 ==>
                   (glob E) = ge /\ res = dec k0 c0] = 1%r
enc_eq: forall (k0 : eK) (p0 : ptxt),
          equiv[ E.enc  ~ E.enc :
                  ((glob E){1} = (glob E){2} /\ k{1} = k{2} /\ p{1} = p{2}) /\
                  k{1} = k0 /\ p{1} = p0 ==>
                  ((glob E){1} = (glob E){2} /\ res{1} = res{2}) /\
                  dec k0 res{1} = Some p0]
------------------------------------------------------------------------
forall &2,
  MACa.SUF_CMA.SUF_Wrap.win{2} => islossless CTXT_Wrap(EtM(E, M)).enc
[138|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `MACa.SUF_CMA.SUF_Wrap.win`
- `islossless`
- `CTXT_Wrap`
- `EtM`
- `enc`

**Visible hypotheses:**
- `dec: eK -> ctxt -> ptxt option`

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **6** · phase `relational_program` / `ambient_logic`

### Need more? submit one of these read-only requests
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

**Last action:** `sp 3 0; exlim ek{1}, p0{1} => ek0 pp0; wp; call (_: true); wp; call (enc_eq ek0…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
