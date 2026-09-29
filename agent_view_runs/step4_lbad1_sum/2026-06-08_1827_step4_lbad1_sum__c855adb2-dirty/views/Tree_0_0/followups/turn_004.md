## Requested: `inspect_context` — diagnose

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

No known diagnosis for this error. Error: [error] This expression has type Tactic: have HP := LP.list_partitioning UFCMA_l tt (fun _ g _ => size g <= qdec /\ exists (p:tag*tag), p \in g /\ p.`1 = p.`2) (fun _ g _ => find (fun (p:tag*tag) => p.`1 = p.`2) g) (iota_ 0 qdec) &m (iota_uniq 0 qdec). General suggestions: - Read the goal state carefully - Try a simpler version of the tactic - Use -search to verify lemma names - Step back: if stuck >5 min, reconsider the approach (Pitfall P4)

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[UFCMA_l.f() @ &m :
   size UFCMA_l.lbad1 <= qdec /\
```
_…(+6 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Opener — reduce the probability goal

**Goal shape:** a goal relating 2 `Pr[...]` terms

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `have HP := LP.list_partitioning UFCMA_l tt (fun (_:unit) (g:glob UFCMA_l) (_:un…` → REJECTED: [error] This proof-term argument is not a valid formula:
- commit `have HP := LP.list_partitioning UFCMA_l tt (fun _ g _ => size g <= qdec /\ exis…` → REJECTED: [error] This expression has type

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

