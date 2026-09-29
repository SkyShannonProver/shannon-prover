# Tree-0.0 · turn 4 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:40:30.317Z -->

**Intent:** `probe_tactic`  
**Payload:** `congr.`

---

The lemma_index only covers file-local lemmas. The crux is the Split theory's RO-equivalence lemma, which lives in the EC library. Let me read the SplitRO theory source directly (it's a library theory, not target-specific).

Now I understand the Split machinery. `SplitCodom.pr_RO_split D p &m x0` gives `Pr[MainD(D,RO)] = Pr[MainD(D,RO_Pair(I1,I2))]`, and `SplitDom.pr_RO_split` does the domain split. The proof is a ladder: `congr` → per-half `byequiv` to `MainD(G4/G5, FinRO)` → FinRO→RO → peel split layers via `pr_RO_split`. Let me start by probing the `congr` opener.
