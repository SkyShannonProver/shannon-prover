## Requested: `lookup_symbol` — ler_sum

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] ler_sum (kind: lemma) * In [lemmas or axioms]: lemma ler_sum ['a]: forall (P : 'a -> bool) (F1 F2 : 'a -> int) (s : 'a list), (forall (a : 'a), P a => F1 a <= F2 a) => BIA.big P F1 s <= BIA.big P F2 s. (* StdBigop.Bigreal.ler_sum *) lemma ler_sum ['a]: forall (P : 'a -> bool) (F1 F2 : 'a -> real) (s : 'a list), (forall (a : 'a), P a => F1 a <= F2 a) => BRA.big P F1 s <= BRA.big P F2 s.

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
HP: forall (E : unit ->
                (glob A) * nonce list * int * int * (nonce, associated_data *
                message * tag) fmap * (tag * tag) list * (nonce * C.counter,
```
_…(+72 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Opener — reduce the probability goal

**Goal shape:** a Pr-difference / distinguishing-advantage bound relating 10 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `rewrite RField.addr0.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

