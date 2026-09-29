## Requested: `inspect_context` — lemma_index

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== chacha_poly.ec: 51 lemma statement(s) (signatures only — proofs are NOT shown) === These are every lemma declared in the current file. Use them to plan which lemmas you can apply/rewrite/bridge with; `lookup_symbol` for the exact declaration of any one before using it. L14 [lemma, top_level] map2_zip: lemma map2_zip (f:'a -> 'b -> 'c) s t : map2 f s t = map (fun (p:'a * 'b) => f p.`1 p.`2) (zip s t). L21 [lemma, top_level] size_map2: lemma size_map2 (f:'a -> 'b -> 'c) (l1:'a list) l2 : size (map2 f l1 l2) = min (size l1) (size l2). L27 [lemma, top_level] nth_map2: lemma nth_map2 dfla dflb dflc (f:'a -> 'b -> 'c) (l1:'a list) l2 i: 0 <= i < min (size l1) (size l2) => nth dflc (map2 f l1 l2) i = f (nth dfla l1 i) (nth dflb l2 i). L54 [lemma, top_level] xorK1: lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2. L134 [lemma, top_level] dblock_ll: lemma dblock_ll : is_lossless dblock. L140 [lemma, top_level] dblock_uni: lemma dblock_uni: is_uniform dblock. L146 [lemma, top_level] dblock_fu: lemma dblock_fu: is_full dblock. L152 [lemma, top_level] dblock_funi: lemma dblock_funi: is_funiform dblock. L163 [lemma, top_level] nth_xor: lemma nth_xor x y i : 0 <= i < block_size => nth Byte.zero (b...

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] +
Pr[UFCMA(A, St).main() @ &m :
```
_…(+6 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Opener — reduce the probability goal

**Goal shape:** a goal relating 4 `Pr[...]` terms

**Reduce with:**
- `apply (ler_trans <mid>)` / `rewrite` a `|·|` norm or `ler_add` step — an order/transitivity move that splits the `|Pr − Pr|` / sum bound into per-term obligations; this comes BEFORE any byequiv/byphoare
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Unfoldable heads:**
- `rewrite /dec.` (unfolds `dec`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

