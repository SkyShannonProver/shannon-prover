## Requested: `lookup_symbol` — LP.list_partitioning

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] LP.list_partitioning (kind: lemma) * In [lemmas or axioms]: (* LP.list_partitioning *) local lemma list_partitioning: forall (M <: EP.T) (i : unit) (E : unit -> (glob M) -> unit -> bool) (phi : unit -> (glob M) -> unit -> int) (P : int list) &m, uniq P => Pr[M.f(i) @ &m : E i (glob M) res] = BRA.big predT<:int> (fun (a : int) => Pr[M.f(i) @ &m : E i (glob M) res /\ phi i (glob M) res = a]) P + Pr[M.f(i) @ &m : E i (glob M) res /\ ! (phi i (glob M) res \in P)].

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

