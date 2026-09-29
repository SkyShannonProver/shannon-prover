# Tree-0.0 · turn 1 · commit_tactic

<!-- session d09e7b01-d19a-40f9-88c6-39b890db65fb · 2026-07-09T03:51:35.344Z -->

**Intent:** `commit_tactic`  
**Payload:** `move => hi.`

---

I'll start by loading the MCP proof tool, since the manager server was still connecting.

I'll load the proof intent tool schema.

Now I understand the target. Let me analyze the proof strategy:

- Goal: `Pr[PIR.main(i0) @ &m : res = a i0] = 1%r`. The result `res = a i0` holds for **all** random choices (it's deterministic), so this is a losslessness + hoare property → use `byphoare`.
- The loop maintains: `j <= i => s = s'` and `i < j => sxor2 s s' i`. At exit (j=N>i), `sxor2 s s' i`, and then `big a s +^ big a s' = a i` by XOR cancellation. Sibling lemmas `sxor_cons`/`sxor2_cons` help the loop step.

Let me start by introducing the hypothesis.
