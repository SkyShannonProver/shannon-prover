# Tree-0.0 · turn 1 · commit_tactic

<!-- session f8e92011-ec92-42b4-9483-8315c67090f8 · 2026-06-11T00:30:25.891Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (ler_trans Pr[UFCMA_l.f() @ &m : has (fun (i : int) => let tt = nth (w1, w2) UFCMA_l.lbad1 i in tt.`1 = tt.`2) (iota_ 0 qdec)]).`

---

I'll start by reading the current workspace view and this node's memory to understand the proof state.

Let me read the latest followup and check the node memory for history.

Fresh start. Let me read the target lemma and its context in the source file.

This is a union-bound argument. Let me look at the `EventPartitioning`/`ListPartitioning` theories that are cloned here, since they likely provide the key bounding lemma.

The key bounding lemma lives in the partitioning theory, but this is fundamentally a union bound over `iota_ 0 qdec`. Let me check the search guide and look for an existing union-bound lemma in the EC stdlib and sibling proofs.

`mu_has_le` at Distr.ec:441 looks like the union-bound core. Let me read around it.

`mu_has_le` (Distr.ec:426) is the exact union bound: `mu d (fun a => has (P a) s) <= big predT (fun b => mu d (fun a => P a b)) s`. I need to lift it to the `Pr` level. Let me check what `Pr[mu_*]` rewrite forms exist and how inequality bounds on `Pr` are done in the stdlib.

`Pr [mu_sub]` is valid (RndExcept.eca:193). Let me see the idiom in context.

Let me check the valid `Pr[mu_*]` rewrite mnemonics from the EC source.

There's a `Pr[mu_has_le]` form. Let me see what it does.

`Pr[mu_has_le]` is exactly the Pr-level union bound — it rewrites `Pr[f()@&m: has Pa s] <= R` into `big predT (fun b => Pr[f()@&m: Pa b]) s <= R`. My plan: bound LHS by `Pr[...: has (fun i => let tt = nth (w1,w2) lbad1 i in tt.\`1=tt.\`2) (iota_ 0 qdec)]` via `Pr[mu_sub]`, then `Pr[mu_has_le]` closes it. Let me confirm the helper lemma signatures.

All helper lemmas confirmed. Let me check how `Pr[mu_sub]` presents its residual implication goal so I write the discharge correctly.

I have all pieces. Let me confirm `tag` so the `nth (w1,w2)` default types correctly, and check the lemmas `index_mem`/`nth_index` exist.

All confirmed: `tag = poly_out`, so `(w1,w2)` is a valid `tag*tag` default, and `neq_w1_w2` ensures out-of-range indices don't collide. My proof:

1. `apply (ler_trans Pr[...: has (fun i => let tt = nth (w1,w2) lbad1 i in tt.\`1=tt.\`2) (iota_ 0 qdec)])`
2. Goal A: `Pr[mu_sub]` then prove the membership⇒has implication via `nthP`/`index`.
3. Goal B: `Pr[mu_has_le]` collapses to the target sum (beta-equal).

Let me load the MCP tool and start committing.

Now I'll commit the first tactic: the transitivity step introducing the `has` intermediate bound.
