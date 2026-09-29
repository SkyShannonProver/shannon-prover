## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
i0: int
hi: 0 <= i0 < N
------------------------------------------------------------------------
Context : hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Bound   : [=] 1%r

pre = i = i0

(1------)  j <- 0                     
(2------)  (PIR.s, PIR.s') <- ([], [])
(3------)  while (j < N) {            
(3.1----)    b <$ {0,1}               
(3.2----)    if (j = i) {             
(3.2.1--)      if (b) {               
(3.2.1.1)        PIR.s <- j :: PIR.s  
(3.2.1--)      } else {               
(3.2.1?1)        PIR.s' <- j :: PIR.s'
(3.2.1--)      }                      
(3.2----)    } else {                 
(3.2?1--)      if (b) {               
(3.2?1.1)        PIR.s <- j :: PIR.s  
(3.2?1.2)        PIR.s' <- j :: PIR.s'
(3.2?1--)      }                      
(3.2----)    }                        
(3.3----)    j <- j + 1               
(3------)  }                          

post = big predT<:int> a PIR.s +^ big predT<:int> a PIR.s' = a i0
[24|check]>
```

---

## Status
remaining **1** · phase `plain`

---

### Need more? submit one read-only request
- `operator_lemmas` (+operator); operator choices: `(+^)`
  submit `{"intent": "operator_lemmas", "payload": {"operator": "<operator>"}}`
- `tactic_forms` (+name); name choices: `call`, `sp`, `while`, `wp`, `swap`, `rcondt`, `rcondf`, `conseq`
  submit `{"intent": "tactic_forms", "payload": {"name": "<name>"}}`

---

## Read-only result
## Requested: `tactic_forms` -- `while`

**Returned text:**
```text
=== `while` tactic — argument forms ===

Current proof mode: ambient

Form 1:  while (INVARIANT) (VARIANT).
  Use when: One-sided phoare/probabilistic loop: the proof is already inside a `phoare` obligation and the loop needs both an invariant and a decreasing integer measure.
  Example:  while (0 <= j <= N /\ oflist s = restr x j) (N - j).
  Note:     Do not append `: p`, `(p)`, or any probability argument. The second parenthesized argument is the termination measure; EC generates the probability/body side obligations after this step.

Form 2:  while (INVARIANT).
  Use when: Symmetric while: both sides have while loops that advance together. Invariant holds between iterations.
  Example:  while (={p, c, i, n} /\ OCC.gs{1} = RO.m{2}); auto.

Form 3:  while{1} (INVARIANT) (TERMINATION).
  Use when: One-sided while on LHS: LHS has a while, RHS doesn't (or has already been processed). Provide INVARIANT (holds each iteration) AND a TERMINATION measure (strictly decreasing integer that reaches 0 to end the loop).
  Example:  while{1} (0 <= i <= n) (n - i).
  Note:     Termination measure REQUIRED for one-sided while. EC won't accept without it.

Form 4:  while{2} (INVARIANT) (TERMINATION).
  Use when: One-sided while on RHS: symmetric to {1} form, just for RHS. Typical case: the RHS has a forgery-detection loop or lookup loop that the LHS doesn't.
  Example:  while{2} (0 <= i <= size ns /\ forged = exists j, 0 <= j < i /\ ...) (size ns - i).
  Note:     Common pattern: a forgery-detection or table-lookup loop on the RHS that scans for a witness while the LHS proceeds without it.

⚠️  Common mistake: Trying symmetric `sim` or `while (Inv)` when LHS and RHS programs are asymmetric (different number of loops, one-sided code). The fix is `while{1}` or `while{2}` with a termination measure. Detecting asymmetry: check if `proc; inline *; sim` leaves significant residual goal — if yes, programs diverged.

See also: seq, sim  (run `-tactic-forms <name>` for any of these)
```

---

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

The current goal is shown in full above. If context is compacted or this response is truncated, re-read `LEGAL_LATEST_FOLLOWUP` for the same agent-readable surface; the raw workspace JSON is audit-only.