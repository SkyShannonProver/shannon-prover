## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** experts decompose this shape as case split then rcond swap wp conseq → local smt.

**Why now:** current pRHL state looks past the main opener: the useful next work is local branch/suffix surgery, not changing proof family.

**Confidence:** medium — The current pRHL goal exposes a bad-event/instrumented branch together with sampling or one-sided suffix evidence; this is the shape where experts use `case`, `rcondt/rcondf`, `swap`, indexed `wp`, `conseq`, or one-sided `rnd` before local SMT. The fast-track tactic is schematic, so confidence is capped until the current view or an inspect result supplies concrete terms.

**Fast track probe:** try `case: (<current branch guard>).` first — Use only when the visible goal has a concrete guard controlling the local branch.

**Where:**
- setup before the frontier (positions 2–3) — absorb with `sp`/`wp`: 2 setup statement(s): UFCMA_l.lbad1 <- UFCMA_l.lbad1 ++ map (fun (t' : tag) => (
- frontier: both sides at `t0 <$ dpoly_out`
- frontier: both sides at `no matching left-side sample at this frontier`
- frontier: both sides at `no matching left-side statement at this frontier`
- frontier: both sides at `no matching left-side statement at this frontier`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Split points:**
- `seq 3 10 : (=?).` — split point given; YOU fill the coupling.
- `seq 1 1 : (=?).` — split point given; YOU fill the coupling.

**Avoid:**
- This is a branch-local/suffix alignment problem; a fresh restart throws away useful opener and invariant work.
- One side has sampling or instrumentation before the suffix; use `rcond`, `swap`, or one-sided `rnd` before plain `wp`.
- `sim` is usually too late/too strong before the guard and suffix shape are aligned.
- Do not use `conseq` as a blind replacement for a missing call or loop invariant; if residuals need facts not carried by the last boundary, repair that boundary first.

**Repair if fails:**
- syntax → inspect tactic_forms for swap, rcondt, rcondf, wp, conseq, rnd, or eager
- frontier → inspect align or goal_info for statement indexes before retrying
- invariant → use undo_to_checkpoint {} and choose the checkpoint before the call/loop invariant that should carry the missing guard or size fact
- lemma → inspect lemma_hints or lookup_symbol for the local size/nth/bad-event lemma
- route → downgrade this surgery route only after a smaller prefix and relevant tactic_forms fail

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling (e.g. `t0{1} = t1{2}`), the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 9)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}
&2 (right) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y, t1 : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             ti : tag, p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}

pre =
  (((Mem.lc{1} = Mem.lc{2} /\
     Mem.log{1} = Mem.log{2} /\
     (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\
     UFCMA.log{1} = UFCMA.log{2} /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
     RO.m{1} = RO.m{2} /\
     SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
     SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    (n{1} = n{2} /\
     a{1} = a{2} /\ c1{1} = c1{2} /\ p0{1} = p0{2} /\ lt{1} = lt{2}) /\
    p{1} = p{2} /\
    UFCMA_li.i{2} = nth0 /\
    UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
    UFCMA_li.badi{2} =
    (nth0 < size UFCMA_l.lbad1{2} /\
     (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
     (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)) /\
   UFCMA.cbad1{1} < qenc /\ size lt{1} <= qdec) /\
  size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}

t0 <$ dpoly_out                        (1----)  t0 <$ dpoly_out                         
UFCMA_l.lbad1 <-                       (2----)  if (size UFCMA_l.lbad1 <= UFCMA_li.i <  
  UFCMA_l.lbad1 ++                     (  ---)      size UFCMA_l.lbad1 + size lt) {     
  map (fun (t' : tag) => (t0, t')) lt  (  ---)                                          
                                       (2.1--)    ti <-                                 
                                       (    -)      nth witness lt                      
                                       (    -)        (UFCMA_li.i - size UFCMA_l.lbad1) 
                                       (2.2--)    t1 <$ dpoly_out                       
                                       (2.3--)    if (UFCMA_li.cbadi < 1) {             
                                       (2.3.1)      UFCMA_li.badi <-                    
                                       (     )        UFCMA_li.badi || t1 = ti          
                                       (2.3.2)      UFCMA_li.cbadi <- UFCMA_li.cbadi + 1
                                       (2.3--)    }                                     
                                       (2.4--)    t0 <- t1                              
                                       (2----)  }                                       
UFCMA.cbad1 <- UFCMA.cbad1 + 1         (3----)  UFCMA_l.lbad1 <-                        
                                       (  ---)    UFCMA_l.lbad1 ++                      
                                       (  ---)    map (fun (t' : tag) => (t0, t')) lt   
                                       (4----)  UFCMA.cbad1 <- UFCMA.cbad1 + 1          

post =
  (Mem.lc{1} = Mem.lc{2} /\
   Mem.log{1} = Mem.log{2} /\
   (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
  (n{1} = n{2} /\
   a{1} = a{2} /\ c1{1} = c1{2} /\ p0{1} = p0{2} /\ t0{1} = t0{2}) /\
  p{1} = p{2} /\
  UFCMA_li.i{2} = nth0 /\
  UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
  UFCMA_li.badi{2} =
  (nth0 < size UFCMA_l.lbad1{2} /\
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)
[441|check]>
```

## Status
remaining **9** · phase `seq_cut` / `procedure_body`

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

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `commit_tactic` `case (size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}).`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":12,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"case (size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2})."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"2.4 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
