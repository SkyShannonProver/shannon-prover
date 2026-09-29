## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier — absorb with `sp`/`wp`: no left-side setup before this frontier
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
Current goal (remaining: 5)

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
&1 (left ) : {b : bool, c0 : ctxt, ek : eK, p, p0 : ptxt option, mk : mK,
             t : tag, c, ct : ctxt * tag, k : eK * mK}
&2 (right) : {b, b0 : bool, c, m : ctxt, t, t0 : tag, ct : ctxt * tag}

pre =
  (b{1} = b0{2} /\
   c0{1} = m{2} /\
   t{1} = t0{2} /\
   c{1} = (m{2}, t0{2}) /\
   ek{1} = CMAa.ek{2} /\
   p0{1} = None<:ptxt> /\
   ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
   CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
   CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
   !CTXT_Wrap.win{1} /\
   !MACa.SUF_CMA.SUF_Wrap.win{2} /\
   forall (c1 : ctxt) (t1 : tag),
     (c1, t1) \in MACa.SUF_CMA.SUF_Wrap.s{2} =>
     dec CMAa.ek{2} c1 <> None<:ptxt>) /\
  b{1}

if (b) {                   (1--)  MACa.SUF_CMA.SUF_Wrap.win <-  
                           (  -)    MACa.SUF_CMA.SUF_Wrap.win \/
                           (  -)    b0 /\                       
                           (  -)    ((m, t0) \notin             
                           (  -)     MACa.SUF_CMA.SUF_Wrap.s)   
  p0 <@ E.dec(ek, c0)      (1.1)                                
}                          (1--)                                
p <- p0                    (2--)  b <- b0                       
CTXT_Wrap.win <-           (3--)                                
  CTXT_Wrap.win \/         (  -)                                
  p <> None<:ptxt> /\      (  -)                                
  (c \notin CTXT_Wrap.s)   (  -)                                

post =
  !MACa.SUF_CMA.SUF_Wrap.win{2} =>
  (p{1} <> None<:ptxt>) = b{2} /\
  ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
  CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
  CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
  !CTXT_Wrap.win{1} /\
  forall (c1 : ctxt) (t1 : tag),
    (c1, t1) \in MACa.SUF_CMA.SUF_Wrap.s{2} =>
    dec CMAa.ek{2} c1 <> None<:ptxt>
[147|check]>
```

## Status
remaining **5** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `case (b{1}).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
