# Tree-0.1.1 · turn 2 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:32:38.248Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* (p{1}.`1).`

---

The tactic was rejected. Let me read the error detail.

The followup lacks the error text. Let me check the manager result JSON.

No detailed error is exposed under this L1 profile, so I'll reason it out. The `call` almost certainly failed because I passed `p{1}.\`1` — a program-variable expression with a memory tag — directly as the lemma's logical argument `n0`, which isn't a valid pure term in the `call` instantiation context. The parent already lifted the RO maps into logical vars `mr0 ms0` via `exists*`/`elim*` precisely so they could be fed to `equ_cc`; the nonce `n0` parameter needs the same treatment. Let me lift it first.
