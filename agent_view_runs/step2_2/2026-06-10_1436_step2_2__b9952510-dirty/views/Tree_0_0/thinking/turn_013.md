# Tree-0.0 · turn 13 · inspect_context

<!-- session 00419e7b-22c2-477c-b7b6-2ff3591b0428 · 2026-06-10T21:42:01.497Z -->

**Intent:** `inspect_context`  
**Payload:** `call_subgoals`

---

Let me read the full workspace view to see the write_map and global state for constructing the invariant.

The skeleton references `inv_cpa`, `BNR.lenc/ndec`, `Mem.lc/log`. For goal 1 the two sides differ only in the SKE module, so the coupling I need is `StLSke.gs{1} = RO.m{2}` plus equality of the shared oracle state. Let me preview the obligations for a candidate invariant.
