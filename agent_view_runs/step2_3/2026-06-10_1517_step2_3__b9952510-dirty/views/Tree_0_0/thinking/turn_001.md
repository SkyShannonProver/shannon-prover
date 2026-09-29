# Tree-0.0 · turn 1 · commit_tactic

<!-- session a51e628e-7b92-45c6-b528-b64183d9b981 · 2026-06-10T22:23:39.015Z -->

**Intent:** `commit_tactic`  
**Payload:** `congr.`

---

I'll start by reading the current workspace view and this node's memory to understand where the proof stands.

Let me check the node memory for history and locate `step2_3` in the source file.

Let me read the followup, notes, and the source around `step2_3` and the related `step2_1`/`step2_2` lemmas.

This is an equality of two probability sums. Strategy: likely `congr` to split into two `byequiv` equalities (CPA↔G8, UFCMA_poly↔G9). Let me gather the relevant module/clone definitions before committing tactics.

Let me read `UFCMA_poly` and find the `Split`/`MainD`/`RO_Pair` definitions.

Let me see the top imports and find the `Split`/`MainD` theory definitions in the EasyCrypt library.

`Split` comes from the `SplitRO` library. Let me locate it.

Let me read the `SplitRO.ec` library to understand `Split`, `IdealAll.MainD`, `SplitCodom`, and `RO_Pair`.

Now I understand the Split machinery. The key library lemma is `SplitCodom.pr_RO_split`: `Pr[MainD(D,RO).distinguish] = Pr[MainD(D,RO_Pair(I1.RO,I2.RO)).distinguish]`. Let me check sibling `step3`'s proof for the idioms used to manipulate these `MainD(G8/G9, ...)` terms.

Both `step3` and `step4_1` are themselves admitted, so no idioms to copy — I must build `step2_3` from scratch. My plan: `congr` to split the sum into the G8/CPA term and G9/UFCMA_poly term, then use `SplitC2.pr_RO_split` to collapse the paired RO, then `byequiv` each. Let me load the MCP tool and start.

I'll commit `congr.` to split the probability-sum equality into two termwise goals.
