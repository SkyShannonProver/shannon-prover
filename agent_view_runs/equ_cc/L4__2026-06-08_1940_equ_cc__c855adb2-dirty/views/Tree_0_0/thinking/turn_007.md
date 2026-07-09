# Tree-0.0 · turn 7 · lookup_symbol

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:47:14.154Z -->

**Intent:** `lookup_symbol`  
**Payload:** `C.ofintdK`

---

The rcondf produced a side-goal: prove `! SplitD.test x` (i.e. `C.toint (C.ofintd i) <> 0`) after the setup assignments. This needs the counter round-trip fact `toint(ofintd i) = i` (valid since `1 <= i <= max_counter`). Let me find the exact name of that subtype lemma in the EasyCrypt source.

Found it: Subtype has `insubdK : P x => val (insubd x) = x` and `val_insubd`. With the `rename "ofint", "toint"` sugar (val→toint, insubd→ofintd), the round-trip lemma should be `C.ofintdK`. Let me confirm its exact name and signature before using it.
