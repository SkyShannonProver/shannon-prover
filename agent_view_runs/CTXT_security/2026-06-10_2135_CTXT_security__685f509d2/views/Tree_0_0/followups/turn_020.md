## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–5) — absorb with `sp`/`wp`: 5 setup statement(s): k <- CTXT_Wrap.k; ct <- c; p0 <- None<:ptxt>; ... (2 more)
- frontier: both sides at `b <@ M.verify(mk, c0, t)`
- frontier: left side only at `p0 <@ E.dec(ek, c0)`
- frontier: left side only at `if (b) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
dec: eK -> ctxt -> ptxt option
dec_sem: forall (ge : (glob E)) (_k : eK) (_c : ctxt),
           hoare[ E.dec :
                   (glob E) = ge /\ k = _k /\ c = _c ==>
                   (glob E) = ge /\ res = dec _k _c ]
E_corr: forall (_k : eK) (_p : ptxt),
          hoare[ E.enc : k = _k /\ p = _p ==> dec _k res = Some _p ]
dec_ph: forall (ge : (glob E)) (_k : eK) (_c : ctxt),
          phoare[ E.dec :
                   (glob E) = ge /\ k = _k /\ c = _c ==>
                   (glob E) = ge /\ res = dec _k _c] = 1%r
------------------------------------------------------------------------
&1 (left ) : {b : bool, c0 : ctxt, ek : eK, p, p0 : ptxt option, mk : mK,
             t : tag, c, ct : ctxt * tag, k : eK * mK}
&2 (right) : {b, b0 : bool, c, m : ctxt, t, t0 : tag, ct : ctxt * tag}

pre =
  !MACa.SUF_CMA.SUF_Wrap.win{2} /\
  c{1} = ct{2} /\
  ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
  CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
  CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
  CTXT_Wrap.win{1} = MACa.SUF_CMA.SUF_Wrap.win{2} /\
  forall (ct0 : ctxt * tag),
    ct0 \in MACa.SUF_CMA.SUF_Wrap.s{2} =>
    dec CMAa.ek{2} ct0.`1 <> None<:ptxt>

k <- CTXT_Wrap.k           (1--)  (c, t) <- ct                          
ct <- c                    (2--)  m <- c                                
p0 <- None<:ptxt>          (3--)  t0 <- t                               
(ek, mk) <- k              (4--)  b0 <@                                 
                           (  -)    M.verify(MACa.SUF_CMA.SUF_Wrap.k, m,
                           (  -)      t0)                               
(c0, t) <- ct              (5--)  MACa.SUF_CMA.SUF_Wrap.win <-          
                           (  -)    MACa.SUF_CMA.SUF_Wrap.win \/        
                           (  -)    b0 /\                               
                           (  -)    ((m, t0) \notin                     
                           (  -)     MACa.SUF_CMA.SUF_Wrap.s)           
b <@ M.verify(mk, c0, t)   (6--)  b <- b0                               
if (b) {                   (7--)                                        
  p0 <@ E.dec(ek, c0)      (7.1)                                        
}                          (7--)                                        
p <- p0                    (8--)                                        
CTXT_Wrap.win <-           (9--)                                        
  CTXT_Wrap.win \/         (  -)                                        
  p <> None<:ptxt> /\      (  -)                                        
  (c \notin CTXT_Wrap.s)   (  -)                                        

post =
  !MACa.SUF_CMA.SUF_Wrap.win{2} =>
  (p{1} <> None<:ptxt>) = b{2} /\
  ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
  CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
  CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
  CTXT_Wrap.win{1} = MACa.SUF_CMA.SUF_Wrap.win{2} /\
  forall (ct0 : ctxt * tag),
    ct0 \in MACa.SUF_CMA.SUF_Wrap.s{2} =>
    dec CMAa.ek{2} ct0.`1 <> None<:ptxt>
[143|check]>
```

## Status
remaining **4** · phase `seq_cut` / `call_site`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The current cut or frontier context may expose a call route.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- The visible cut may depend on LHS/RHS statement alignment or missing live facts.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`
- Need the valid form for call, seq, while, rnd, or rewrite.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The visible cut/frontier may need indexed `sp i j` before branch tactics.
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

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `proc; inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
