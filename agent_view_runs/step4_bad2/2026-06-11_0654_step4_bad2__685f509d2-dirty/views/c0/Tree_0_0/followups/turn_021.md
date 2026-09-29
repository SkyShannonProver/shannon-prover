## 🎯 Current Goal
```
Current goal (remaining: 8)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
              r : poly_in, t : poly_out}
Bound   : [<=] BRA.big predT<:nonce>
                 (fun (n0 : nonce) =>
                    (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc))%r)
                 ns1 *
               pr_zeropol

pre =
  ns = undup (map (fun (p : ciphertext) => p.`1) Mem.lc) /\
  ns1 = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m) ns /\
  ns2 = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m) ns /\
  i = 0 /\
  (UF.forged = false /\
   UFCMA.bad2 = false /\ RO.m = empty<:nonce * C.counter, poly_in>) /\
  size Mem.lc <= qdec

(1--)  while (i < size ns1) {                                                  
(1.1)    n <- nth witness<:nonce> ns1 i                                        
(1.2)    r <@ LRO.get(n, C.ofintd 0)                                           
(1.3)    UF.forged <- UF.forged || test_poly_in n Mem.lc r (oget UFCMA.log.[n])
(1.4)    i <- i + 1                                                            
(1--)  }                                                                       
(2--)  i <- 0                                                                  

post = UF.forged
[397|check]>
```

## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** while (true) (size ns1 - i). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** framework reads the head as left=`call` right=`None` (one-sided_frontier) — find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Evidence:**
- [error] invalid last instruction

**Available local work:**
- residual program surgery

**Limitations:**
- does not prescribe a conseq, sim, wp, or skip script
- reports residual program evidence before pure-tail obligations

**Rewind targets:**
- `After seq opened / before branch work #13` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_13_0d4408177e8350da"}}`

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (rewind_targets above name the exact points).

## Status
remaining **8** · phase `failure_diagnostic` / `procedure_body`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `while (true) (size ns1 - i).` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] invalid last instruction`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `trivial.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
