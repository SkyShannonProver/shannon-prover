# Narrative Eval Contract

This contract separates the semantic proof-story layer from executable proof
construction for paper-facing eval runs.

## Responsibility Boundary

`workflow/tools/narrative_annotator.py`

- Owns offline semantic annotation of a target `.ec` file.
- Default input is proof-stripped source: every proof body is replaced by
  `admit.` before the model sees the file.
- May describe file purpose, game chain, lemma roles, semantic deltas, glossary,
  and statement-derived bridge signatures.
- Must not output proof-body-derived tactic tails, invariant sketches, call
  templates, or proof scripts.
- Writes provenance that records input mode, raw source hash, proof-stripped
  input hash, annotator input hash, model, and annotator version.

`workflow/agents/proof_planner.py`

- Owns prompt injection of narratives.
- In eval mode, loads only narratives whose provenance proves
  `input_mode=proof_stripped` and whose proof-stripped hash matches the current
  source file.
- Rejects legacy/no-provenance/raw-source/stale narratives completely.
- Sanitizes target-lemma entries before prompt injection: only structural
  fields such as `name`, `role`, and `hop` remain.

`core/easycrypt/session_runtime.py`

- Owns runtime access to sibling narrative JSON for backend hooks.
- Enforces the same eval provenance gate as the planner so hooks cannot use a
  tainted narrative that the prompt layer refused.
- Returns an empty narrative to hooks when provenance is missing, raw, or stale.

Manager-owned proof compilers and EasyCrypt daemon checks

- Own executable route construction.
- May use clean statement-derived bridge metadata as input, but any tactic or
  chain surfaced to the agent must be verified against the current live proof
  state.
- Narrative text is never proof authority.

## Allowed Annotator Input In Strict Eval

- Target `.ec` source after proof stripping.
- Module declarations, clone/include structure, type signatures, op
  definitions, lemma/equiv/hoare/phoare statements, names, and imports.
- Sibling lemma statements visible in the same stripped source.
- Clone obligation names and declarations after their proof bodies or
  `by ...` realizations have been redacted.

## Forbidden Annotator Input In Strict Eval

- Human proof bodies for the target lemma or sibling lemmas.
- Clone realization proof bodies, including `realize ... by ...`, `proof X by
  ...`, and `realize X. proof. ... qed.` text.
- Existing session traces, proof-bank entries, old agent reports, timeline
  payloads, or stale session directories.
- Raw `.ec` source with completed proofs.

## Forbidden Narrative Fields In Eval-Clean Output

The annotator prompt forbids these fields, and eval sanitization removes them
if legacy JSON still contains them:

- `closer_hints`
- `typical_tail`
- `closing_tail`
- `call_template`
- `invariant_sketch`
- `proof_script`
- `proof_sketch`
- `tactic`
- `tactics`
- `script`

For the target lemma entry, eval sanitization also removes free-text and
route-like fields such as `narrative`, `semantic_delta`, `rewrite_form`, and
`arg_types`.

## Raw Narrative Policy

Raw-source narratives remain useful for research/debugging, but they must be
marked with `input_mode=raw_source`. Strict eval loaders reject them.
