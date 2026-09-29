## Requested: `inspect_context` — lemma_hints

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[AUTO-LEMMA-HINTS] EC stdlib lemmas relevant to ops in your goal — paste-ready signatures (apply / rewrite / smt(...)): [current-file-or-cloned-theory / op:`list-shape`] `nth_cat`: case split for nth over concatenation note: Resolve the actual declaration first with lookup_symbol; cloned theories may require a qualified name such as `DH.G.expD`. [current-file-or-cloned-theory / op:`list-shape`] `nth_take`: rewrite nth of a take prefix note: Resolve the actual declaration first with lookup_symbol; cloned theories may require a qualified name such as `DH.G.expD`. [current-file-or-cloned-theory / op:`list-shape`] `nth_mkseq`: rewrite nth of a generated sequence note: Resolve the actual declaration first with lookup_symbol; cloned theories may require a qualified name such as `DH.G.expD`. [current-file-or-cloned-theory / op:`list-shape`] `size_cat`: rewrite size of concatenation note: Resolve the actual declaration first with lookup_symbol; cloned theories may require a qualified name such as `DH.G.expD`. [current-file-or-cloned-theory / op:`list-shape`] `size_take`: rewrite size of a take prefix note: Resolve the actual declaration first with lookup_symbol; cloned theories may requ...

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

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

