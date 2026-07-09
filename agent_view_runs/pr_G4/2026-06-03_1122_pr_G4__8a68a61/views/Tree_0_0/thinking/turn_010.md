# Tree-0.0 · turn 10 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:32:29.555Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r.`

---

Now the main subgoal: `phoare[1..21 : true ==> event] <= bound`. I'll split off the `A.choose` prefix to establish the invariant `size G3.cilog <= qD`, then bound the four samples. Let me probe the inner `seq 13`.
