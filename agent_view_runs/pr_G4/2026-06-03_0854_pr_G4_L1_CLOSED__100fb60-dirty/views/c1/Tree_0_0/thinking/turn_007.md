# Tree-0.0 · turn 7 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:35:39.741Z -->

**Intent:** `commit_tactic`  
**Payload:** `skip => &hr [[hsz hw hg] _]; split; last by move=> v _ h; exact h.`

---

`rnd` reduced to a `mu`-bound plus a trivial coverage conjunct. The real work is `mu dt (fun x => g^x ∈ map fst cilog /\ statics) <= qD/order`. 

The file's `mu_mem_le_mu1_size` lemma (added right before `pr_G4`) is clearly the intended tool, but it's stated for `mu dt (mem l)`, so I need the exact names for: discrete-log/injectivity of `g^·`, `mu1 dt`, and `dmap`. Let me read the EC library source to get exact names rather than guess. First locate the theories.

Good — group is `CyclicGroup as G`, `GP = G.PowZMod`, `dt = GP.FDistr.dt`. Let me read the `Group.ec` theory for `FDistr` (dt facts), exponentiation injectivity, and log.

Found `loge`/`expgK`/`loggK` (bijection) and `pow_bij` (injectivity). Now let me see the FDistr `dt` distribution facts (`mu1 dt`, etc.).

I have everything needed: `dt1E : mu1 dt s = 1/order`, `loggK`/`expgK` (bijection), `pow_bij` (injectivity), and the file's `mu_mem_le_mu1_size`. I need the predicate as `mem l`, so I'll rewrite `(fun x => g^x ∈ L1)` to `mem (map loge L1)`. Let me confirm the monotonicity lemma name and `mem_map`.

I now have all exact names: `dt1E : mu1 dt s = 1/order`, `loggK : loge (g^k) = k`, `map_f`, `mu_le`, and the file's `mu_mem_le_mu1_size`. 

Now discharge the `rnd` VC. First `skip`, intro the precondition, and dispatch the trivial coverage conjunct, leaving the `mu` bound.
