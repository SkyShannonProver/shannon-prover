# Tree-0.0 · turn 38 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:17:08.676Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}); first by smt().`

---

THEN branch (bad-flip): after `bad<-true` both sides, `bad{2}` is true so the post reduces to `bad{1}<=>bad{2}` (both true) — both sides just need to terminate. Same pattern as before. Weakening the post via conseq.
