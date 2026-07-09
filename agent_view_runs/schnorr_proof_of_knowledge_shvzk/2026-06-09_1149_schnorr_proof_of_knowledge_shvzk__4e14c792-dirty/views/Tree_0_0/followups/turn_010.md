## 🔍 Probe preview — `auto.` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
&m0: {b : bool, h, a : group, w0, r, e1, z1 : ZModE.exp,
     x, x0, h0, h1 : statement, w, w1, w2 : witness, m, m0, a0 : message,
     s, r0 : secret, e, e0, e2 : challenge, z, z0 : response,
     t : message * challenge * response, sw : statement * witness,
     ms : message * secret}
------------------------------------------------------------------------
forall &hr,
  (glob D){m0} = (glob D){m} /\ (glob D){hr} = (glob D){m} =>
  forall (w0_0 : ZModE.exp),
    w0_0 \in dt =>
    if w0_0 = zero then
      let x2 = g ^ zero in
      forall (r1 : ZModE.exp),
        r1 \in dt =>
        forall (e6 : challenge),
          e6 \in de =>
          forall (z1_0 : ZModE.exp),
            z1_0 \in dt =>
            let m0_0 = g ^ z1_0 * x2 ^ -e6 in
            if m0_0 * x2 ^ e6 = g ^ z1_0 then
              Some (m0_0, e6, z1_0) <> None<:message * challenge * response>
            else
              None<:message * challenge * response> <> None<:message *
              challenge * response>
    else
      let x2 = g ^ w0_0 in
      forall (r1 : ZModE.exp),
        r1 \in dt =>
        forall (e6 : challenge),
          e6 \in de =>
          forall (z1_0 : ZModE.exp),
            z1_0 \in dt =>
            let m0_0 = g ^ z1_0 * x2 ^ -e6 in
            if m0_0 * x2 ^ e6 = g ^ z1_0 then
              Some (m0_0, e6, z1_0) <> None<:message * challenge * response>
            else
              None<:message * challenge * response> <> None<:message *
              challenge * response>
[45|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

