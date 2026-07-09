# Tree-0.0 · turn 18 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:20:14.540Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (: _ ==> ((g ^ G1.u, G1.g_ ^ G1.u', g ^ r', g ^ r) \in G3.cilog)) (: _ ==> size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w).`

---

Now the 4-sample product bound. Let me find the distribution and group lemmas I'll need (point-mass of `dt`, `g^·` injectivity/bijection, and `dexcepted` point-mass).

Found the key group lemmas: `pow_bij` (injectivity of `g^·`), `loggK`/`expgK` (dlog inverse), `logbK`/`expbK` (injectivity of `b^·` when `loge b` is a unit), and `dt1E : mu1 dt s = 1/order`. Now I need the point-mass of the excepted distribution `dt \ pred1 u`.

I found the needed lemmas. Now the core challenge: each coordinate bound needs `size cilog ≤ qD` (and `w≠0`) in scope, but for the seq peel's `p4=0` branch to be clean I must enrich the postcondition with these preserved facts. Let me find the EC `conseq` syntax for adding a preserved (hoare) fact to a phoare postcondition.

The threading requires enriching the postcondition with the preserved facts (`size ≤ qD`, `w≠0`, `g_=g^w`) — sound via `conseq` with a hoare side-condition. Let me test the two-judgment `conseq` form and observe the subgoals it generates.
