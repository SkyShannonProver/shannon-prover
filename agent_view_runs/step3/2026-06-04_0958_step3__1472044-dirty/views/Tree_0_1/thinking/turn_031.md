# Tree-0.1 · turn 31 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:18:43.429Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (equ_cc (p{1}.`1) (SplitC2.I1.RO.m{1}) (SplitC2.I2.RO.m{1})).`

---

Repeated rejection signals a structural matching problem, not arguments. The L1 panel hides the EC error. Let me check whether the manager logged the raw error anywhere in this node's memory.

The raw EC error is stripped by the framework. Let me check the timeline for any richer diagnostic on these rejected calls.

The 2.3s-then-reject pattern suggests EC is doing real unification work and failing — likely it tries to match the lemma's post `ROF.m ⊆ n0::lenc` against my intermediate's `ROF.m ⊆ p{1}.\`1::lenc`, which forces `n0 = p{1}.\`1`. Let me instantiate `n0` with `p{1}.\`1` so the post aligns syntactically.
