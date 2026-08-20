# Proof Terminal Outcome Ownership

Status: canonical harness architecture, implemented 2026-08-08.

This document owns one question: who may say that an entire prover run
succeeded? The answer is exactly one existing coordinator:
`workflow.agents.prover.run()` produces one validated `ProverResult`.

No new parallel terminal service exists. The repair instead separates the
responsibilities that were previously collapsed into two unrelated `proved`
booleans.

## State vocabulary

```text
EasyCrypt/session facts
  OPEN
  GOALS_DISCHARGED_PENDING_QED
  SESSION_CLOSED_PENDING_VERIFICATION
  VERIFIED_SESSION_EVIDENCE
                    |
                    v
tree search handoff
  SessionClosureCandidate
                    |
                    v
run-level outcome
  ProverResult
    verified | incomplete | infrastructure_invalid
```

`proof.candidate_closed` means EasyCrypt discharged the current goals for one
specific session occurrence. It is not a whole-run success event. A tree
"winner" is a scheduling choice. It is not a proof verdict. Only a
`ProverResult(status="verified")` may become `final_proved=true` in a summary.
Upper-layer transports call this fact `goals_discharged`; only a state with
committed `qed.` is a `session_completion_candidate`.

## Existing-module responsibility map

| Module | Owns | Must not own |
|---|---|---|
| `core.easycrypt.committed_history` | Canonical committed-history reading, compound/standalone `qed` recognition, closed-history extraction | Current goal, event validity, run outcome |
| `core.easycrypt.session_runtime` and `session_events` | EasyCrypt mutation lifecycle and append-only factual occurrences | Tree winner or final verification verdict |
| `core.easycrypt.session_projection` | The single joined projection of goal, history, event contract, exact close occurrence and session lifecycle status | Search scheduling or whole-run success |
| `workflow.tree.session_observer` | Provider-neutral transport of one `ProofStateProjection`; workflow telemetry is derived from the same parsed event records | Rereading history/events to decide lifecycle, close, verification, `qed`, or tactic count |
| `ProofNodeManager` and protocol repair | One agent turn, including when `qed.` is legal and which current view is returned | Finalization, writeback or run outcome |
| `workflow.tree.trackers` | Observe whether a node has an authoritative session completion candidate | Offline verification |
| `workflow.tree.supervisor` | Search topology, capacity, termination, selection of one immutable `SessionClosureCandidate`, and the explicit managed-session set inside `TreeRunResult` | `proved`, source writeback or final report |
| `workflow.proof_acceptance` | Fail-closed validation of the canonical projection against immutable candidate identity and final-verification requirements | Resummarizing raw events into another close/verified fact, scheduling, or terminal result publication |
| `workflow.agents.prover_writeback` | Extract the exact candidate history, write the target proof, invoke EasyCrypt verification, revert on failure, emit verification evidence | Selecting a different session or publishing a run verdict |
| `workflow.agents.prover.run` | The only terminal outcome owner; bind the selected candidate to writeback/verification and save `prover_run_result.json` | Reconstructing a candidate from sibling/global files |
| `workflow.orchestrator` | Run lifecycle and a summary projection carrying the canonical result ID/status | Independent precheck or second `proved` judgment |
| `eval_suite.metrics`, `run_report_bundle`, `project_driver` | Validate and present a `ProverResult`; session histories remain diagnostic evidence | Inferring verified success from logs, text, `qed.` suffixes, or summary booleans |

## Immutable handoffs

`SessionClosureCandidate` binds:

- exact node and session;
- target file hash and lemma;
- committed-history hash and tactic count; and
- exact close-result, close-event and terminal-event occurrences.

It is created only from the current authoritative session projection. The
finalizer validates it again before extraction and before target-file write.
Mutable function attributes, `last_ec_session_dir`, directory scans, raw agent
text and the largest history are not semantic fallback sources.

Node-memory proof presentation follows the separate manager-turn boundary. It
is not a terminal-acceptance input.

`TreeRunResult` carries search output, selected identities, candidate,
session records, audits, destructive-abort evidence and infrastructure errors.
It deliberately has no `proved` field.

`ProverResult` is content-addressed by `result_id`. A verified result requires
passing verification evidence. Candidate extraction/finalization failure,
tree infrastructure failure and destructive abort produce
`infrastructure_invalid`; normal search exhaustion produces `incomplete`.

## Projection rules

- `orchestrator.summary.final_proved` is only
  `ProverResult.is_verified` and carries the same result ID/status.
- eval metrics require exactly one valid `prover_run_result.json` and reject a
  contradictory summary.
- automatic run reports may reconstruct accepted/undone histories and label a
  script `session_closed`; they may say `verified` only from `ProverResult`.
- a project-level multi-lemma driver reads the typed result artifact rather
  than parsing console markers.

## Failure that closed this boundary

The paused operation-binding diverse run showed the old ambiguity:
session projection emitted a candidate-close fact before `qed.`, the manager
did not admit the mismatched pending-qed status, the tree set its own `proved`,
and final writeback later set another `proved=false`. The retained run remains
valid diagnostic evidence, but it is infrastructure-invalid for efficacy.

The repair changes the contract, not merely the failing status string:

1. session lifecycle names are canonical and manager preflight consumes them;
2. tree search cannot publish final success;
3. the candidate is content- and occurrence-bound;
4. finalization consumes only that candidate;
5. all terminal consumers validate the one `ProverResult`; and
6. committed-history `qed` syntax has one owner, including compound closers and
   a narrowly validated undo-restored-close occurrence.

## Permanent regression gates

- no tree result or tracker field named `proved`;
- no `run_tree_prover.last_*` semantic handoff;
- manager `qed` admission and lifecycle status tests;
- candidate hash/event/source drift tests;
- compound `TAC. qed.` plus rejected-extra-`qed`/undo test;
- report and metrics tests that require the canonical result artifact; and
- full repository regression before another managed efficacy experiment.
