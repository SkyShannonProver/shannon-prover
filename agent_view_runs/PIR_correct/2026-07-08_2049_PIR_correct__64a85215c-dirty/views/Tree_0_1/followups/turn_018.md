## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
i0: int
hi: 0 <= i0 < N
------------------------------------------------------------------------
Context : hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Bound   : [=] 1%r

pre = i = i0


post =
  (0 <= 0 <= N /\
   i = i0 /\ (0 <= i0 => [] = []) /\ (i0 < 0 => sxor2 [] [] i0)) /\
  forall (s1 s' : int list) (j0 : int),
    (0 <= j0 <= N /\
     i = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0) =>
     N - j0 <= 0 => ! j0 < N) /\
    (! j0 < N =>
     0 <= j0 <= N /\
     i = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0) =>
     big predT<:int> a s1 +^ big predT<:int> a s' = a i0)
[34|check]>
```

---

## Status
remaining **1** · phase `plain`

---

### Need more? submit one read-only request
- `operator_lemmas` (+operator); operator choices: `(+^)`
  submit `{"intent": "operator_lemmas", "payload": {"operator": "<operator>"}}`
- `tactic_forms` (+name); name choices: `rewrite`, `apply`
  submit `{"intent": "tactic_forms", "payload": {"name": "<name>"}}`

---

**Last action:** `wp.` -- EasyCrypt accepted the committed tactic.

---

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

The current goal is shown in full above. If context is compacted or this response is truncated, re-read `LEGAL_LATEST_FOLLOWUP` for the same agent-readable surface; the raw workspace JSON is audit-only.