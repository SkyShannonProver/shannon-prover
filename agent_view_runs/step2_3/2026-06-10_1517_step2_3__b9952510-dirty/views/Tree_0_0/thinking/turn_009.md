# Tree-0.0 · turn 9 · commit_tactic

<!-- session a51e628e-7b92-45c6-b528-b64183d9b981 · 2026-06-10T22:34:22.896Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll.`

---

Parse error on the inline lambda proof-term. Let me establish the losslessness hypothesis as a named fact first, mirroring step1 exactly.
