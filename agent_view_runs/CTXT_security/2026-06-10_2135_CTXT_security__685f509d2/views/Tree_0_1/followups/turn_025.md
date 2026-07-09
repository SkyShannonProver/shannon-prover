## Requested: `lookup_symbol` — M_verify_ll

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] M_verify_ll (kind: axiom) * In [lemmas or axioms]: declare axiom M_verify_ll: islossless M.verify. [AMBIGUOUS] M_verify_ll also resolves in 1 other clone instance(s): - RCPA_SUF_CTXT.M_verify_ll (kind: axiom) declare axiom M_verify_ll: islossless M.verify. → If your goal references one specifically, use the qualified name. Re-run `-where Foo.M_verify_ll` to get its body.

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
dec: eK -> ctxt -> ptxt option
dec_sem: forall (ge : (glob E)) (_k : eK) (_c : ctxt),
           hoare[ E.dec :
```
_…(+18 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `MACa.SUF_CMA.SUF_Wrap.win`
- `islossless`
- `CTXT_Wrap`
- `EtM`
- `verify`

**Visible hypotheses:**
- `dec: eK -> ctxt -> ptxt option`

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **3** · phase `relational_program` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `rcondf{1} 1; first by auto. by wp; skip; smt().` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

