## Requested: `inspect_context` — pr_bridge_routes

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[UFCMA(RO).distinguish() @ &m : res \/ UFCMA.bad2] <=
qdec%r * maxr pr_zeropol pr1_poly_out
```

## Opener — reduce the probability goal

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound

**Unfoldable heads:**
- `rewrite /pr1_poly_out.` (unfolds `pr1_poly_out`)

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

