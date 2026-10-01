# Contributing to Shannon Prover

Thank you for your interest in Shannon Prover. Bug reports, questions,
documentation fixes, EasyCrypt compatibility reports, and code contributions
are all welcome.

## Ways to contribute

- **Report a bug or ask a question.** Open a GitHub issue. Please include your
  operating system, the command you ran, the EasyCrypt receipt printed by
  `uv run python tools/bootstrap_easycrypt.py --verify-only`, and the relevant
  output. Remove API keys, tokens, and private file paths before posting.
- **Improve the documentation.** Small fixes can go straight into a pull
  request.
- **Change the code.** For anything beyond a small fix, please open an issue
  first so that we can agree on the approach before you invest time in it.

Security problems should not be reported in public issues; see
[SECURITY.md](SECURITY.md).

## How pull requests are merged

This repository is published from the maintainers' development repository,
which also holds unpublished benchmarks and experiments. Each public commit is
a release snapshot, so pull requests are not merged here directly:

1. A maintainer reviews your pull request here.
2. An accepted change is applied in the development repository, keeping you
   as a co-author (`Co-authored-by:` trailer).
3. The change appears in the next public release, and the pull request is
   closed with a link to that release.

## Development setup

Use macOS or Linux with Git, [opam](https://opam.ocaml.org), Python ≥ 3.12,
and [uv](https://docs.astral.sh/uv/). Follow the
[installation instructions](README.md#install), including the solver setup,
before running the checks below. The bootstrap builds the pinned EasyCrypt
release in a repository-local opam root and uses a local Why3 configuration.
It preserves your existing global configuration.

```bash
uv sync
uv run python tools/bootstrap_easycrypt.py --verify-only
```

After changing installed solvers, run
`uv run python tools/bootstrap_easycrypt.py --configure-solvers` to refresh
their registration. Existing installations need this once to create the local
configuration.

Before opening a pull request, run the test suite, check that the demo still
plans correctly without calling a model, and check for whitespace errors:

```bash
uv run python -m pytest -q tests
uv run python -m eval_suite.run --suite eval_suite/suites/demo_pir.json --dry-run
git diff --check
```

CI runs the same commands on every pull request. A few tests that depend on
unpublished research material run only in the maintainers' repository, and
maintainers run them before accepting a change.

## Design principles

A few rules shape almost every change; [AGENTS.md](AGENTS.md) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) describe them in detail.

- **EasyCrypt is the authority on proof semantics.** A proof counts only after
  a fresh EasyCrypt check. Do not re-implement EasyCrypt reasoning in Python.
- **Feedback to the agent must be true.** A compiler feature that cannot
  establish a fact stays silent rather than guessing.
- **Fail closed.** Missing, incomplete, or inconsistent evidence leads to no
  action, not to a best-effort one.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE), the same license as the project.
