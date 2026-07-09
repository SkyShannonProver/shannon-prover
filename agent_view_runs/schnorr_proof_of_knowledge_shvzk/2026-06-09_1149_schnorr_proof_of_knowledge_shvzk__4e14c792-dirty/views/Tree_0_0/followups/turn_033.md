## 🔍 Probe preview — `auto.` accepted · committed state unchanged
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
h <- g ^ w0                  ( 1)  h <- g ^ w0
(x, w) <- (h, w0)            ( 2)  (x0, w) <- (h, w0)
h0 <- x                      ( 3)  h0 <- x0
w1 <- w                      ( 4)  w1 <- w
r <$ dt                      ( 5)  r <$ dt
a <- g ^ r                   ( 6)  a <- g ^ r
(m, s) <- (a, r)             ( 7)  (m0, s) <- (a, r)
e <$ de                      ( 8)  h1 <- x0
x0 <- x                      ( 9)  a0 <- m0
e0 <- e                      (10)  e1 <$ dt
h1 <- x0                     (11)  e0 <- e1
e2 <- e0                     (12)  sw <- (x0, w)
z1 <$ dt                     (13)  ms <- (m0, s)
a0 <- g ^ z1 * h1 ^ -e2      (14)  e2 <- e0
(m0, e0, z) <- (a0, e2, z1)  (15)  w2 <- sw.`2
h2 <- x0                     (16)  r0 <- ms.`2
a1 <- m0                     (17)  z1 <- r0 + e2 * w2
e3 <- e0                     (18)  z0 <- z1
z2 <- z                      (19)  (x, m, e, z) <- (x0, m0, e0, z0)
v1 <- a1 * h2 ^ e3           (20)  t <- (m, e, z)
v' <- g ^ z2                 (21)
v <- v1 = v'                 (22)
to0 <- Some (m0, e0, z)      (23)
to <- to0                    (24)
i <- 0                       (25)
t <- oget to                 (26)
post = x{1} = x{2} /\ t{1} = t{2} /\ (glob D){1} = (glob D){2}
[53|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

