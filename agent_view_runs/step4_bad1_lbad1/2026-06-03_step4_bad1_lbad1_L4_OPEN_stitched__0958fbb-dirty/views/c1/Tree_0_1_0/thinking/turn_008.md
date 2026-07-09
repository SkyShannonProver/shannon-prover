# Tree-0.1.0 · turn 8 · probe_tactic

<!-- session 6ba4c334-113f-4b01-a999-5d6b459f95b9 · 2026-06-03T20:37:55.099Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> />.`

---

The inline inspect just redirects me to `call_site_surface` in the full view. The handoff `program_frontier` reported `live_call_sites: 0`, which conflicts with my "it's a call" hypothesis. Let me read the actual full workspace view to settle what the residual program really is.

The decisive signal is in `candidate_moves.limitations`: *"No program frontier remains; solve the residual side condition."* So this is a **pure logical residual** `pre => post` (the `&1`/`&2` are bound memories, not universally-quantified — hence `move=> &1 &2` says "nothing to introduce", and `skip`/`sp`/`if` are inapplicable). The parent's failure was throwing one monolithic `rewrite /check_plaintext; smt(...)` at the whole bundled conjunction.

Let me consult the advisor before committing to the divergent strategy (introduce + substitute equalities + split the post conjuncts + targeted closes vs. monolithic smt).

The advisor confirms the diagnosis and strategy: discharge in place (the "move up" action doesn't fit — note in report), decompose the post, supply existential witnesses by hand (translating Tree-0.0's fragments), since SMT provably cannot synthesize those witnesses. Let me probe `move=> />.` to see the residual subgoals it produces after substituting the `{1}={2}` equalities.
