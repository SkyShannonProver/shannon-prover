# Tree-0.1.0 · turn 33 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:43:04.042Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /inv_cpa; sp; if; auto; smt(mem_set get_setE).`

---

Both bodies are byte-identical (in sync), reading `Mem.log` and updating `Mem.lc`/`ndec` the same way; the RO maps and `lenc` are untouched. Unfold `inv_cpa` to expose the component equalities (needed for the guard alignment and freshness), then align and discharge.
