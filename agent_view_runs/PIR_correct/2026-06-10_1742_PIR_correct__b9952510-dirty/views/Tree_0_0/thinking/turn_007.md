# Tree-0.0 · turn 7 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:45:23.933Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (0 <= j <= N /\ i = i0 /\ big predT a PIR.s +^ big predT a PIR.s' = (if i0 < j then a i0 else zerow)) (N - j).`

---

Now the phoare while with my membership/XOR-cancellation invariant. The key invariant: the XOR-sum difference equals `a i0` once `j` has passed `i0`, else `zerow`. Let me probe it.
