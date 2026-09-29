# Tree-0.0 · turn 29 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:05:32.691Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc. wp. call poly_mac1. call chacha_enc1. auto.`

---

Now the enc obligation. Plan: `proc`, inline the `GenChaChaPoly.enc` layer on the left to expose the `ChaCha.enc`/`Poly.mac` subcalls, then close with `call poly_mac1` / `call chacha_enc1`. Probing the full sequence.
