# Changelog

Notable changes to Shannon Prover, newest first. Each public release from
0.2.0 on is tagged `vX.Y.Z`. Earlier releases are listed by date and tagged
together as `v0.1.0`.

## 0.3.1 (2026-10-28)

- Installing Shannon Prover no longer installs litellm, anthropic, openai
  and pexpect. Nothing imported them: the agents run through the Codex and
  Claude command-line tools. The locked environment is now pytest and its
  dependencies, about 7 MB instead of about 120 MB.
- A single-lemma proof is no longer reported verified when EasyCrypt accepts
  it without checking a goal. The guard used to match only a literal
  `admit.`, so `admit; trivial.`, `by (admit).`, `try admit; done.`, the
  `admitted` proof end, `exit.`, `abort.` or `pragma reset.` followed by a
  restated lemma, and `pragma Proofs:weak` or `Proofs:report` followed by
  `smt()` all passed with a "proof" of `false`. The guard now reads text as
  EasyCrypt's lexer does, so comments, string literals and operators such
  as `(*)` cannot hide these. Write-back rejects each of them, a file with
  `exit` or such a pragma stops the run with an explanation, a proof left
  open at the end of a file no longer counts as already proved, and
  verification deletes a `.eco` cache next to the checked file, since
  EasyCrypt skips checking a file whose cache it accepts.
- A project-level run is no longer reported `proved` when the target uses
  one of those constructs. Its final check matched only a literal `admit.`;
  it now rejects every form above anywhere in the target, and auxiliary
  lemma imports and finished auxiliary jobs apply the same rule.
- A project-level run is no longer reported `proved` when, by its end, a
  tracked file other than the target differs from the starting commit, a new
  unignored file exists outside the run artifacts, or the managed EasyCrypt
  toolchain changed. The overall agent can write the whole checkout, so the
  final check could otherwise run a modified verifier or dependency. The
  manifest lists such changes as `checkout_integrity_violations`.
- Proof verification and why3server reuse now accept only a why3server
  socket owned by your own account. The sockets live at predictable `/tmp`
  paths, so on a shared machine another account could have answered every
  SMT call as proved.
- The backend `session_cli -verify` check now fails when EasyCrypt exits
  with an error, is killed, runs past ten minutes, or leaves the proof open.
  It used to pass whenever the output contained no `[error` line.
- SECURITY.md now states what each agent can do on your machine. It used to
  say that the agent tools' own configuration and sandbox settings govern
  their access, but Shannon ignores your Codex configuration and rules,
  never asks for approval, and runs the project-level overall agent without
  a sandbox.
- A single-lemma run or the demo suite no longer blocks a later
  project-level run. Both wrote run bundles to a new, untracked
  `agent_view_runs/` directory, and a project-level run refuses a checkout
  with untracked files. Shannon now marks a bundle directory it creates as
  ignored by Git.
- The suite example in `eval_suite/README.md` now runs; it lacked the
  target `id` and named the output key `output_root` instead of
  `output_dir`.
- The public tree no longer includes a research campaign suite that named
  unreleased profiles and stopped with `ModuleNotFoundError`, or the
  scheduler that only that suite used. A missing research package now
  reports an unknown profile.
- The documented first run now works. The bundled examples already contain
  their proofs, so `$prove PIR_correct` only reports that the lemma is
  verified; the README and the `$prove` skill now point a first run at the
  PIR demo suite, which proves a proof-stripped copy, and the skip message
  says how to try the prover on a proved lemma.
- Choosing another model, corrected from the 0.3.0 note: `$prove` and
  `/prove` take only a lemma name, so run the orchestrator command they use
  with a different `--prover-model`. `/prove` uses `claude-opus-4-8` unless
  a model is named. Project-level models are set in
  `workflow/interleaved/agent_profiles.json`.
- The README and the project-level guide now give the sign-in steps, say
  that project-level runs accept only a ChatGPT or Claude account login,
  describe what the overall agent can access, and say that the bootstrap
  needs network access and a Git clone. They also give rough durations.
- The public compiler design document no longer points at a tag that
  exists only in the private repository, and the public export now rejects
  such tag names.

## 0.3.0 (2026-10-27)

- Concurrent proof nodes in one checkout no longer lose compiler help at
  random. Every native EasyCrypt query first runs `dune build` in the shared
  companion directory, and dune refuses to start while another instance is
  running there, so the query failed and the compiler silently skipped that
  turn. Companion builds now take turns through a file lock.
- The compiler no longer fails when the agent submits a tactic after the
  proof is already closed. A failed tactic there still made recovery
  features ask EasyCrypt for a diagnosis, which EasyCrypt refuses without an
  open goal; the planner now records a typed abstention instead. The agent
  sees the same turn as before.
- Compound-tactic diagnosis no longer fails when the agent's tactic clashes
  with an existing name (`move=> H` when `H` exists) or clears a hypothesis
  that is still used. EasyCrypt reports these outside its ordinary tactic
  errors; they escaped the native adapter and failed the whole native batch.
  They are now diagnosed with EasyCrypt's own message. The same holds for
  the intro-pattern, PHL-transitivity and eager-while recognizers, which run
  the agent's tactic themselves: a nested `move=> [H [a b]]` whose `H`
  already existed, or an `eager while` invariant that does not type, failed
  the batch there too.
