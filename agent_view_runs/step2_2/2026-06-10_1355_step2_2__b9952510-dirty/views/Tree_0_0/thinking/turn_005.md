# Tree-0.0 · turn 5 · undo_last_step

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T21:04:01.198Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

The relational goal is set up. The right program (`UFCMA_poly`) begins with the same GenChaChaPoly game that `UFCMA_genCC` relates to the left. Let me read the game/oracle module definitions to plan the alignment.

Let me check `genpoly1305`, `get`, and `mk_rs` to see whether tag verification actually depends on `Mem.k` (the `UFCMA_genCC` postcondition omits `Mem.k`).

Confirmed: `get gs k n c = oget gs.[(n,c)]` ignores `k`, and `genpoly1305 (get gs) k n p` only reads the RO block at `(n, ofintd 0)` — so tag verification (hence `dec`) is independent of `Mem.k`. That resolves the `Mem.k` gap left by `UFCMA_genCC`'s postcondition.

I'll restructure h2 into a cleaner two-step form: first an equality moving to the GenChaChaPoly game (via `UFCMA_genCC`), then the forge bound. Let me undo the direct byequiv.
