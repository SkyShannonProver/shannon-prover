# Tree-0.0 · turn 12 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:10:51.030Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

Now the remaining programs are just:

Left:
1. sk0 <$ dt
2. y <$ dt

Right:
1. x <$ dt
2. y <$ dt

And the post involves `sk0{1}`, `y{1}`, `x{2}`, `y{2}`. The key conditions are:
- `g ^ sk0{1} = g ^ x{2}` (i.e., sk0{1} = x{2})
- `y{1} = y{2}`

So I need to couple the samplings. Both sides sample from `dt` (the uniform distribution over exponents). 

I'll use `rnd.` to couple the y samplings on both sides, which should make y{1}=y{2}, and then couple the first samplings to ensure sk0{1}=x{2}.
