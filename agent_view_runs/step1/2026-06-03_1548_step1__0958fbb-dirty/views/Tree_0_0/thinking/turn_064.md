# Tree-0.0 · turn 64 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:25:07.954Z -->

**Intent:** `probe_tactic`  
**Payload:** `call poly_mac2. auto. if => //. wp. call chacha_enc2. auto. auto.`

---

Part1 is the `Poly.mac` prefix, identical structure to the first half. Probing the dec remainder (mirror of the working first-half sequence).
