# Changelog

Notable changes to Shannon Prover, newest first. Each public release from
0.2.0 on is tagged `vX.Y.Z`. Earlier releases are listed by date and tagged
together as `v0.1.0`.

## 0.3.2 (2026-11-01)

- LICENSE and README now say that the vendored EasyCrypt's inifiles library
  is licensed under the LGPL 2.1, whose text ships in `licenses/`.
- Tests are grouped by subsystem under `tests/public/` (`core`, `compiler`,
  `workflow`, `eval`, `repo`), with shared builders and fakes in
  `tests/helpers/`. Run a test through pytest; test modules no longer set
  up `sys.path` themselves. CONTRIBUTING.md says where a new test goes.
  Tests that need the EasyCrypt toolchain carry the `easycrypt` marker, so
  `pytest -m "not easycrypt"` runs the rest without the toolchain.
- Test fixtures, helpers and comments use synthetic identifiers, and a
  ChaChaPoly fixture keeps only the fields its test reads.
- `$prove` and `/prove` no longer replace an existing proof that fails to
  verify with `admit`. The source file changes only when a verified proof
  is written back. Write-back now checks a hidden copy next to the file and
  moves it into place only after it passes, so an interrupted run never
  leaves an unverified proof behind, and an edit made during the check is
  kept.
- The single-lemma precheck runs once the run's why3server is up and
  ignores declarations in comments and strings. When EasyCrypt gives no
  verdict on an existing proof (a why3server failure or a timeout), the run
  stops as `infrastructure_invalid` instead of searching for a lemma that
  may already be proved. A missing lemma or file is reported without
  starting a search, `equiv`, `hoare` and `phoare` targets are recognised,
  and a target without its own `qed.` is no longer reported as verified on
  the strength of the next lemma's proof.
- Tactics are committed exactly as submitted. A clean-up meant for shell
  output cut `elim: s => [|head tail ih].` down to `elim: s => [.` and
  turned `/\!` into `!`.
- After a daemon timeout, an EasyCrypt exit or an out-of-step pipe, the
  session is replaced and replayed from its committed history. Every later
  reply used to arrive one command late, so the agent could see a goal that
  did not match its history, or have a valid tactic rejected. A failed
  session open, a close during a running request, and a failed rollback
  after a rejection no longer leave a session inconsistent.
- Batch EasyCrypt runs stop after 600 s, and an EasyCrypt process the
  manager timed out can no longer overwrite the session's output files.
- A compound tactic with a space before `;` (`wp ; transitivity y.`) no
  longer silences the compiler for that turn.
- A node whose compiler changes the proof session stops as
  `compiler_read_only_violation` instead of serving inconsistent state.
- A node restored from a resume capsule gets its route history back, and
  for the same node id its pre-rewind restore point. Both were silently
  dropped, so capsule history shrank with each generation.
- Restart, rewind, restore and amend turns report `accepted` and
  `changed`; a replay that stops part way reports `partial_success` and the
  step where it stopped.
- `finish` while goals are open is accepted as a give-up even after an
  `admit.` was committed. `qed`, and `finish` once the goals are closed, are
  still refused while an `admit.` remains.
- Tree search: a child branch that fails to start no longer ends the whole
  run. A failed or interrupted start, or an error in the supervisor loop,
  reaps the workers already started and still archives the session
  directories, resume capsules and partial prefix. A healthy node is no
  longer killed to make room at capacity, a node that just exited no
  longer makes the capacity loop spin, a failed Layer-3 capsule selection
  is not retried every second, the winner's final output is no longer
  truncated, no worker is left running at the end, and worker output lines
  that arrive together are handled in one poll.
- A worker that receives SIGTERM or SIGINT no longer deadlocks before
  writing its safe-stop checkpoint.
- Two runs of the same lemma started in the same minute get separate run
  directories and no longer shut down each other's EasyCrypt daemon.
- Eval metrics no longer count a reverted no-op commit, a premature `qed.`
  the manager never ran, or a commit without an execution result as an
  accepted commit. Recorded no-op commits already carried an error, which
  earlier versions counted as a failure, so accepted-commit counts and
  rejection rates computed from recorded runs do not change. Blind-retry
  runs are counted per node, and `final_proof_length` is now the tactic
  count of the verified proof, including a prefix replayed from a resume
  capsule; for resumed runs it is larger than before.
- An interrupted or failed eval suite marks its manifest `interrupted` or
  `failed`, and an `output_dir` outside the working directory no longer
  stops the suite.
- `-verify` recognises a session proof that ends with `TAC. qed.`, and
  `commit_chain` reports the EasyCrypt error of the step that failed.
- `orchestrator --human-proof-dir` is removed; `--max-iterations` is kept
  for compatibility and documented as ignored.
- One EasyCrypt text layer now splits sentences, masks comments and strings,
  reads prompts and finds a lemma's declaration and proof for every caller.
  The copies it replaced disagreed. As a result:
  - `[1 .. 2]` is no longer cut at `..`.
  - Write-back can no longer overwrite the `equiv` declaration that follows
    the target.
  - A commented-out lemma or a clone override is no longer taken for the
    target.
  - Opening a target proved by a one-line `by` no longer produces a file
    EasyCrypt rejects.
  - The extracted-lemma check no longer admits the target's own `by smt(...)`,
    which let the precheck report a lemma as verified without running its
    proof; it also refuses a target whose proof is never closed.
