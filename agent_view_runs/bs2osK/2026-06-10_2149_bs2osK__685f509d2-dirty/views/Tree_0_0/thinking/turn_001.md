# Tree-0.0 · turn 1 · commit_tactic

<!-- session 93467796-eb97-4873-aac2-fb6f922f24ec · 2026-06-11T04:52:19.523Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /os2bs /bs2os flattenK //.`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is `os2bs (bs2os bs) = bs` — a roundtrip lemma. Let me check the definitions in the source file.

`flattenK` confirmed. Now check the Word theory's cancellation lemma name (word→block renamed).

`mkblockK : cancel ofblock mkblock` and `size_block` exist. Let me check `id_map`'s signature, then start committing tactics.
