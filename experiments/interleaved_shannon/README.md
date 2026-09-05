# ChaChaPoly: project-level proving with Shannon Prover

This example asks Shannon to construct an EasyCrypt proof of the supplied
ChaChaPoly security theorem. The starting files contain the security model,
supporting declarations, and the final theorem `conclusion`, with its proof
unfinished. They do not supply a decomposition of that theorem into
auxiliary lemmas.

For your own scheme or theorem, use the
[general interleaved guide](../../workflow/interleaved/README.md).
This directory is a fixed reference task with additional checks for
reproducible experiments.

## What is included?

- [`task/chacha_poly.ec`](task/chacha_poly.ec): the model and target theorem.
- [`task/ske.ec`](task/ske.ec) and
  [`task/indistinguishability.eca`](task/indistinguishability.eca):
  supporting definitions.
- [`project.json`](project.json): target, time limits, and file locations.
- [`prompt.md`](prompt.md): the instructions given to the overall proof agent.
- [`verify_task.py`](verify_task.py): checks that the supplied problem has
  been preserved and that the final proof passes EasyCrypt.

The reusable prover is in `workflow/interleaved/`. This example supplies
a task and its evaluation rules.

## Prepare a run

Complete the [installation](../../README.md#install) first. Commit any changes
you want included, then run this command from the repository root:

```bash
experiments/interleaved_shannon/prepare_workspace.sh HEAD
```

It creates a separate checkout at the selected commit and prints
`workspace ready: ...`. Change into that directory. The preparation removes
known answer-bearing examples and unrelated research material from that
checkout and checks that the starting task loads.

Run the checks without starting a proof-generating model:

```bash
experiments/interleaved_shannon/run.sh --preflight-only
```

Then start the attempt:

```bash
experiments/interleaved_shannon/run.sh
```

The default is Claude Code for the overall argument and Codex for auxiliary
lemmas. Both CLIs need the stored OAuth logins described in the
[agent setup guide](../../workflow/interleaved/README.md#choose-the-agents-and-limits).
To use a different pair, add explicit flags to both the preflight and live
commands. For example:

```bash
experiments/interleaved_shannon/run.sh \
  --outer-provider codex --inner-provider codex \
  --preflight-only
```

The supplied task allows a 12-hour overall attempt, at most two simultaneous
auxiliary-lemma attempts, and up to 120 minutes per auxiliary attempt. The
exact model settings and additional provider limits are in
[`agent_profiles.json`](../../workflow/interleaved/agent_profiles.json).
These time limits are not a combined spending cap.

## What is checked?

Shannon may add auxiliary declarations in the designated scratchpad and work
on the final theorem's proof. The final checker compares the protected
regions and supporting files with the starting commit, rejects forbidden
declarations and unfinished proofs, and checks the complete file using
EasyCrypt `r2026.06`.

The example also limits access to existing answers. Individual lemma agents
receive a prepared source copy with the target proof removed. The overall
agent receives explicit source-access restrictions and a checkout excluding
known answer-bearing trees. This setup is an auditable protocol for agents
following those restrictions; it is not an adversarial operating-system
sandbox.

Preflight exercises source access and partial-proof transfer with the real
EasyCrypt backend, without launching a proof-generating model. Passing those
checks demonstrates that the setup works, not that Shannon can prove the
theorem.

## Results and continuations

Results are written to
`artifacts/interleaved_shannon/official_TIMESTAMP/`.
The manifest records the selected models, limits, elapsed time, and outcome.
A verified final theorem requires `status: "proved"` and
`final_verification_passed: true` in `manifest.json`; the checking details
are in `final_verification.json`.

If final verification fails, the runner saves `partial_candidate.ec`.
After reviewing and committing a loadable checkpoint, continue from a clean
checkout with:

```bash
experiments/interleaved_shannon/run.sh \
  --continuation-of artifacts/interleaved_shannon/official_TIMESTAMP \
  --continuation-candidate \
    artifacts/interleaved_shannon/official_TIMESTAMP/partial_candidate.ec
```

The continuation inherits the previous providers unless a change is
explicitly requested with `--allow-provider-change`. It records the previous
attempt and can reuse compatible saved lemma progress. Report all segments
and any intervention when describing a result.

For a shorter observation, `--timeout-seconds` changes the external stop
timer. The reference instructions still describe a 12-hour task; a shortened
run therefore observes the beginning of that task rather than a separately
designed short-budget experiment.

A successful run demonstrates a proof for this task and configuration.
It does not establish success on arbitrary security theorems or a speed
advantage over other approaches. The current proof browser displays
individual lemma attempts, not the full interleaved argument.

See the [technical architecture](../../docs/architecture/interleaved_shannon.md)
for details of partial proofs, delegation, and final checking.
