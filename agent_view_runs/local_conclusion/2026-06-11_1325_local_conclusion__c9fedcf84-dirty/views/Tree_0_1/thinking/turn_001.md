# Tree-0.1 · turn 1 · commit_tactic

<!-- session bd946db8-6bb2-46f8-ab63-3851d56b380a · 2026-06-11T20:32:37.539Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (MtE_security &m) (PtE_security &m) (CBC_security &m).`

---

I'll start by loading the proof intent tool and reading the current workspace view.

The goal is a probability bound chaining lemma. Let me read the target file to find sibling lemmas around `local_conclusion`.

`CBCa.Conclusion` is the keystone. Let me check the clone parameters (what `ell`, `dBlock`, `Random` map to) and the section's adversary axioms.

Now let me look at the wrapper adversaries `RCPAa` (RCPA_pad) and `RCPA_WUF_RCPA.RCPAa` (RCPA_CMA), plus the MAC declaration, to plan the losslessness side-condition.
