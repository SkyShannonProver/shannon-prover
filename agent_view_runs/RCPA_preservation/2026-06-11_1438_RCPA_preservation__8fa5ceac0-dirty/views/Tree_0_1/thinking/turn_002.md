# Tree-0.1 · turn 2 · commit_tactic

<!-- session 7b045324-0954-4f34-a974-d63f5851a2c0 · 2026-06-11T21:41:16.493Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[INDR_CPA(MacThenEncrypt(E, M), A).main() @ &m : res] = Pr[SKEa.RCPA.INDR_CPA(E, RCPAa(M, A)).main() @ &m : res] by exact (RCPA_prob E M A &m).`

---

Intros accepted. Now rewriting the real-scheme side with the sibling lemma `RCPA_prob`.
