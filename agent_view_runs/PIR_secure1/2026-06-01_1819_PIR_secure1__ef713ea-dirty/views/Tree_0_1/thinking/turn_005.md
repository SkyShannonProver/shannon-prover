# Tree-0.1 · turn 5 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:21:58.311Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp.`

---

`inline *.` was also rejected. The programs are "in sync" after `proc.`, which means EasyCrypt is treating them as syntactically identical (modulo the `i` parameter which is local). Since the programs are in sync, `inline *` has nothing to do — the query calls are already being viewed as synchronized.

Let me try a different approach. Since the programs are in sync, I should try `wp.` to absorb the suffix (the query calls and return), or try `sim.` to close it directly, or use a `while` with an invariant that includes `={PIR.s, j}`.
 
The view suggestions mentioned probes for `exact/PIR_s_uniform.` and `exact/PIR_secure1.`, but `PIR_secure1` is the lemma I'm proving, so that's circular, and `PIR_s_uniform` has a different type signature anyway. I think the right move is to use `wp.` after `proc.` to handle the suffix following the while loop, then apply `while` with an appropriate invariant — the issue is that `inline *` failed because the programs are already synchronized.

Looking at the probe rejection messages more carefully, they're actually being accepted by EasyCrypt itself, but the manager is blocking them because it predicts no progress. So these are manager-level rejections, not fundamental failures. Let me try `wp.` directly since it should be able to absorb the call and return statements at the end, and the manager might allow it.
