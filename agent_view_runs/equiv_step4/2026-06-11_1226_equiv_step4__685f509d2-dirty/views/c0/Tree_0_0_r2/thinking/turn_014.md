# Tree-0.0.r2 · turn 14 · commit_tactic

<!-- session 351c551b-47e9-4b44-8771-01f4aa096d11 · 2026-06-11T16:17:01.885Z -->

**Intent:** `commit_tactic`  
**Payload:** `(have ens: ns{1} = ns{2} by rewrite hns1 hns2 hlc); (have ens1: ns1{1} = ns1{2} by rewrite hns11 hns12 ho ens); (have ens2: ns2{1} = ns2{2} by rewrite hns21 hns22 ho ens); exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} ROout.m{2} ns1{2} ns2{2}; rewrite ens1 ens2 hf1 hf2 hb hc hl hlc hr ho /=; rewrite hns22 hns12 hns2; split; [by apply/filter_uniq/undup_uniq | split; [by move=> n0; rewrite mem_filter /= => -[] | by move=> n0; rewrite mem_filter /= => -[]]].`

---

Hypotheses are in place. Now deriving the cross-side list equalities, providing witnesses, and closing the residue manually (avoiding smt on the higher-order filter facts).
