# Tree-0.0 · turn 1 · inspect_context

<!-- session b128090b-36da-4fd4-859a-3411ec0b8984 · 2026-06-06T12:39:09.750Z -->

**Intent:** `inspect_context`  
**Payload:** `call_site_options`

---

I'll analyze the proof. `pedersen_correctness` is a hoare correctness statement. The commitment `c = g^d * h^m` and verify recomputes `c' = g^d * h^m`, so they trivially match. Let me first see the `Correctness.main` body, then try the standard `proc; inline *; auto` route.
