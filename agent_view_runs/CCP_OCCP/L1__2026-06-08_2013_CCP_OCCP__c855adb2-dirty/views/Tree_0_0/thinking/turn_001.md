# Tree-0.0 · turn 1 · commit_tactic

<!-- session c47170b7-d351-4369-a1ec-64c14b2b3c04 · 2026-06-09T03:16:22.680Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc (={glob I, glob OCC}).`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the latest followup and the source file to understand the lemma context.

Let me read the source file to understand the lemma and its context.

Let me find the lemma and relevant definitions.

Let me read the relevant module definitions around the lemma.

Let me find the SKE module type definition.

Let me look at the SKE module type and the key ctr lemmas.

Now I understand the lemma. `CCP_OCCP` shows `A(GenChaChaPoly(OCC(I))).main ~ A(OChaChaPoly(I)).main` give equal results. The two SKE oracles differ only in that `GenChaChaPoly(OCC(I))` uses the modular `ChaCha`/`Poly` procedures while `OChaChaPoly(I)` inlines the `gen_CTR_encrypt_bytes`/`genpoly1305` ops — exactly what `chacha_spec` and `poly_spec` (admitted, earlier in section) bridge. Standard approach: adversary `proc` with invariant `={glob I, glob OCC}`.

Let me load the MCP tool schema.

Now let me commit the adversary `proc` tactic with the oracle invariant.
