# Tree-0.0 · turn 10 · lookup_symbol

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:56:54.169Z -->

**Intent:** `lookup_symbol`  
**Payload:** `pr_CCP_OCCP`

---

After `proc.`, the two sides align as `init(); A(O).main()` vs `IndBlock.init(); D(A,IndBlock).guess()` (where `guess = CCA_game(A, D.O).main`). The crux is relating the enc/dec oracles: functional `OChaChaPoly` vs loop-based `D.O` calling `IndBlock`. The local lemmas `chacha_enc1`/`poly_mac1` bridge the *loop-based* `ChaCha`/`Poly` modules to `D.O` — which suggests `GenChaChaPoly` may be the better normalization target than `OChaChaPoly`. Let me get the advisor's read before committing to a manual call-invariant route.

Advisor confirms the reroute: chain through `GenChaChaPoly` via `pr_CCP_OCCP`/`CCP_OCCP`, then use `call chacha_enc1`/`call poly_mac1`. First I must verify these lemmas instantiate with the `CCA_game(A, RealOrcls(·))` wrapper. Let me look them up.
