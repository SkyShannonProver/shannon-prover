# Tree-0.1.0 · turn 2 · probe_tactic

<!-- session 6ba4c334-113f-4b01-a999-5d6b459f95b9 · 2026-06-03T20:28:48.271Z -->

**Intent:** `probe_tactic`  
**Payload:** `skip.`

---

The probe shows `move=> &1 &2` fails with "nothing to introduce" — the goal is still a relational judgment (programs in sync, empty bodies), not yet a logical implication. I need `skip`/`auto` first. Let me probe the suggested `auto.` to see the residue.
