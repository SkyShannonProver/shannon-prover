## 🔍 Probe preview — `conseq (_: _ ==> ={x, t, glob D}).` accepted · committed state unchanged
_committing this would produce (remaining 2):_
```
Current goal (remaining: 2)
Type variables: <none>
D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
forall &1 &2,
  (glob D){1} = (glob D){2} =>
  forall (t_L : message * challenge * response) (x_L : statement)
    (t_R : message * challenge * response) (x_R : statement),
    x_L = x_R /\ t_L = t_R /\ (glob D){1} = (glob D){2} =>
    (((x_L, t_L).`1 = (x_R, t_R).`1 /\ (x_L, t_L).`2 = (x_R, t_R).`2) /\
     (glob D){1} = (glob D){2} /\ true) &&
    forall (result_L result_R : bool) (D_L D_R : (glob D)),
      result_L = result_R /\ D_L = D_R /\ true => result_L = result_R
[50|check]>
```
→ `commit_tactic` to keep this, or keep probing.

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

