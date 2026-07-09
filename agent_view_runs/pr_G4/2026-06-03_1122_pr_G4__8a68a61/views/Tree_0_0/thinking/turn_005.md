# Tree-0.0 · turn 5 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:29:04.922Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 1%r 1%r 0%r.`

---

Full body is visible (25 statements). The event is fixed after stmt 21; stmts 22–25 (incl. `A.guess`) preserve it because `cstar` is `Some` so the oracle never appends to `cilog`. I'll drop the tail with a phoare `seq`. Let me probe the exact form first.
