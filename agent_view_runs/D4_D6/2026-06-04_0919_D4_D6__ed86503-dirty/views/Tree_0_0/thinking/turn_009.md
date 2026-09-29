# Tree-0.0 · turn 9 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:29:02.330Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (@D4_6.pr_sampleWi &2 tt 5 (fun (r:int) => finv r = a)).`

---

The `-` rewrite likely failed on higher-order unification of the predicate `P`. With `pragma +implicits`, explicit args need `@`. Let me use `pr_sampleWi` directly with `@` and an explicit predicate.
