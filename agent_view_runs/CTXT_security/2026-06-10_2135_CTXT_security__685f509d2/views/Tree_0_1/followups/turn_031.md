## Surgery — align or decompose the two sides

**Where:**
- frontier: both sides at `ek <@ E.keygen()`
- frontier: both sides at `mk <@ M.keygen()`

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
Current goal

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
&1 (left ) : {ek : eK, mk : mK}
&2 (right) : {}

pre =
  (glob A){1} = (glob A){2} /\
  (glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}

ek <@ E.keygen()                   (1)  CMAa.ek <@ E.keygen()                
mk <@ M.keygen()                   (2)  MACa.SUF_CMA.SUF_Wrap.k <@ M.keygen()
CTXT_Wrap.k <- (ek, mk)            (3)  MACa.SUF_CMA.SUF_Wrap.s <-           
                                   ( )    fset0<:ctxt * tag>                 
CTXT_Wrap.s <- fset0<:ctxt * tag>  (4)  MACa.SUF_CMA.SUF_Wrap.win <- false   
CTXT_Wrap.win <- false             (5)                                       

post =
  (!MACa.SUF_CMA.SUF_Wrap.win{2} =>
   true /\
   (glob A){1} = (glob A){2} /\
   ((glob E){1} = (glob E){2} /\ (glob M){1} = (glob M){2}) /\
   CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
   CTXT_Wrap.s{1} = MACa.SUF_CMA.SUF_Wrap.s{2} /\
   !CTXT_Wrap.win{1} /\
   forall (c : ctxt) (t : tag),
     (c, t) \in MACa.SUF_CMA.SUF_Wrap.s{2} => dec CMAa.ek{2} c <> None<:ptxt>) &&
  forall (result_L result_R : unit) (A_L : (glob A)) (E_L : (glob E))
    (M_L : (glob M)) (s_L : (ctxt * tag) fset) (win_L : bool)
    (A_R : (glob A)) (E_R : (glob E)) (M_R : (glob M)) (s_R : (ctxt *
    tag) fset) (win_R : bool),
    (!win_R =>
     result_L = result_R /\
     A_L = A_R /\
     (E_L = E_R /\ M_L = M_R) /\
     CTXT_Wrap.k{1} = (CMAa.ek{2}, MACa.SUF_CMA.SUF_Wrap.k{2}) /\
     s_L = s_R /\
     !win_L /\
     forall (c : ctxt) (t : tag),
       (c, t) \in s_R => dec CMAa.ek{2} c <> None<:ptxt>) =>
    win_L => win_R
[157|check]>
```

## Status
remaining **1** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `by inline *; wp; call M_verify_ll; auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_ctxt_fable_l4np/l4_checked_action_surface/mee_CTXT_security/r01/2026-06-10_2135_CTXT_security/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
