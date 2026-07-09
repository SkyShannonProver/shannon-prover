# Route Candidate Contract

This anchor defines the minimum acceptable prover-facing view for high-level
route states.  It is intentionally semantic: the view should preserve the proof
phase and verified route options, not merely list tactics that EasyCrypt might
accept.

## Pr Equality Bridge Goals

For a current goal with at least two `Pr[...]` endpoints and an equality or
inequality relation:

- `application_context.proof_story` must be present.
- `proof_story.source` must be one of:
  - `eval_clean_narrative`
  - `deterministic_statement_index`
  - `none`
- If `proof_story.source == none`, `proof_story.unavailable_reason` must explain
  why no high-level story is available.
- `proof_story.active_route_objective` should identify the current game-hop or
  bridge objective before local pRHL/program lowering.
- `inspect_lookup_handles.ask_manager_for[0]` should be `pr_bridge_routes`
  (old name `bridge_options` still resolves as a back-compat alias).
- `pr_bridge_routes` is the primary entrypoint for verified Pr bridge routes
  (game-hops and scheme/endpoint normalizations).
- `equiv_bridge_lemmas` (old name `bridge_lemmas`) is secondary context for
  pRHL/procedure bridge lemma names and must not be the only visible route entry
  when a Pr bridge route can be derived.
- Verified bridge or call routes must rank above direct lowering moves.
- Direct `byequiv=>//.`, broad `inline *.`, and premature `wp.` are
  accepted-but-risky fallbacks unless a verified bridge/call route is
  unavailable and the view says why.

## Pr Bridge Routes Output

`pr_bridge_routes` may expose executable moves only after daemon verification on
the current goal.  The output must use manager-owned intent shape, for example:

```json
{"intent": "commit_tactic", "payload": {"tactic": "TACTIC_CHAIN"}}
```

It must not expose backend/private CLI strings such as `session_cli.py`,
`-chain`, sockets, tokens, or raw bridge-client commands as the agent-facing
protocol.

If deterministic candidates exist but the daemon is unavailable, the inspect
result should say that verification is unavailable and hide executable
candidates rather than presenting unverified tactics as runnable.

## Call-Site Options Output

`call_site_options` must treat narrative `call_template` and
`invariant_sketch` fields as legacy context, not executable authority. Runnable
call-site moves must come from current ProofIR/frontier facts and daemon
verification on the current goal.

Acceptable executable call-site output uses the same manager-owned intent shape:

```json
{"intent": "commit_tactic", "payload": {"tactic": "CALL_TACTIC"}}
```

If ProofIR exposes a call-site route but no concrete tactic is ready, the
inspect result should return context-only evidence describing the route state,
missing slots, or frontier blockers. If concrete candidates exist but daemon
verification is unavailable or rejects them, the result must say so explicitly
and must not present unverified call templates as runnable.

## Rewrite Candidates Output

`rewrite_candidates` may expose executable rewrite/unfold moves only after
daemon verification accepts them with progress on the current goal. Candidate
sources are current-goal hypotheses and frozen session source structure; legacy
narrative closer hints must not be the primary source of runnable rewrite
options in eval-clean runs.

Runnable rewrite candidates must be shown as manager-owned `commit_tactic`
intents, not backend CLI strings such as `-next -c`.

## Step1 Anchor Shape

At the ChaChaPoly `step1` state immediately after `congr.`, an acceptable
`pr_bridge_routes` route includes the binding evidence:

- namespace: `OpCCinit`
- init module: `I_stateless`
- game functor: `G1`
- bridge lemma: `OpCCinit.pr_CCP_OCCP`

The verified route should normalize:

```easycrypt
Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res]
```

to:

```easycrypt
Pr[CCA_game(A, RealOrcls(OpCCinit.OChaChaPoly(I_stateless))).main() @ &m : res]
```

and then rewrite with:

```easycrypt
rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
```
