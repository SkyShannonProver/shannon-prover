# Tree-0.0 · turn 9 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:07:09.192Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r.`

---

Goal 1 (prefix termination) closed. Now the current goal is the core: `phoare[1-21 : true ==> (a,a_,c,d) ∈ cilog] <= bound`. I need `size G3.cilog <= qD` as an invariant after `A.choose`. Let me check the `qD` declaration and the oracle structure in the PKE source first.

Confirmed `axiom qD_pos : 0 < qD`, so `size cilog ≤ qD` is valid at init. Now I'll cut at statement 13 to establish the `size G3.cilog <= PKE_.qD` invariant after `A.choose`, with the sampling bound on the tail.
