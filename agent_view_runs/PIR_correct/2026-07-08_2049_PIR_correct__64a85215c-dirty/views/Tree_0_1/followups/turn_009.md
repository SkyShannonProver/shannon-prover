## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
i0: int
hi: 0 <= i0 < N
z: int
------------------------------------------------------------------------
Context : hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Bound   : [=] 1%r

pre =
  ((0 <= j <= N /\
    i = i0 /\
    (j <= i0 => PIR.s = PIR.s') /\ (i0 < j => sxor2 PIR.s PIR.s' i0)) /\
   j < N) /\
  N - j = z

(1)  b <$ {0,1}               

post =
  if j = i then
    if b then
      let s1 = j :: PIR.s in
      let j0 = j + 1 in
      (0 <= j0 <= N /\
       i = i0 /\ (j0 <= i0 => s1 = PIR.s') /\ (i0 < j0 => sxor2 s1 PIR.s' i0)) /\
      N - j0 < z
    else
      let s' = j :: PIR.s' in
      let j0 = j + 1 in
      (0 <= j0 <= N /\
       i = i0 /\ (j0 <= i0 => PIR.s = s') /\ (i0 < j0 => sxor2 PIR.s s' i0)) /\
      N - j0 < z
  else
    if b then
      let s1 = j :: PIR.s in
      let s' = j :: PIR.s' in
      let j0 = j + 1 in
      (0 <= j0 <= N /\
       i = i0 /\ (j0 <= i0 => s1 = s') /\ (i0 < j0 => sxor2 s1 s' i0)) /\
      N - j0 < z
    else
      let j0 = j + 1 in
      (0 <= j0 <= N /\
       i = i0 /\
       (j0 <= i0 => PIR.s = PIR.s') /\ (i0 < j0 => sxor2 PIR.s PIR.s' i0)) /\
      N - j0 < z
[26|check]>
```

---

## Status
remaining **2** · phase `plain`

---

### Need more? submit one read-only request
- `tactic_forms` (+name); name choices: `while`, `rnd`, `wp`, `rcondt`, `rcondf`, `rewrite`, `apply`
  submit `{"intent": "tactic_forms", "payload": {"name": "<name>"}}`

---

## Read-only result
## Requested: `tactic_forms` -- `rnd`

**Returned text:**
```text
=== `rnd` tactic — argument forms ===

Current proof mode: ambient

Form 1:  rnd.
  Use when: Symmetric random sampling: both sides sample from the same distribution and EC can infer the coupling automatically (usually just identity).
  Example:  rnd.

Form 2:  rnd (fun s => FWD(s)) (fun s => BWD(s)).
  Use when: Bijection coupling: the two samples are related by a bijection. Provide forward map and backward map. EC generates a subgoal to show FWD and BWD are mutual inverses.
  Example:  rnd (fun s => s + mask) (fun s => s - mask).
  Note:     THE key technique for game hops that shift/mask random samples. Look for it whenever a sampled value on one side equals the other side's sample plus a deterministic offset.

Form 3:  rnd{1}. / rnd{2}.
  Use when: Drop a one-sided sampling that's not present on the other side (dead-code elimination for randoms). Typical: LHS samples something the proof doesn't use, RHS doesn't sample.
  Example:  rnd{1}.    (* drop useless LHS sample *)
  Note:     In branch-local pRHL surgery, it is also common to combine a one-sided drop with an aligned sample step, e.g. `rnd{2}; rnd.` when the RHS has an extra instrumentation sample before the shared sample.

Form 4:  rnd predT.    (* phoare/pHL single program *)
  Use when: SINGLE-program phoare/bd_hoare goal (`phoare[...] = p` / `[<=] p` / `[>=] p`, or `bd_hoare`) whose program ends in a sample `x <$ d`, where the postcondition does NOT constrain the sampled value — the probability-1 / losslessness case. `predT` is the always-true event, so EC reduces the sample step to `mu d predT = 1%r` (i.e. `is_lossless d`); discharge it with the distribution's `*_ll` lemma.
  Example:  proc; rnd predT; skip => />; smt(dbool_ll).
  Note:     The argument is a PREDICATE / event (`'a -> bool`), NOT a probability-mass function — EC computes the sample's contribution as `mu d <event>`. `rnd.` (no argument) also works when the post is independent of the sampled variable (EC infers the event as `predT`); pass `predT` explicitly when that inference fails. Do NOT use the two-function `rnd (fwd) (bwd)` bijection form here — that is pRHL-only and EC rejects it in a single-program goal.

Form 5:  rnd (fun x => P x).    (* phoare/pHL single program *)
  Use when: SINGLE-program phoare/bd_hoare goal where the bound is the probability that the freshly sampled value satisfies a specific predicate `P`. EC reduces the sample step to `mu d (fun x => P x) <cmp> bound` (the `<cmp>` matches the goal's `=` / `<=` / `>=`).
  Example:  rnd (fun b => !b); skip; smt(dbool_funi dbool_fu).    (* EasyCrypt examples/PIR.ec *)
  Note:     `P` ranges over the sampled value's type only (no `{1}`/`{2}` side annotation — this is one program). Discharge the residual mass obligation with the distribution's mass lemmas (`mu1_*`, `dboolE`, `*_funi`, `*_fu`, `*_ll`).

⚠️  Common mistake: Mode confusion is the #1 trap. In pRHL (two programs, `equiv [_ ~ _]`), `rnd.` with a non-trivial coupling fails — use `rnd (fwd) (bwd)` with explicit mutually-inverse maps. In a SINGLE-program phoare/bd_hoare goal (`phoare[...] = p`), the two-function bijection form is INVALID; `rnd` there takes one predicate/event argument — `rnd predT.` for a probability-1 sample (residual is the distribution's losslessness), or `rnd (fun x => P x).` to reduce to `mu d P`. Read the goal head (`equiv [...]` vs `phoare[...]`/`bd_hoare`) before choosing the form.

See also: while, wp, phoare, conseq  (run `-tactic-forms <name>` for any of these)
```

---

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

The current goal is shown in full above. If context is compacted or this response is truncated, re-read `LEGAL_LATEST_FOLLOWUP` for the same agent-readable surface; the raw workspace JSON is audit-only.