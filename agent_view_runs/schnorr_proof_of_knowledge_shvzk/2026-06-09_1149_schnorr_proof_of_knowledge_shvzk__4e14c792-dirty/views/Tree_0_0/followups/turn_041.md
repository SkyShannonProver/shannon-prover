## 🔍 Probe preview — `wp.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
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
pre = w0{1} = w0{2} /\ (glob D){1} = (glob D){2}
h <- g ^ w0                (1)  h <- g ^ w0
(x, w) <- (h, w0)          (2)  (x0, w) <- (h, w0)
h0 <- x                    (3)  h0 <- x0
w1 <- w                    (4)  w1 <- w
r <$ dt                    (5)  e1 <$ dt
a <- g ^ r                 (6)
(m, s) <- (a, r)           (7)
e <$ de                    (8)
post =
  (forall (rR : ZModE.exp),
     rR \in dt => rR = rR - e1{2} * w{2} + e1{2} * w{2}) &&
  forall (z1L : ZModE.exp),
    z1L \in dt =>
    z1L = z1L + e1{2} * w{2} - e1{2} * w{2} &&
    let r_R = z1L + e1{2} * w{2} in
    let m0_R = g ^ r_R in
    let m0_L = g ^ z1L * x{1} ^ -e{1} in
    x{1} = x0{2} /\
    oget (Some (m0_L, e{1}, z1L)) =
    (m0_R, e1{2}, (m0_R, r_R).`2 + e1{2} * (x0{2}, w{2}).`2) /\
    (glob D){1} = (glob D){2}
[57|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

