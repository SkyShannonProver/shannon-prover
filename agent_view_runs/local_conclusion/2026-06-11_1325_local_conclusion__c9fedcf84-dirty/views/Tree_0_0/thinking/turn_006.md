# Tree-0.0 · turn 6 · commit_tactic

<!-- session abd26ef5-2223-44fa-90ae-640e8ee18bd8 · 2026-06-11T20:37:12.478Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(Random)).O').S.enc; inline{2} RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A), QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A)), CBCa.SKEa.RCPA.RCPA_Wrap(CBCa.SKEa.RCPA.Ideal)).O').S.enc.`

---

`MAC.tag` inlined cleanly. Now inlining the `S.enc` wrapper on both sides with explicit functor paths.
