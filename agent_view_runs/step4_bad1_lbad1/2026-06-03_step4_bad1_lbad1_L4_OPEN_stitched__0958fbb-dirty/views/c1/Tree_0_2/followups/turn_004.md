## 🎯 Current Goal
```
Current goal (remaining: 6)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &1 &2,
  (n{1} = n{2} /\
   a{1} = a{2} /\
   c1{1} = c1{2} /\
   lt{1} = lt{2} /\
   t0{1} = t0{2} /\
   p0{1} = p0{2} /\
   p{1} = p{2} /\
   Mem.log{1} = Mem.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   BNR.lenc{1} = BNR.lenc{2} /\
   BNR.ndec{1} = BNR.ndec{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
  inv_lbad1 UFCMA_l.lbad1{2} BNR.lenc{2} UFCMA.log{2} Mem.log{2} Mem.lc{2}
    UFCMA.cbad1{2} BNR.ndec{2} /\
  (UFCMA.bad1{1} <=>
   exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2) /\
  check_plaintext BNR.lenc{1} p{1} /\
  n{1} = p{1}.`1 /\
  lt{2} =
  map (fun (c3 : ciphertext) => c3.`4)
    (filter (fun (c3 : ciphertext) => c3.`1 = n{2}) Mem.lc{2}) =>
  UFCMA.cbad1{1} < qenc /\ size lt{1} <= qdec <=>
  UFCMA.cbad1{2} < qenc /\ size lt{2} <= qdec
[415|check]>
```

## Pure Logic — close with smt / rewrite

**Goal shape:** quantified ambient tail

**Obligation families:**
- `constructor_projection` — The pure goal exposes tuple/record projections or constructor equalities that can connect… (NOT: Projection equalities are reported only when visible in the current t…)
- `quantified_residual_logic` — The current proof point is dominated by local logical obligations rather than program-fro… (seen: universal quantifier visible; implication residual visible) (NOT: Quantifier names are not normalized across EasyCrypt pretty-printer v…)

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition.

## Status
remaining **6** · phase `relational_program` / `ambient_logic`

### Need more? submit one of these read-only requests
- Goal relates map and membership; native search should surface map/mem lemmas.
  submit `{"intent": "inspect_context", "payload": {"topic": "rewrite_candidates"}}`
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
- you submitted: `commit_tactic` `if.`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":4,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"if."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"256 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
