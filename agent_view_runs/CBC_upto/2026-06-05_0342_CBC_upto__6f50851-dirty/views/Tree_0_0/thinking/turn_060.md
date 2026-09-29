# Tree-0.0 · turn 60 · undo_last_step

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:37:11.810Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

The plain `call f_eq` leaves a residual that is **unprovable as-is**: reconstructing `!bad_R ⟹ c{1}=c{2}` needs monotonicity (`!new_bad ⟹ !old_bad`), which `f_eq`'s post doesn't export. This is a real gap. Let me consult the advisor on the cleanest fix.

The residual is genuinely unprovable from plain `f_eq` — reconstructing `!new_bad ⟹ c{1}=c{2}` requires `bad` monotonicity (`old_bad ⟹ new_bad`), which `f_eq`'s post doesn't carry. The clean fix: derive a monotonicity-strengthened `f_eqM` from `f_eq` via `conseq` with a side-2 monotonicity hoare, using a ghost `B` for the pre-call `bad{2}`. Let me undo the failed loop-body step first.
