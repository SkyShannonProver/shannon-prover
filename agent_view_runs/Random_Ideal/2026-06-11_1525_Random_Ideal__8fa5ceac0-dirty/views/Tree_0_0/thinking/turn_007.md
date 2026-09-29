# Tree-0.0 · turn 7 · commit_tactic

<!-- session 0ebceb60-af84-4e06-90e7-5d4bc72be9df · 2026-06-11T22:29:35.522Z -->

**Intent:** `commit_tactic`  
**Payload:** `transitivity{2} { r <@ Sample.sample(size p + 1); } (size p{1} = size p{2} ==> c{1} = r{2}) (={k, p} ==> ={r}).`

---

Goal 1 closed. Now the second `transitivity` on side 2 to introduce `Sample.sample`.