- Native diagnoses now carry EasyCrypt's message for typing errors, alias
  clashes and failed `apply` instances instead of the OCaml exception name,
  such as `EcLib.EcTyping.TyError(_, _, _)`. A compound-tactic diagnosis
  quotes this message to the agent when part of the tactic succeeded.
- An attempted `call` whose native diagnosis ends in an internal EasyCrypt
  assertion is reported as undiagnosed. It used to be labelled a
  call-applicability failure, which the transport rejects, so the whole
  native batch failed and the compiler skipped that turn.
- The typed-state projection accepts `() <- e`, the empty tuple target that
  `inline *` produces when a unit argument meets a procedure declared
  without parameters. Such states used to lose their native projection.
- Native semantic protocol schema 20. Each compiler feature that explains a
  failed tactic now brings its own EasyCrypt realizer, and the compiler asks
  EasyCrypt to run only the realizers of the features it enables, so a disabled
  feature does no native work. What the agent sees is unchanged.
- Compound-tactic diagnoses quote the accepted prefix once in their
  explanation instead of up to five times. Long compound tactics, as Opus
  5.5 writes them, pushed 15 of 50 recorded diagnoses past the 700-byte
  delivery budget, so the agent never saw them; now only those with the
  longest prefixes still exceed it.
- Arms that never show compiler output (L1 and hidden audits) get a prompt
  that does not mention a compiler, and a suite can give each arm's output
  directory a neutral name, since the agent sees paths under it. The
  production treatment's prompt is unchanged.
- Eval suites can give every arm the manager-owned source navigation tools
  (`source_navigation: true`); each arm is bound to its own proof-stripped
  source copy before any model starts. Suites previously never enabled them.
- Claude workers survive a safety-classifier retry. The note the CLI
  injects before retrying counted as a protocol violation, which killed the
  worker and restarted it with a fresh context.
- Claude eval workers run without built-in tools or slash commands; with
  CLI 2.1.311, calling one was a capability violation that killed the worker.
  Models with a 1M-token context window swap context at 400k tokens instead
  of 140k, and a worker that exits with an error writes the reason to its
  stderr log.
- The Codex backend now defaults to `gpt-6-astra` instead of `gpt-5.6-sol`,
  still with high reasoning effort. Runs that name a model are unchanged; if
  your account cannot use GPT-6, select an available model with
  `--prover-model` or the suite `model` setting.

## 0.2.0 (2026-09-30)

- Keep Why3 solver configuration inside the managed toolchain. Runtime checks
  are read-only, and `--configure-solvers` refreshes configuration without
  rebuilding EasyCrypt or replacing the user's global settings.
- Make production runtime and compiler feature tests runnable in the public
  source tree; retain research configuration and campaign tests privately.
- Document system build dependencies, solver installation and migration for
  existing installations; refresh solver configuration explicitly in CI.
- Clarify that both project-level agents default to Codex, and add a reading
  guide to the compiler design.
- Install the pinned SMT solvers in CI through one shared action, and rebuild
  the cached EasyCrypt toolchain whenever the bootstrap script changes.

## 2026-09-29

- Serve the website from the `gh-pages` branch. The recorded run bundles it
  displays no longer live in the main branch, which shrinks a checkout from
  about 17,000 files to about 1,000.
- Publish the test suite and add continuous integration; document the SMT
  solvers EasyCrypt needs.
- Add contribution guidelines, a security policy, a code of conduct, and this
  changelog.

## 2026-09-28

- Unknown lemma names: when a lemma name written by the agent does not
  resolve, EasyCrypt looks for declarations with the same last name
  component and checks them at the current goal. If exactly one of them makes
  progress, the agent gets a checked "Do you mean?" suggestion.
- Operation-binding feedback no longer states facts EasyCrypt has not
  established. This covers the argument-layout diagnostic, the "no completed
  instance" diagnostic, implicit arguments, and definitions that unfold into
  further arguments.
- Native semantic protocol schema 19.
- Claude Code system notices are accepted at any point of a turn.

## 2026-09-10

- Dilithium and ChaChaPoly proof narratives on the website.
- Fixes to the shared handoff between the overall and auxiliary-lemma agents.

## 2026-09-09

- Proof case studies on the website.
- OpenAI Codex with `gpt-6-astra` as the default for both project-level
  roles.

## 2026-09-05

- Project-level (interleaved) proving: Shannon proposes and revises the proof
  decomposition as well as proving the individual lemmas.
- Updated website and auxiliary-lemma agent workflow.

## 2026-08-19

- Lighter runtime structure, a production boundary that ships only the
  treatment configuration, and a live-verified public demo.

## 2026-08-16

- Proof-state compiler v2.

## 2026-07-09 – 2026-07-20

- Initial public release (0.1.0), benchmark browser, and project website.
