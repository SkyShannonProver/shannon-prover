## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
i0: int
hi: 0 <= i0 < N
z: int
------------------------------------------------------------------------
Context : hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Bound   : [=] 1%r

pre =
  ((i = i0 /\
    0 <= i0 < N /\
    0 <= j <= N /\
    (j <= i0 => PIR.s = PIR.s') /\ (i0 < j => sxor2 PIR.s PIR.s' i0)) /\
   j < N) /\
  N - j = z

(1)  b <$ {0,1}               

post =
  if j = i then
    if b then
      let s1 = j :: PIR.s in
      let j0 = j + 1 in
      (i = i0 /\
       0 <= i0 < N /\
       0 <= j0 <= N /\
       (j0 <= i0 => s1 = PIR.s') /\ (i0 < j0 => sxor2 s1 PIR.s' i0)) /\
      N - j0 < z
    else
      let s' = j :: PIR.s' in
      let j0 = j + 1 in
      (i = i0 /\
       0 <= i0 < N /\
       0 <= j0 <= N /\
       (j0 <= i0 => PIR.s = s') /\ (i0 < j0 => sxor2 PIR.s s' i0)) /\
      N - j0 < z
  else
    if b then
      let s1 = j :: PIR.s in
      let s' = j :: PIR.s' in
      let j0 = j + 1 in
      (i = i0 /\
       0 <= i0 < N /\
       0 <= j0 <= N /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0)) /\
      N - j0 < z
    else
      let j0 = j + 1 in
      (i = i0 /\
       0 <= i0 < N /\
       0 <= j0 <= N /\
       (j0 <= i0 => PIR.s = PIR.s') /\ (i0 < j0 => sxor2 PIR.s PIR.s' i0)) /\
      N - j0 < z
[26|check]>
```

---

## Status
remaining **2** · phase `plain`

---

### Need more? submit one read-only request
- `tactic_forms` (+name); name choices: `while`, `rnd`, `wp`, `rcondt`, `rcondf`, `rewrite`, `apply`
  submit `{"intent": "tactic_forms", "payload": {"name": "<name>"}}`

---

**Last action:** `move => z; wp.` -- EasyCrypt accepted the committed tactic.

---

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

The current goal is shown in full above. If context is compacted or this response is truncated, re-read `LEGAL_LATEST_FOLLOWUP` for the same agent-readable surface; the raw workspace JSON is audit-only.