- A tactic whose text looks like a backend flag is no longer misread as one
  when the manager classifies its own backend calls.
- A rewind, restore or amend late in a long proof no longer makes the node
  unhealthy. The turn budget was fixed at launch from the starting history,
  while such a turn replays the whole current history. The budget now
  covers the longest history a node can reach, and Claude receives the same
  tool timeout as Codex instead of its 30-minute default. Setting
  `SHANNON_REPLAY_AGG_BUDGET` to 0 or less no longer shrinks every turn to
  600 s.
- A proof node now watches its own manager. A turn that spends 300 s
  outside any EasyCrypt call, a call that runs 30 s past its own timeout,
  or a dead tool endpoint is recorded as `manager_turn.stalled`, with thread
  stacks, in the manager audit log. `SHANNON_MANAGER_STALL_WATCHDOG` selects
  `report` (the default: record only), `enforce` (the node exits with code
  75 and the tree search respawns it from its last checkpoint) or `off`.
  Such a hang used to keep the node blocked until the run ended.
- Rewind, restore and amend no longer restart EasyCrypt and replay the
  whole kept history: the persistent daemon backtracks with EasyCrypt's
  `undo`, and restore and amend replay only the part that differs. A
  rejected or no-progress commit and `undo_last_step` also keep the daemon
  session instead of rebuilding it. Rewinding a 90-command proof by a few
  steps takes about 0.2 s instead of 10 s, and a commit after a rejection
  about 0.2 s instead of 3 s. A history containing a `pragma`, a rewind into
  a multi-command commit or onto a closed proof, and any mismatch fall back
  to the old restart and replay. The kept prefix is no longer re-checked,
  rewinds no longer emit per-step `replay_prefix_step_*` actions, and the
  tree search now counts a rewind like an undo when it measures progress.
- A tactic that EasyCrypt needs more than 60 s for no longer gets stuck.
  The daemon gave each committed or replayed transaction 60 s, while the
  manager gives a commit call 180 s; past 60 s the commit fell back to batch,
  which ran the slow tactic twice, and once it was in the history every
  later commit ran past 180 s. The daemon's limit is now the manager's
  budget less 10 s (170 s, `SHANNON_EC_STEP_TIMEOUT`), for replays too, and
  a transaction that runs past it is rejected on the daemon with
  `EasyCrypt did not finish this transaction within 170 s` instead of
  falling back to batch. A daemon started by an older version ignores the
  new limit and falls back as before.
- A daemon attempt that is known to fail is no longer repeated on every
  commit. When the daemon cannot be spawned (each attempt waited 10 s), the
  session does not try again for 5 minutes. When a committed transaction
  does not replay on the daemon, the session skips the daemon for 10 minutes
  while the history still starts with that transaction; when EasyCrypt
  rejects the lemma's context, for 10 minutes while the source file is
  unchanged. Those
  commits run in batch as before, with `negative cache: <reason>` in the
  `ec.routing` detail; each new entry is recorded once as an
  `ec.daemon_unavailable` event, and `-start` clears them.
- A commit that runs in batch runs EasyCrypt once instead of twice. The
  first run only rebuilt the state before the commit, which the session
  already keeps; goal counts and no-op detection now read that state, as
  daemon commits always did, with the same results. A reverted no-op in
  batch now leaves the compressed state in `current.out`, as on the daemon,
  instead of the whole replay.
- A manager backend call that times out no longer leaves EasyCrypt running.
  Only `session_cli` itself was killed, and the `easycrypt` it had started
  for a batch commit kept the CPU until it finished. `session_cli` now runs
  in a process group of its own, which is stopped as a whole on a timeout or
  an interrupt; the daemon, which detaches, is not affected.
- A supervisor that has to SIGKILL an orchestrator now also stops the run's
  EasyCrypt daemon. The daemon runs in a session of its own, so reaping the
  recorded process groups missed it; the orchestrator now names the run's
  daemon socket in the worker manifest, and reaping stops the daemon that
  still serves it.
- Project-level runs:
  - Cross-run `--resume-job` works for projects whose `artifact_root` is
    not the ChaChaPoly reference's, and a broken continuation chain no
    longer crashes the runner.
  - The runner handles SIGTERM and SIGHUP like Ctrl-C: it stops the
    overall agent, cancels jobs, runs the final check and writes the
    verdict.
  - Each run directory has a manifest from the start (`preflight_running`,
    `running`, `preflight_failed`, `runner_failed`). A missing or signed-out
    provider is reported before the EasyCrypt source preflight, and the
    Claude preflight checks that the CLI accepts `--max-turns`.
  - `proved` is refused when a job ran from a commit that differs from the
    starting commit outside the target.
  - Killed or crashed jobs end as `infrastructure_invalid`, and their lanes
    (worktree and EasyCrypt daemon) are removed. A reused process id is no
    longer mistaken for a worker, and worker heartbeats continue while
    results are collected.
  - Sessions receive the library include directory, resources resolve
    against every include directory, and lanes check them out. A project
    with more than one library include directory is rejected for now.
  - Auxiliary jobs of the ChaChaPoly reference project start again. Their
    lanes did not check out the project file, so every job failed at start.
  - The project is passed explicitly from each entry point instead of being
    read from an environment variable when modules are imported, job states
    follow an explicit transition table, a closed job is no longer rewritten
    by its worker, and a cancel request is no longer lost.

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
