# Tree-0.1 · turn 1 · inspect_context

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:02:51.162Z -->

**Intent:** `inspect_context`  
**Payload:** `lemma_index`

---

I'll start proving this module-refactoring equivalence. The structure is clear: `GenChaChaPoly(OCC(I))` uses procedure-based `ChaCha`/`Poly`, while `OChaChaPoly(I)` inlines the ops — and the two phoare specs (`chacha_spec`, `poly_spec`) bridge them. The standard idiom is `proc*` then `call` on the abstract adversary.

Let me first pull the lemma index to confirm the spec signatures.

Let me pull the lemma index to confirm spec signatures.
