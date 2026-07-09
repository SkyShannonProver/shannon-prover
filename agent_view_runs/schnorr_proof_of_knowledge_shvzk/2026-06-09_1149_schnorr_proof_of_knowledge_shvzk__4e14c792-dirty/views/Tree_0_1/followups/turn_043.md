## 🔍 Probe preview — `auto.` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
forall &1 &2,
  (glob D){1} = (glob D){2} =>
  (forall (w0R : ZModE.exp), w0R \in dt => w0R = w0R) &&
  forall (w0L : ZModE.exp),
    w0L \in dt =>
    w0L = w0L &&
    if w0L = zero then
      let x_L = g ^ zero in
      forall (r1 : ZModE.exp),
        r1 \in dt =>
        if w0L = zero then
          forall (eL : challenge),
            eL \in de =>
            (forall (rR : ZModE.exp),
               rR \in dt => rR = rR + eL * zero - eL * zero) &&
            forall (z1L : ZModE.exp),
              z1L \in dt =>
              z1L = z1L - eL * zero + eL * zero &&
              ((x_L = g ^ zero /\
                g ^ z1L * x_L ^ -eL = g ^ (z1L - eL * zero) /\
                z1L = z1L - eL * zero + eL * zero) /\
               (glob D){1} = (glob D){2}) &&
              forall (result_L result_R : bool) (D_L D_R : (glob D)),
                result_L = result_R /\ D_L = D_R => result_L = result_R
        else
          forall (eL : challenge),
            eL \in de =>
            (forall (rR : ZModE.exp),
               rR \in dt => rR = rR + eL * zero - eL * zero) &&
            forall (z1L : ZModE.exp),
              z1L \in dt =>
              z1L = z1L - eL * zero + eL * zero &&
              ((x_L = g ^ w0L /\
                g ^ z1L * x_L ^ -eL = g ^ (z1L - eL * zero) /\
                z1L = z1L - eL * zero + eL * w0L) /\
               (glob D){1} = (glob D){2}) &&
              forall (result_L result_R : bool) (D_L D_R : (glob D)),
                result_L = result_R /\ D_L = D_R => result_L = result_R
    else
      let x_L = g ^ w0L in
      forall (r1 : ZModE.exp),
        r1 \in dt =>
        if w0L = zero then
          forall (eL : challenge),
            eL \in de =>
… (+26 more lines)
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

