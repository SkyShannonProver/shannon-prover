# Tree-0.0 · turn 35 · probe_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T00:59:28.093Z -->

**Intent:** `probe_tactic`  
**Payload:** `smt(BBS.big_cons xorwA xorwC xorw0).`

---

I'll read the latest workspace view to see the current proof state.

Let me look at the source to find the exact word-xor lemma names available, since the closing step needs group reasoning on `+^`.

Good — word lemmas are `xorwA`, `xorwC`, `xorw0`, and Bigop is cloned as `BBS` (so `BBS.big_cons`). The leaf needs: expand `big ... (j::s)` via `big_cons`, then use H (which gives the sum = zerow since `j=i0`) plus xor laws. Let me probe smt with those hints.

Let me load the MCP tool schema to submit the probe.

I'll probe smt with the big_cons and xor lemma hints.
