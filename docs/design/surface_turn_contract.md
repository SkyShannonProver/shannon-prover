# Surface Turn Presentation Contract

This document fixes the presentation boundary for the prover agent and the
human playground.  It is about what a turn *shows*, not how EasyCrypt proof
state is mutated.

## Pipeline

The canonical presentation route is:

```text
raw ProverWorkspaceView facts
  -> SurfaceModel
  -> SurfaceTurnModel
  -> agent markdown / human web card
```

`SurfaceModel` describes the current proof state: goal, primary proof panel,
status, and available actions.

`SurfaceTurnModel` describes one manager turn: the stable proof surface, an
optional read-only overlay, an optional typed control menu, the outcome line,
and whether the base proof surface should update.

Renderers consume these models.  They must not re-decide which raw workspace
panels are visible.

## Agent Contract

The agent reads markdown.  It has no visual navigation state.

For a proof-state-changing turn, the markdown renders the current proof surface
and the turn outcome in the order requested by `TurnOutcome.lead_before_goal`.

For a read-only turn such as `tactic_forms`, `operator_lemmas`, or
`lookup_symbol`, the markdown renders:

1. The returned read-only content.
2. `Continue from unchanged proof state`.
3. The unchanged proof surface and its original actions.

The agent does not need and must not receive a `back` intent.  Its next action
is just another normal proof intent submitted from the unchanged proof state.

For a control-menu turn such as bare `undo_to_checkpoint`, bare
`fresh_restart`, or a blocked `finish`, the markdown renders the typed menu plus
the unchanged proof surface.  The menu items already contain ready-to-submit
intent/payload objects.

## Human Playground Contract

The human web card is a visual rendering of the same `SurfaceTurnModel`, with
one extra UI affordance: local navigation.

Every WebSocket `view` message rendered by the card must contain
`surface_turn.proof_surface`.  The card does not synthesize a turn from legacy
`surface_model` data.  A missing `surface_turn` is a contract violation,
usually meaning the browser is talking to an old playground server process that
must be restarted.

The WebSocket presentation payload has exactly one rendered-surface contract:
`surface_turn`.  The raw `workspace_view` remains available only for the audit
tab.  The server does not send a top-level `surface_model` compatibility field.

For a normal proof-state turn, the card renders `proof_surface`.

For a read-only turn, the card renders:

1. A visible overlay/drawer for `overlay_surface`.
2. The unchanged `proof_surface` underneath.
3. A persistent `Back to proof menu` button in the right panel header while the
   overlay is open.

For a control-menu turn, the card renders:

1. A left-side proof-control menu from `control_menu`.
2. The unchanged `proof_surface` in the right panel.

The control menu is anchored to the proof controls because it is a choice of the
next submitted proof-control intent, not context content about the goal.  Its
items already contain exact ready-to-submit intent/payload objects.

`Back to proof menu` for read-only overlays, and closing the left control menu,
are local browser state only:

- It does not send a WebSocket message.
- It does not submit an MCP/prover intent.
- It does not mutate EasyCrypt state.
- It only hides the overlay or menu and re-renders the already-present
  `proof_surface`.

When a new read-only overlay opens, the web card should scroll the right proof
panel to the top so the drawer and header affordance are visible immediately.
The header button is the reliability guard: even if the drawer body is long or
the user is scrolled, returning to the proof menu remains discoverable.

## Ownership

- `context_intents.py` owns intent taxonomy.
- `surface_profiles.py` gates profile-visible capabilities.
- `surface_composer.py` composes proof-state `SurfaceModel`.
- `surface_turn_model.py` composes and renders turn-level presentation.
- The web UI renders `SurfaceTurnModel`; it does not parse raw manager result
  text to infer menus or base-state updates.
- The web UI renders panel facts exactly as `SurfaceModel` provides them.  It
  may choose visual placement for `overlay_surface` and `control_menu`, but it
  must not hide or promote individual facts by key.
- The web UI does not keep a compatibility base surface cache and does not
  promote a raw `surface_model` into `SurfaceTurnModel`.

Legacy `inspect_context` may remain accepted for replay/back-compat, but it is
not emitted by `SurfaceModel`, `SurfaceTurnModel`, markdown, or web actions.

Probe affordances are hidden by default upstream.  The web UI must not repair
probe wording by text scrubbing.
