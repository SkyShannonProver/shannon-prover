# eval — the local benchmark corpus (data only)

This directory holds **data**: the EasyCrypt example corpus the prover is
evaluated against. The runner lives in [`eval_suite/`](../eval_suite/), and
suite configuration JSONs live in [`eval_suite/suites/`](../eval_suite/suites/).

- `examples/` — target `.ec`/`.eca` files: single-file lemmas (PIR, PRG,
  Pedersen, SchnorrPK, Dice4_6, br93, elgamal, hashed ElGamal, WhileSample)
  and multi-file projects (`ChaChaPoly/`, `MEE-CBC/`, `cramer-shoup/`).
  These files contain complete reference proofs; eval-mode runs never show
  them to the prover — `eval_suite.run` copies the target per run and strips
  proofs to `admit.` (`strip_proofs`, on by default).
- `CLAUDE.md` — eval-mode leakage rules for agents working in this repo
  (what may and may not be read while a target lemma is being proved).

To run a target, see `eval_suite/README.md`; the shortest path is

```bash
uv run python -m eval_suite.run --suite eval_suite/suites/demo_pir.json \
    --profiles l4_checked_action_surface
```
