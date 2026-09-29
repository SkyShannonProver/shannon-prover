# Tree-0.0 · turn 31 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:39:06.848Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -(@D4_6.pr_sampleE &2 tt (pred1 (f a))).`

---

Support condition done. Main goal: `(if 1<=a<=4 then inv 4 else 0) = mu1 D (f a)`. Let me check `dexcepted1E`'s exact form.

I can avoid the dexcepted arithmetic entirely by reusing `pr_sampleE` + `prD4`: `mu1 D (f a) = Pr[SampleE(tt): res=f a] = Pr[D4.sample: res=f a] = prD4 (f a)`. Let me try the first rewrite (right-to-left `pr_sampleE`).
