# Tree-0.0 · turn 1 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:23:57.279Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> hf hfinv.`

---

I'll start by loading the proof-intent tool and reading the current workspace view.

Let me find the `WhileSamplingFixedTest` theory to understand `SampleE`, `SampleWi`, and its main equivalence lemma.

I now understand the structure. The clone `D4_6` instantiates `dt=[1..6]`, `test=(fun r=>!1<=r<=4)`, and provides `sampleE_sampleWi`. My helpers `D4_Sample` (D4~SampleE, `={res}`) and `D6_Sample` (D6~SampleWi, `={res}`) bridge to the clone. Since both programs are uniform on `{1,2,3,4}` and `finv` is a bijection there, I'll prove it via `bypr`, reducing to a probability identity I can compute through the proven lemmas.

Let me start by introducing the two hypotheses.
