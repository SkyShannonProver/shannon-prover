# Tree-0.0.r2 · turn 6 · commit_tactic

<!-- session 9c6ff196-6193-4d35-b3d1-45aa33af05e6 · 2026-06-10T22:17:06.713Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (IH c); [ by rewrite -Hlc' | exact Hdec | rewrite take_oversize 1:/# Hns' mem_undup -Hlc'; apply/mapP; exists c => /=; exact Hc ].`

---

That closed the branch (remaining: 2). The next goal is reflexivity. Let me commit, then close the trivial goals.
