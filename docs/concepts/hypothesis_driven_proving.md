# Hypothesis-Driven Proving

Shannon Prover presents one current proof state through a typed surface rather
than exposing backend transport or a ranked proof plan.

## Current Route

```text
EasyCrypt snapshot
  -> ProverWorkspaceView (raw/audit facts)
  -> SurfaceModel (current proof-state presentation)
  -> SurfaceTurnModel (outcome, overlay, controls)
  -> agent markdown / human cards
```

The prover owns semantic proof choices. The compiler may surface mechanical
facts that are expensive to recover manually, such as an exact loaded theorem,
module bindings for a live call, checked statement coordinates, or the premises
of a matching distribution certificate. It must not choose an invariant, cut,
branch truth value, coupling, witness, or global proof architecture.

## What The Agent Sees

The normal agent-readable presentation is the markdown rendered from
`SurfaceTurnModel`. A human card renders the same typed turn model. Raw
workspace JSON, `candidate_moves`, and `decision_context` are audit/runtime
data; renderers do not infer visible content from them.

Read-only context requests return an overlay while retaining the unchanged base
proof surface. Humans close the overlay locally. The agent receives the result
followed by the unchanged proof surface and can submit another ordinary intent.
There is no public tactic-probe capability.

## Ownership

- The orchestrator owns tree/racing policy.
- `ProofNodeManager` owns the turn boundary and metadata binding.
- `ReplSessionManager` owns EasyCrypt lifecycle and mutation.
- analyzers produce typed mechanical facts;
- `surface_panels.py` adapts facts into panel facts;
- action policy, eligibility, and preflight own action visibility;
- `surface_composer.py` owns proof-surface selection and order;
- `surface_turn_model.py` owns turn outcome, overlay, and control menus;
- markdown and web renderers only render the typed turn contract;
- the prover owns proof strategy and tactic choice.

The canonical contracts are:

- [`docs/design/surface_turn_contract.md`](../design/surface_turn_contract.md)
- [`docs/design/surface_class_audit_protocol.md`](../design/surface_class_audit_protocol.md)

Historical reports may mention older navigator or probe experiments. They are
experiment records, not the current agent protocol.
