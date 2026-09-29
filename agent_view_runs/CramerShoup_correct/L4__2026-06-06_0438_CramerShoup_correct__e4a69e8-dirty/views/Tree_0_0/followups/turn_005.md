## 🔍 Probe preview — `move=> &hr _ x1 hx1 x2 hx2 y1 hy1 y2 hy2 z1 hz1 z2 hz2 w hw k hk /= u hu /=.` accepted · committed state unchanged
_committing this would produce (remaining 1):_
```
Current goal
Type variables: <none>
&hr: {g_, g, g_0, e, f, h, a, a_, c0, d, g0, g_1, a0, a_0, c1, d0 : group,
     x1, x2, y1, y2, z1, z2, w, u, v, x10, x20, y10, y20, z10, z20, v0 :
     ZModE.exp, k, k0, k1 : K,
     pk0 : K * group * group * group * group * group,
     sk0 : K * group * group * ZModE.exp * ZModE.exp * ZModE.exp *
     ZModE.exp * ZModE.exp * ZModE.exp, pk, pk1 : PKE_.pkey,
     sk, sk1 : PKE_.skey, m, m0 : PKE_.plaintext, c, ci : PKE_.ciphertext,
     m' : PKE_.plaintext option}
x1: ZModE.exp
hx1: x1 \in dt
x2: ZModE.exp
hx2: x2 \in dt
y1: ZModE.exp
hy1: y1 \in dt
y2: ZModE.exp
hy2: y2 \in dt
z1: ZModE.exp
hz1: z1 \in dt
z2: ZModE.exp
hz2: z2 \in dt
w: ZModE.exp
hw: w \in dt \ pred1 zero
k: K
hk: k \in dk
u: ZModE.exp
hu: u \in dt
------------------------------------------------------------------------
(if (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u *
    (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^
    (u *
     H k
       (DH.G.g ^ u, DH.G.g ^ w ^ u,
        (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr})) =
    DH.G.g ^ u ^
    (x1 +
     H k
       (DH.G.g ^ u, DH.G.g ^ w ^ u,
        (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}) *
     y1) *
    DH.G.g ^ w ^ u ^
    (x2 +
     H k
       (DH.G.g ^ u, DH.G.g ^ w ^ u,
        (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}) *
     y2) then
   Some
     ((DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} /
      (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2))
 else None) =
Some m{hr}
[53|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

