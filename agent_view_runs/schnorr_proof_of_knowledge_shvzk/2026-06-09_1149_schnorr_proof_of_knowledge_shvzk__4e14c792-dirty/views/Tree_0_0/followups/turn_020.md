## Requested: `inspect_context` — tactic_forms `call`

_(read-only — committed proof state unchanged; any accepted/rejected text below is route-selection context, not your current error)_

=== `call` tactic — argument forms === Current proof mode: ambient Form 1: call LEMMA. Use when: An equiv lemma already proves the procedure correspondence you need. This is the preferred form when available — EC closes the whole adversary/oracle call in one step. Example: call H_proc. (* uses a pre-declared equiv handle *) Note: EC unifies the pRHL call's LHS/RHS procedure targets against LEMMA's statement. If that succeeds, the call is fully handled. Form 2: call (_: INVARIANT). Use when: No pre-existing equiv lemma matches — you must provide the oracle invariant manually. EC generates oracle-equiv subgoals (one per oracle procedure the adversary may call). Example: call (_: ={Mem.k, Mem.log} /\ StLSke.gs{1} = RO.m{2}). Note: Two pre-flight checks before writing the invariant: (a) Is there already a named equiv lemma that proves this correspondence? Run `-file-index` or check `strategic_helpers[equiv]` in your plan's context brief — if yes, prefer Form 1 (`call LEMMA.`) instead of re-deriving via invariant. (b) For an outer call to an abstract adversary's main (e.g. `A.main`, `BNR_Adv(A).main`), do NOT include `={glob A}` in the invariant. EC handles glob A implicitly via the...

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, v, v0 : bool, i : int,
```
_…(+54 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 3–6) — absorb with `sp`/`wp`: 4 setup statement(s): h <- g ^ w0; (x, w) <- (h, w0); h0 <- x; ... (1 more)
- frontier: both sides at `b <@ D.distinguish(x, t)`
- frontier: both sides at `w0 <$ dt`
- frontier: both sides at `r <$ dt`
- frontier: both sides at `if (w0 = zero) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **1** · phase `seq_cut` / `call_site`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `conseq (_: ={glob D} ==> _) => //.` → accepted
- probe `call (_: ={glob D}).` → REJECTED: The module D can write D (add restriction D to D, or D to D)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

