## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** experts decompose this shape as case split then rcond swap wp conseq → local smt.

**Why now:** current pRHL state looks past the main opener: the useful next work is local branch/suffix surgery, not changing proof family.

**Confidence:** medium — The current pRHL goal exposes a bad-event/instrumented branch together with sampling or one-sided suffix evidence; this is the shape where experts use `case`, `rcondt/rcondf`, `swap`, indexed `wp`, `conseq`, or one-sided `rnd` before local SMT. The fast-track tactic is schematic, so confidence is capped until the current view or an inspect result supplies concrete terms.

**Fast track probe:** try `case: (<current branch guard>).` first — Use only when the visible goal has a concrete guard controlling the local branch.

**Where:**
- setup before the frontier (positions 1–8) — absorb with `sp`/`wp`: 8 setup statement(s): UFCMA_l.lbad1 <- []; UFCMA.cbad1 <- 0; UFCMA.log <- empty;

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Avoid:**
- This is a branch-local/suffix alignment problem; a fresh restart throws away useful opener and invariant work.
- One side has sampling or instrumentation before the suffix; use `rcond`, `swap`, or one-sided `rnd` before plain `wp`.
- `sim` is usually too late/too strong before the guard and suffix shape are aligned.

**Repair if fails:**
- syntax → inspect tactic_forms for swap, rcondt, rcondf, wp, conseq, rnd, or eager
- frontier → inspect align or goal_info for statement indexes before retrying
- invariant → use undo_to_checkpoint {} and choose the checkpoint before the call/loop invariant that should carry the missing guard or size fact
- lemma → inspect lemma_hints or lookup_symbol for the local size/nth/bad-event lemma
- route → downgrade this surgery route only after a smaller prefix and relevant tactic_forms fail

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling (e.g. `t0{1} = t1{2}`), the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {b, b0, b1, b2 : bool}
&2 (right) : {b, b0, b1, b2 : bool, i0 : int}

pre = (glob A){1} = (glob A){2} /\ i0{2} = nth0

UFCMA_l.lbad1 <- []        ( 1)  UFCMA_li.cbadi <- 0      
UFCMA.cbad1 <- 0           ( 2)  UFCMA_li.badi <- false   
UFCMA.log <- empty         ( 3)  UFCMA_li.i <- i0         
RO.m <- empty              ( 4)  UFCMA_l.lbad1 <- []      
SplitC2.I2.RO.m <- empty   ( 5)  UFCMA.cbad1 <- 0         
SplitD.ROF.RO.m <- empty   ( 6)  UFCMA.log <- empty       
Mem.log <- empty           ( 7)  RO.m <- empty            
Mem.lc <- []               ( 8)  SplitC2.I2.RO.m <- empty 
BNR.lenc <- []             ( 9)  SplitD.ROF.RO.m <- empty 
BNR.ndec <- 0              (10)  Mem.log <- empty         
                           (11)  Mem.lc <- []             
                           (12)  BNR.lenc <- []           
                           (13)  BNR.ndec <- 0            

post =
  ((glob A){1} = (glob A){2} /\
   (Mem.k{1}, Mem.lc{1}, Mem.log{1}) = (Mem.k{2}, Mem.lc{2}, Mem.log{2}) /\
   (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
  UFCMA_li.i{2} = nth0 /\
  UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
  UFCMA_li.badi{2} =
  (nth0 < size UFCMA_l.lbad1{2} /\
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)
[423|check]>
```

## Status
remaining **4** · phase `relational_program` / `procedure_body`

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

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `probe_tactic` `auto.`
- result: Accepted closing/checking probe. Commit the exact tactic only if you want to try closing or checking this obligation.

```json
{"turn":12,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"auto."}},"ok":true,"manager_note":"Accepted closing/checking probe. Commit the exact tactic only if you want to try closing or checking this obligation.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed.","timing":"2.2 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
