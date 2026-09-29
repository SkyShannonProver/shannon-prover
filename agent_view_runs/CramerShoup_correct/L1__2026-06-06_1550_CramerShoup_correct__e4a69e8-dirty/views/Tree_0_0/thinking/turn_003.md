# Tree-0.0 · turn 3 · commit_tactic

<!-- session 07455470-e8fa-4295-a197-2758a7098fad · 2026-06-06T22:54:49.316Z -->

**Intent:** `commit_tactic`  
**Payload:** `pose v := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}).`

---

Now I'll pose the hash term as `v` and prove the two algebraic facts. Let me start with `pose` plus the decryption-condition equality.
