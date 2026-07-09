# scripts/

- `run_queue.sh` — strictly-sequential prover run queue for ONE worktree
  (usage in its 35-line header; replaces the pgrep-deadlock-prone chain
  launchers).
- `public_export/` — open-source export machinery: fail-closed
  PUBLIC/PRIVATE labels over every tracked file, scrubbing build, and a
  leak verifier. See `public_export/README.md`.
