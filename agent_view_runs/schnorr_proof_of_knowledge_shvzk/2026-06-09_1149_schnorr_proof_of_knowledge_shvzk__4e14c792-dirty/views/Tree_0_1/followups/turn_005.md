## 🔍 Probe preview — `proc.` accepted · committed state unchanged
_committing this would produce (remaining 3):_
```
Current goal (remaining: 3)
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool, i : int, x : statement, w : witness, m : message,
             s : secret, e : challenge, t : message * challenge * response,
             to : (message * challenge * response) option}
&2 (right) : {b : bool, x : statement, m : message, e : challenge,
             z : response, t : message * challenge * response}
pre = (glob D){1} = (glob D){2}
(x, w) <@ SchnorrPK.gen()                (1--)  (x, m, e, z) <@ Run(SchnorrPK).main()
(m, s) <@ SchnorrPK.commit(x, w)         (2--)  t <- (m, e, z)
e <$ de                                  (3--)  b <@ D.distinguish(x, t)
to <@                                    (4--)
  SpecialHVZKExperiment(SchnorrPK,       (  -)
    SchnorrPKAlgorithms).main(x, e)      (  -)
i <- 0                                   (5--)
while (to = None<:message * challenge *  (6--)
       response>) {                      (  -)
  to <@                                  (6.1)
    SpecialHVZKExperiment(SchnorrPK,     (   )
      SchnorrPKAlgorithms).main(x, e)    (   )
  i <- i + 1                             (6.2)
}                                        (6--)
t <- oget to                             (7--)
b <@ D.distinguish(x, t)                 (8--)
post = b{1} = b{2}
[42|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

