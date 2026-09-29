## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {x : unit, r, b : bool}

pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}

RealOrcls(GenChaChaPoly(OCC(IFinRO))).init()  (1)  FinRO.init()                 
                                              (2)  () <- x                      
                                              (3)  D(A, G2(FinRO).CCRO).O.init()

post = (glob A){1} = (glob A){2} /\ OCC.gs{1} = RO.m{2}
[323|check]>
```

## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** experts decompose this shape as case split then rcond swap wp conseq → local smt.

**Why now:** current pRHL state looks past the main opener: the useful next work is local branch/suffix surgery, not changing proof family.

**Confidence:** medium — The current pRHL goal has local branch/suffix surgery signals, but the exact guard or statement order still needs inspection.

**Fast track probe:** try `case: (<current branch guard>).` first — Use only when the visible goal has a concrete guard controlling the local branch.

**Where:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: RealOrcls(GenChaChaPoly(OCC(IFinRO))).init()

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

## Status
remaining **2** · phase `relational_program` / `procedure_body`

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
- you submitted: `commit_tactic` `seq 1 3 : (={glob A} /\ OpCCRO.OCC.gs{1} = RO.m{2}).`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":55,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"seq 1 3 : (={glob A} /\\ OpCCRO.OCC.gs{1} = RO.m{2})."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"315 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
