# Tree-0.1 · turn 1 · commit_tactic

<!-- session 71eefeb0-ba0c-4a92-8c5d-eb48f1c8df06 · 2026-06-09T03:58:49.762Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

I'll read the latest workspace view to see the current goal state.

I'll inspect the source to understand `enc`, `Poly.mac`, and the `poly_mac1/poly_mac2` lemmas before choosing the next tactic.

Now I understand the frontier. Left side is empty (the `enc` operator value); right side has `c1 <- c2` then the one-sided `Poly.mac` call. The ciphertext parts already match (that's what the while-loop proof established); the remaining work is showing the right-side `mac` tag equals the left's `genpoly1305`. Key fact: `FinRO` is a *finite eager* RO, so `FinRO.get` is a deterministic read of `RO.m`.

Let me load the MCP tool and first absorb the `c1 <- c2` assignment with `sp`.
