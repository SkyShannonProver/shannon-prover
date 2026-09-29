## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b : bool, i0 : int}

pre = (glob A){1} = (glob A){2} /\ i0{2} = nth0

UFCMA_l.lbad1 <- []                  (1)  UFCMA_li.cbadi <- 0                
UFCMA.cbad1 <- 0                     (2)  UFCMA_li.badi <- false             
b <@                                 (3)  UFCMA_li.i <- i0                   
  CPA_game(CCA_CPA_Adv(BNR_Adv(A)),  ( )                                     
    UFCMA_l.O).main()                ( )                                     
                                     (4)  UFCMA_l.lbad1 <- []                
                                     (5)  UFCMA.cbad1 <- 0                   
                                     (6)  b <@                               
                                     ( )    CPA_game(CCA_CPA_Adv(BNR_Adv(A)),
                                     ( )      UFCMA_li.O).main()             

post =
  (let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) => UFCMA_li.
  badi{2}
[421|check]>
```

## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `named_handle_not_callable_in_current_view`; so step into the body or write a manual invariant.

**Candidate:**
- `UFCMA_genCC` (`call UFCMA_genCC.`)

**Frontier:**
- setup before the frontier (positions 1–2) — absorb with `sp`/`wp`: 2 setup statement(s): UFCMA_l.lbad1 <- []; UFCMA.cbad1 <- 0
- frontier: both sides at `b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA_l.O).main()`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

## Status
remaining **3** · phase `failure_diagnostic` / `call_site`

### Need more? submit one of these read-only requests
- proof-state analysis has a dataflow invariant skeleton, but the generated oracle/residual obligations are only classifi…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals"}}`
- A tactic or probe failed and the latest error needs classification.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":7,"handled_intent":{"intent":"inspect_context","payload":{"topic":"call_invariant_skeleton"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect call invariant skeleton","outcome":"The manager returned read-only context for the current goal.","timing":"250 ms","content":{"title":"Call-Invariant Glob Skeleton","items":[{"why":"Named predicates that mention your goal's state (lookup_symbol for each definition): make_lbad1, inv_lbad1, inv_lbad1_i. No mechanical `={glob}` frame applies at this call \u2014 build the call invariant from THIS development's own in-scope predicates (an invariant conjunct can be a guarded implication / size-or-count bound / domain fact, not only an equality). In-scope forms + named predicates (use lookup_symbol for the full definition of any): guarded implication (guard => relation) \u2014 make_lbad1: flatten (map (fun n:nonce => map (fun c:ciphertext => ((oget log.[n]).`3, c.`4)) (filter (fun c:ciphertext => c.`1 = n) lc)) lenc). lemma make_lbad1_size_cons2 ; inv_cpa: log1 = log2 /\\  | size / count bound \u2014 inv_lbad1: uniq lenc /\\ cbad1 <= qenc /\\ size lenc <= qenc /\\ size lbad1 <= size (make_lbad1 ufcmalog lc lenc) <= qdec /\\ size lc <= ndec <= qdec /\\ uniq lenc /\\ (forall n; inv_lbad1_i: uniq lenc /\\ cbad1 <= qenc /\\ siz | domain membership \u2014 check_plaintext: let (n, a, m) = p in ! n \\in lenc /\\ valid_topol a m /\\ size lenc < qenc. op check_cipher (ndec:int) (c:ciphertext) = (let (n, a, m, t) = c in valid_topol a m) ; inv: inv_cpa mr1 ms1 log1 log2 lc1 lc2 le | relational equality \u2014 check_cipher: (let (n, a, m, t) = c in valid_topol a m) /\\ ndec < qdec. (* Bounded and Nonce Respecting *) module BNR (O:CCA_Oracles) = { var lenc : nonce list var ndec : int"}]}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
