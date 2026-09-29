# Changelog

Notable changes to Shannon Prover, newest first. Starting with the next
release, each public release is tagged with a version number.

## Unreleased

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
