# Tree-0.0 · turn 15 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:04:06.263Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; smt(qD_pos size_ge0 supp_dexcepted).`

---

Oracle obligation closed (back to 5). Now the main goal: prefix statements 1–12 must establish the call's precondition — initial `J` (with empty logs) plus the framing of `w≠0`/`g_=g^w`. I need `0 ≤ qD` for `size [] ≤ qD`. Let me find the qD bound axiom.

`qD_pos : 0 < qD` exists. The framed `w≠0` comes from the `dt \ pred1 zero` support. Let me verify the dexcepted support lemma name before composing the closer.

Both lemmas confirmed. Now process the prefix and discharge with the support and bound facts.
