## Requested: `lookup_symbol` — big_cons

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] big_cons (kind: lemma) * In [lemmas or axioms]: lemma big_cons ['a]: forall (P : 'a -> bool) (F : 'a -> word) (x : 'a) (s : 'a list), big P F (x :: s) = if P x then F x +^ big P F s else big P F s. [AMBIGUOUS] big_cons also resolves in 1 other clone instance(s): - BBS.big_cons (kind: lemma) lemma big_cons ['a]: → If your goal references one specifically, use the qualified name. Re-run `-where Foo.big_cons` to get its body.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
i0: int
hi0: 0 <= i0 < N
------------------------------------------------------------------------
```
_…(+14 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Status
remaining **2** · phase `procedure_frontier` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `while (0 <= j <= N /\ i = i0 /\ big predT a PIR.s +^ big predT a PIR.s' = (if i…` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

