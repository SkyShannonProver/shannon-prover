# Documentation Index

This directory is the maintained documentation home for Shannon Prover. Root
files stay small and operational; longer concepts and references live here.

## Start Here

- [Project README](../README.md) -- architecture overview, directory map, and
  current proof-agent vocabulary.
- [Testing guide](../TESTING.md) -- replay, eval-mode, A/B, and long-run
  testing patterns.
- [Agent instructions](../AGENTS.md) -- canonical runtime contract for Codex
  and prover-agent work.

## Concepts

- [Hypothesis-driven proving](concepts/hypothesis_driven_proving.md) -- the map,
  navigator, workbench, surgery-table, preview, route-health, and phase-door
  model.
- [Paper eval interface ladder](concepts/eval_interface_ladder.md) -- how the
  raw-CLI, signpost, navigator, preview, and full-system ablations map to the
  proof-state compiler story.

## Architecture And Contracts

- [Workflow design](../workflow/DESIGN.md) -- managed proof-node architecture,
  orchestration, data flow, and agent phases.
- [Validation and replay](../workflow/validation/README.md) -- event logs,
  ToolView, ProofContextView, ProverWorkspaceView, CommitResponse, acceptance,
  replay, and audits.
- [Analysis compiler layer](../core/easycrypt/analysis/README.md) -- ProofIR,
  canonical frontends, resource layers, planners, and action rendering.
- [Knowledge base design](../knowledge/base/DESIGN.md) -- KB policy, stores,
  retrieval flow, schema notes, and validation.

## Reference

- [EasyCrypt tools](../core/easycrypt/TOOLS.md) -- backend flags, ToolViews,
  semantic inspect topics, hooks, daemon infrastructure, and tool catalog.
- [Hook registry](reference/hook_registry.md) -- commit/search hook lifecycle,
  layer ordering, persistence files, and debugging.
- [Lemma authoring rules](../core/easycrypt/analysis/LEMMA_AUTHORING.md) --
  how to write compiler-friendly EasyCrypt lemmas.
- [Analysis contracts](../core/easycrypt/analysis/CONTRACTS.md) and
  [schemas](../core/easycrypt/analysis/SCHEMAS.md) -- stable analysis-layer
  boundaries and fact shapes.
