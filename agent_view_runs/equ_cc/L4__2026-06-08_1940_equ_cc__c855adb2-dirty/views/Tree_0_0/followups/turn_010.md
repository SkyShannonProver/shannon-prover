## Requested: `inspect_context` — checkpoints

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
```
_…(+53 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–5) — absorb with `sp`/`wp`: 5 setup statement(s): k0 <- k; n0 <- n; c0 <- C.ofintd i; ... (2 more)
- frontier: right side only at `z <$ dblock`
- frontier: left side only at `r0 <$ dblock`
- frontier: left side only at `if (x1 \notin SplitD.ROF.RO.m) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Rewind targets — submit one `undo_to_checkpoint` to rewind
Structural rewind targets in THIS node's committed proof. Submit the `undo_to_checkpoint` payload shown on a target to rewind to it: that restores the committed proof to the selected point (undoing that tactic and every committed tactic after it), and later steps can then be re-committed.
- `Before inline expansion #4` (committed step 4) — inline boundary; selecting it restores the proof state before this expansion
  → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_4_92843bd13814cb9f"}}`

## Status
remaining **2** · phase `seq_cut` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> &m; wp; skip; rewrite /SplitD.test /=; smt(C.ofintdK max_cipher_size_ok …` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

