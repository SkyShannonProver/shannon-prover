# Tree-0.0 · turn 1 · commit_tactic

<!-- session 14b2516c-a539-4bae-8aa7-991bf981a2fb · 2026-06-12T00:21:44.748Z -->

**Intent:** `commit_tactic`  
**Payload:** `by rewrite /int2o /o2int -(size_octet o) bs2intK mkoctetK.`

---

I'll start by reading the current workspace view to see the goal state.

The goal is `int2o (o2int o) = o` for `o: octet` — a roundtrip cancellation lemma. Let me check the source file for the definitions.

The definitions are `o2int o = bs2int (ofoctet o)` and `int2o i = mkoctet (int2bs 8 i)`. Let me look at the theory setup around line 10-30.
