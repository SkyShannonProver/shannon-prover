# Tree-0.0 · turn 17 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:06:31.648Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (: _ ==> true).`

---

Remaining 3 — this is the trailing branch of the outer `seq 21` split: `phoare[ tail : (a,a_,c,d)∈cilog ==> (a,a_,c,d)∈cilog ] ≤ 1%r`. Since it's an upper bound of 1 (the trivial maximum), I don't need to preserve the membership — I can weaken the post to `true`, then discharge the deterministic head + the (lossless) `A.guess` call with the same `call (_: true)` idiom the prefix used. First weaken the post.
