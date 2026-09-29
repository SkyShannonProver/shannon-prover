# Tree-0.0 · turn 1 · lookup_symbol

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:24:15.272Z -->

**Intent:** `lookup_symbol`  
**Payload:** `mu_mem_le_mu1_size`

---

I'll start by loading the proof intent tool and orienting myself on the proof.

I have the full initial view. This is a single-program probability upper bound on `G4.main`: the event is that a freshly-sampled tuple `(g^u, g_^u', g^r', g^r)` lands in `G3.cilog` (frozen after `A.choose`). The tail (`alpha`, `cstar`, `A.guess`) doesn't affect the event. Let me confirm a few facts before composing. First, the key membership lemma and the distribution facts.
