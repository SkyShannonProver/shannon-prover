## Requested: `lookup_symbol` — iter_cat

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

[WHERE-HIT] iter_cat (kind: lemma) * In [lemmas or axioms]: lemma iter_cat: forall (O <: Orcl), equiv[ Iter(O).iter ~ Iter(O).iters : (glob O){1} = (glob O){2} /\ arg{1} = l1{2} ++ l2{2} ==> (glob O){1} = (glob O){2}]. [AMBIGUOUS] iter_cat also resolves in 1 other clone instance(s): - IPNonce.iter_cat (kind: lemma) lemma iter_cat: → If your goal references one specifically, use the qualified name. Re-run `-where Foo.iter_cat` to get its body.

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, ns, ns1, ns2 : nonce list}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}
```
_…(+56 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: UF.forged <- false
- frontier: right side only at `r <@ RO.get(n, C.ofintd 0)`
- frontier: right side only at `t <@ UFCMA(RO).set_bad2(map (fun (c : ciphertext) => c.`4 - `
- frontier: right side only at `while (i < size ns1) {`
- frontier: right side only at `while (i < size ns2) {`
- frontier: both sides at `if (size Mem.lc <= qdec) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **1** · phase `relational_program` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `sim.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

