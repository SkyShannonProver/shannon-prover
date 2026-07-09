# Tree-0.0 · turn 2 · probe_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:26:18.583Z -->

**Intent:** `probe_tactic`  
**Payload:** `byphoare => //.`

---

`mu_mem_le_mu1_size` confirmed: `size l <= n => (forall x, mu1 dt x <= r) => mu dt (mem l) <= n%r * r`.

My plan: the event `(G3.a,G3.a_,G3.c,G3.d) ∈ G3.cilog` is fixed right after `G3.d <- g^r` (stmt 21); the tail (`v`, `alpha`, `cstar`, `A.guess`) preserves it. `cilog` is frozen after `A.choose` with `size ≤ qD`. The four fresh samples `u,u',r',r` are independent, each coordinate an injective image of one sample, so I bound the tuple-membership by the conjunction of four projection-memberships and multiply the four per-coordinate bounds.

Let me probe the opener reduction.
