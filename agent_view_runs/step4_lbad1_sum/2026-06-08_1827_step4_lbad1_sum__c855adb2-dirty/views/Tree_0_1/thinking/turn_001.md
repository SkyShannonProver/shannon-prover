# Tree-0.1 · turn 1 · inspect_context

<!-- session f78d4592-d48f-4bf0-a0cf-dafbe8cdbb92 · 2026-06-09T01:34:29.324Z -->

**Intent:** `inspect_context`  
**Payload:** `lemma_hints`

---

I'll start by loading the MCP tool schema and exploring the EventPartitioning theory that provides the union-bound machinery this goal needs.

Let me read the EventPartitioning theory to find the union-bound / list-partitioning lemma I need.

The union-bound machinery is `LP.list_partitioning` (line 18). The tricky part is expressing `E`/`phi` over `(glob M)`. Let me find real usages of `list_partitioning` to nail the idiom, and check the `Pr` sub-event tactic.

`Pr [mu_sub]` is the term-wise idiom I need. Now let me find `list_partitioning` usage examples to learn the glob handling.

I'll avoid reading `eval/examples/ChaChaPoly/chacha_poly.ec` since in EVAL mode that contains the prior proof of this exact lemma. Let me engage the manager to understand the goal and available routes, starting with the lemma hints.
