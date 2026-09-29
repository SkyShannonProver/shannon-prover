# Tree-0.1.0 · turn 9 · inspect_context

<!-- session 6ba4c334-113f-4b01-a999-5d6b459f95b9 · 2026-06-03T20:38:33.103Z -->

**Intent:** `inspect_context`  
**Payload:** `diagnose`

---

`move=> />` is also rejected — so the advisor's "pure implication" read is contradicted by EC. Combined with `if` giving "invalid first instruction" and `move=> &1 &2` giving "nothing to introduce", this is still a **relational `equiv` judgment** with a non-empty, non-`if` first instruction — but plain `sp`/`auto` won't process it (likely a length imbalance needing indexed/one-sided handling). Let me get EC's actual failure diagnosis rather than keep guessing.
