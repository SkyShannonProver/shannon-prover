## 🎯 Current Goal
```
Current goal (remaining: 8)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
forall &m0,
  hoare[ t0 <$ $dpoly_out :
          ((Mem.lc = Mem.lc{m0} /\
            Mem.log = Mem.log{m0} /\
            (BNR.lenc, BNR.ndec) = (BNR.lenc{m0}, BNR.ndec{m0}) /\
            UFCMA.log = UFCMA.log{m0} /\
            UFCMA.cbad1 = UFCMA.cbad1{m0} /\
            UFCMA_l.lbad1 = UFCMA_l.lbad1{m0} /\
            RO.m = RO.m{m0} /\
            SplitC2.I2.RO.m = SplitC2.I2.RO.m{m0} /\
            SplitD.ROF.RO.m = SplitD.ROF.RO.m{m0}) /\
           (n = n{m0} /\
            a = a{m0} /\ c1 = c1{m0} /\ p0 = p0{m0} /\ lt = lt{m0}) /\
           p = p{m0} /\
           UFCMA_li.i{m0} = nth0 /\
           UFCMA_li.cbadi{m0} = b2i (nth0 < size UFCMA_l.lbad1{m0}) /\
           UFCMA_li.badi{m0} =
           (nth0 < size UFCMA_l.lbad1{m0} /\
            (nth (w1, w2) UFCMA_l.lbad1{m0} nth0).`1 =
            (nth (w1, w2) UFCMA_l.lbad1{m0} nth0).`2)) /\
          ! (UFCMA.cbad1 < qenc /\ size lt <= qdec) ==>
          ! (UFCMA.cbad1 < qenc /\ size lt <= qdec)]
[461|check]>
```

## Pure Logic — close with smt / rewrite

**Goal shape:** quantified ambient tail

**Obligation families:**
- `sampling_bijection` — The remaining pure goal may include invertibility or lossless side conditions from an ear… (seen: distribution or lossless token remains visible) (NOT: No distribution lemma is selected by this surface.)
- `constructor_projection` — The pure goal exposes tuple/record projections or constructor equalities that can connect… (NOT: Projection equalities are reported only when visible in the current t…)
- `quantified_residual_logic` — The current proof point is dominated by local logical obligations rather than program-fro… (seen: universal quantifier visible; implication residual visible) (NOT: Quantifier names are not normalized across EasyCrypt pretty-printer v…)

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition.

## Status
remaining **8** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- proof-state analysis extracted multiple EC operator tokens from the current goal; use native AST/operator search before…
  submit `{"intent": "inspect_context", "payload": {"topic": "rewrite_candidates"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `commit_tactic` `rcondf{1} 2.`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":37,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"rcondf{1} 2."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"504 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
