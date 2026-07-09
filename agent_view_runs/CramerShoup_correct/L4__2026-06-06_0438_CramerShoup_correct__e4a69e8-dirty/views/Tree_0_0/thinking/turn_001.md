# Tree-0.0 · turn 1 · probe_tactic

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:39:35.924Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc.`

---

I'll start by orienting myself: loading the MCP tool, reading the source, and understanding the proof structure.

I have the full file. My target is just `CramerShoup_correct` (lines 181-184) — a hoare correctness statement. Notably, the `equiv CCA_DDH0` proof at lines 287-308 shows me the exact group-algebra toolkit this file uses: `log_bij`, `logg1`, `logrzM`, `logDr`, and `ring`.

Let me start by entering the procedure. First, a probe of `proc.`.
