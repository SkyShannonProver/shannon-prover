## 🔍 Probe preview — `inline *.` accepted · committed state unchanged
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
w0 <$ dt                                 ( 1-----)  w0 <$ dt
if (w0 = zero) {                         ( 2-----)  if (w0 = zero) {
  w0 <- zero                             ( 2. 1--)    w0 <- zero
}                                        ( 2-----)  }
h <- g ^ w0                              ( 3-----)  h <- g ^ w0
(x, w) <- (h, w0)                        ( 4-----)  (x0, w) <- (h, w0)
h0 <- x                                  ( 5-----)  h0 <- x0
w1 <- w                                  ( 6-----)  w1 <- w
r <$ dt                                  ( 7-----)  r <$ dt
a <- g ^ r                               ( 8-----)  a <- g ^ r
(m, s) <- (a, r)                         ( 9-----)  (m0, s) <- (a, r)
e <$ de                                  (10-----)  h1 <- x0
x0 <- x                                  (11-----)  a0 <- m0
e0 <- e                                  (12-----)  e1 <$ dt
h1 <- x0                                 (13-----)  e0 <- e1
e2 <- e0                                 (14-----)  sw <- (x0, w)
z1 <$ dt                                 (15-----)  ms <- (m0, s)
a0 <- g ^ z1 * h1 ^ -e2                  (16-----)  e2 <- e0
(m0, e0, z) <- (a0, e2, z1)              (17-----)  w2 <- sw.`2
h2 <- x0                                 (18-----)  r0 <- ms.`2
a1 <- m0                                 (19-----)  z1 <- r0 + e2 * w2
e3 <- e0                                 (20-----)  z0 <- z1
z2 <- z                                  (21-----)  (x, m, e, z) <- (x0, m0, e0, z0)
v1 <- a1 * h2 ^ e3                       (22-----)  t <- (m, e, z)
v' <- g ^ z2                             (23-----)
v <- v1 = v'                             (24-----)
if (v) {                                 (25-----)
  to0 <- Some (m0, e0, z)                (25. 1--)
} else {                                 (25-----)
  to0 <- None<:message * challenge *     (25? 1--)
    response>                            (      -)
… (+35 more lines)
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

