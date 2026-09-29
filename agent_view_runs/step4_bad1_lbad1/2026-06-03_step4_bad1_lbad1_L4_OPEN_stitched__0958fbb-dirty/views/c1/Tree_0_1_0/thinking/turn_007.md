# Tree-0.1.0 · turn 7 · inspect_context

<!-- session 6ba4c334-113f-4b01-a999-5d6b459f95b9 · 2026-06-03T20:32:17.046Z -->

**Intent:** `inspect_context`  
**Payload:** `call_site_options`

---

`skip`, `auto`, `sp`, `if` all fail, while the manager keeps surfacing `call_site_options`/`call_invariant_skeleton`. That strongly indicates the residual program's frontier is a **procedure call** (not an assignment/conditional), which is exactly why none of the straight-line tactics apply — and it matches my assigned "move up / use call structure" action. Let me inspect the live call site.
