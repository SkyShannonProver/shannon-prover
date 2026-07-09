# Tree-0.0 · turn 13 · inspect_context

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:21:02.078Z -->

**Intent:** `inspect_context`  
**Payload:** `call_subgoals`

---

The error is the known "module A can write A" trap — `call (_: I)` over an abstract adversary must NOT include `={glob A}` (EasyCrypt frames it automatically). Let me drop it and re-test.
