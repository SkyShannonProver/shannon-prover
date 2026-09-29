# Tree-0.0 · turn 1 · probe_tactic

<!-- session 0a515f21-14cf-4eb0-8268-add1012f095d · 2026-06-06T20:39:55.850Z -->

**Intent:** `probe_tactic`  
**Payload:** `by move=> h; rewrite -(parseK r p) -(parseK r' p') h.`

---

I'll start by loading the MCP tool schema, then work the proof. The goal is `(r || p) = (r' || p') => (r,p) = (r',p')`, and we have `parseK r p: parse (r || p) = (r,p)` available — applying `parse` to both sides should close it.
