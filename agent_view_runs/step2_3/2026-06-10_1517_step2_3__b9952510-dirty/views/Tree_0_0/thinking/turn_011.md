# Tree-0.0 · turn 11 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:41:34.430Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hA := SplitD.pr_RO_split (G4(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA.`

---

I'll read the latest workspace view to see the current proof state.

Let me look at the target source and sibling lemmas to mirror the proof structure.

I'm proving `step2_3`. The current first subgoal (of 2) is `Pr[MainD(G4(A), RO).distinguish()] = Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish()]`. Let me check the Split/G8 definitions before deciding the bridge.

Now I understand the structure: this is the RO domain+codomain split equivalence. Let me find the `Split` theory's key lemmas.

`Split` is from the `SplitRO` library. Let me find its key correctness lemmas.

Let me read the actual SplitRO lemma statements and section structure.

I now understand the full split chain. Let me check whether the file already proves an analogous G4↔G8 split I can mirror, by searching for `pr_RO_split`, `G6`, `G8` usages in proofs.

I now understand the full split chain. The LHS bare `MainD(G4(A), RO)` should be `Split0.IdealAll.MainD` over the block RO, and the bridge to `G8` requires a domain split (`SplitD`) then a codomain split (`SplitC1`), mirroring step1's `have/rewrite /=` beta pattern. Let me start the domain split.

Committing the domain split (SplitD) via the beta-safe `have/rewrite /=` pattern.
