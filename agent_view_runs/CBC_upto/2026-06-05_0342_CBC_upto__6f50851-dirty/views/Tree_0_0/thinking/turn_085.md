# Tree-0.0 · turn 85 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:45:46.409Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; while (0 <= i <= size p) (size p - i).`

---

Form 1: `while (INV) (VARIANT)` for phoare loops. Let me set up the enc losslessness: `proc` then the while with measure `size p - i`. Probing to see the generated obligations.
