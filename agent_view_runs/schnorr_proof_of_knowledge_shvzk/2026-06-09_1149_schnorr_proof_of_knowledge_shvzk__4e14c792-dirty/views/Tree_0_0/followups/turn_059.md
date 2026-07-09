## Surgery — align or decompose the two sides

**Route:** align or decompose the two sides; don't transform the whole goal at once.

**Toolbox:**
- `case:` the divergent branch, then `rcondt`/`rcondf` to force guards.
- `conseq(:_==> ={<few equal vars>})` + `sim` on the identical prefix.
- `wp` (incl. `wp -N -N`) to absorb tails before `call`/`sim`.

**Yours:** which guard to `case`/`rcond`, the coupling, the smt lemmas.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, v, v0 : bool, i : int,
             h, a, a0, v1, v', a2, v2, v'0 : group,
             w0, r, z1, z3 : ZModE.exp,
             x, h0, x0, x1, h1, h2, h3, h4 : statement, w, w1 : witness,
             m, m0, m1, a1, a3 : message, s : secret,
             e, e0, e1, e2, e3, e4, e5 : challenge, z, z0, z2, z4 : response,
             t : message * challenge * response,
             to, to0, to1 : (message * challenge * response) option}
&2 (right) : {b : bool, h, a : group, w0, r, e1, z1 : ZModE.exp,
             x, x0, h0, h1 : statement, w, w1, w2 : witness,
             m, m0, a0 : message, s, r0 : secret, e, e0, e2 : challenge,
             z, z0 : response, t : message * challenge * response,
             sw : statement * witness, ms : message * secret}

pre = w0{1} = w0{2} /\ (glob D){1} = (glob D){2}


post =
  let x_L = g ^ w0{1} in
  forall (r1 : ZModE.exp),
    r1 \in dt =>
    let x0_R = g ^ w0{2} in
    (forall (e1R : ZModE.exp), e1R \in dt => e1R = e1R) &&
    forall (eL : challenge),
      eL \in de =>
      eL = eL &&
      (forall (rR : ZModE.exp),
         rR \in dt => rR = rR + eL * w0{2} - eL * w0{2}) &&
      forall (z1L : ZModE.exp),
        z1L \in dt =>
        z1L = z1L - eL * w0{2} + eL * w0{2} &&
        let r_R = z1L - eL * w0{2} in
        let m0_R = g ^ r_R in
        let m0_L = g ^ z1L * x_L ^ -eL in
        x_L = x0_R /\
        oget (Some (m0_L, eL, z1L)) =
        (m0_R, eL, (m0_R, r_R).`2 + eL * (x0_R, w0{2}).`2) /\
        (glob D){1} = (glob D){2}
[61|check]>
```

## Status
remaining **1** · phase `relational_program` / `procedure_body`

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

**Last action:** `wp.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
