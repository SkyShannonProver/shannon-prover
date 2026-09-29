## 🔍 Probe preview — `wp.` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, v, v0 : bool, i : int,
             h, a, a0, v1, v', a2, v2, v'0 : group,
             w0, r, z1, z3 : ZModE.exp,
             x, h0, x0, x1, h1, h2, h3, h4 : statement, w, w1 : witness,
             m, m0, m1, a1, a3 : message, s : secret,
             e, e0, e1, e2, e3, e4, e5 : challenge, z, z0, z2, z4 : response,
             t : message * challenge * response,
             to, to0, to1 : (message * challenge * response) option}
&2 (right) : {b : bool, h, a : group, w0, r, e1, z1 : ZModE.exp,
             x, x0, h0, h1 : statement, w, w1, w2 : witness,
             m, m0, a0 : message, s, r0 : secret, e, e0, e2 : challenge,
             z, z0 : response, t : message * challenge * response,
             sw : statement * witness, ms : message * secret}
pre = (glob D){1} = (glob D){2}
w0 <$ dt                   (1--)  w0 <$ dt
if (w0 = zero) {           (2--)
  w0 <- zero               (2.1)
}                          (2--)
h <- g ^ w0                (3--)
(x, w) <- (h, w0)          (4--)
h0 <- x                    (5--)
w1 <- w                    (6--)
r <$ dt                    (7--)
post =
  if w0{2} = zero then
    let x0_R = g ^ zero in
    (forall (e1R : ZModE.exp), e1R \in dt => e1R = e1R) &&
    forall (eL : challenge),
      eL \in de =>
      eL = eL &&
      (forall (rR : ZModE.exp), rR \in dt => rR = rR + eL * w{1} - eL * w{1}) &&
      forall (z1L : ZModE.exp),
        z1L \in dt =>
        z1L = z1L - eL * w{1} + eL * w{1} &&
        let r_R = z1L - eL * w{1} in
        let m0_R = g ^ r_R in
        let t_R = (m0_R, eL, (m0_R, r_R).`2 + eL * (x0_R, zero).`2) in
        let m0_L = g ^ z1L * x{1} ^ -eL in
        let t_L = oget (Some (m0_L, eL, z1L)) in
        (((x{1}, t_L).`1 = (x0_R, t_R).`1 /\ (x{1}, t_L).`2 = (x0_R, t_R).`2) /\
         (glob D){1} = (glob D){2} /\ true) &&
        forall (result_L result_R : bool) (D_L D_R : (glob D)),
          result_L = result_R /\ D_L = D_R /\ true => result_L = result_R
  else
    let x0_R = g ^ w0{2} in
… (+18 more lines)
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

