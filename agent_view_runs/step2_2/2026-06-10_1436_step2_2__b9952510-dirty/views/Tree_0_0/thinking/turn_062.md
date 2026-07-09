# Tree-0.0 · turn 62 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:10:09.414Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /=; move: Hdec; rewrite /dec /genpoly1305 /get Hgs Hn0 /=; smt().`

---

Now beta-reduce the leaf and derive the tag equation from `Hdec` by unfolding `dec`/`genpoly1305`/`get` and rewriting with `Hgs`/`Hn0`.
