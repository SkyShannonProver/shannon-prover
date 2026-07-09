# Tree-0.0 · turn 17 · commit_tactic

<!-- session f8563eb0-33e2-483a-a365-92671a67224b · 2026-06-11T04:44:41.713Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> &2; proc; inline *; wp; call M_tag_ll; wp; call E_enc_ll; auto.`

---

Now the side-2 Sim.enc lossless-preserving-bad goal. `win` is outside `glob E`/`glob M` by the module restrictions, so framing handles preservation.
