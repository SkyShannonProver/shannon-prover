# Tree-0.0 · turn 2 · inspect_context

<!-- session 9c846476-96bc-4564-94eb-a9ec19803719 · 2026-06-08T23:58:01.224Z -->

**Intent:** `inspect_context`  
**Payload:** `pr_bridge_routes`

---

Let me look at the broader source to find the `CCA_CPA_UFCMA` generic reduction lemma, since this bound is almost certainly a generic theorem in that cloned theory.

There's a generic `CCA_CPA_UFCMA` lemma. Let me read it and its surrounding theory.

The generic `CCA_CPA_UFCMA` lemma (ske.ec:186) is exactly our bound, but stated over `StLSke(St)` whereas our LHS is over `OChaChaPoly(IFinRO)`. So the plan is: normalize the LHS Pr to `StLSke(St)`, then apply the generic lemma. Let me ask the manager for verified bridge routes.
