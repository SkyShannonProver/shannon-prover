# Tree-0.1 · turn 11 · undo_last_step

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:07:20.355Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

I made an ordering error: peeling `poly_spec` first captured `c0` as the *uninitialized* pre-state value of `c`, but `c` is written by the `ChaCha.enc` call. The post now demands the chacha output equal that junk `c0`, which is unprovable. I need to rewind and split the two calls with `seq` so the intermediate state binds `c` properly. Let me undo the two peels.
