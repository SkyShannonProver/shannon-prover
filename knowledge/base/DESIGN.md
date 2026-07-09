# Knowledge Base Design

For the architecture overview and pipeline commands, see
[knowledge/README.md](../README.md).

## Policy

The KB stores reusable proof knowledge only. It must not contain concrete
lemma proof scripts, replay chains, or per-lemma examples that can be used as
retrieval shortcuts.

Allowed:
- Generic proof strategies and phase roadmaps
- Generic structural patterns with `<slot>` placeholders
- EasyCrypt tactic syntax and error recovery
- Decision-tree navigation and pitfalls
- Provenance metadata at the file/source level when it does not include proof
  scripts

Forbidden in `knowledge/base`:
- `sources/proof_bank.jsonl`
- `agent/goal_state_bank.jsonl`
- `sources/goal_state_descriptions.jsonl`
- `sources/human_proof_bank.jsonl`
- `examples[]`, `members[]`, `seen_in`, `chain_step`, `goal_state`,
  `next_state`, `instantiation_template`, `usage_pattern`, `proof_files`,
  or concrete `tactic` fields attached to a specific lemma

This is an authoring convention. The standalone lint that once enforced it
(`kb_no_exact_tactics`) has been removed; eval-mode leakage is now prevented at
query time by `search_guide.search()`, which self-redacts target-specific fields.

## Agent-Facing Stores

| Store | File | What agent does with it |
|---|---|---|
| Proof Guide | `agent/proof_guide.json` | Strategy layer: roadmaps, structural patterns, closer idioms, and syntax tips. |
| EC Tactics | `agent/ec_tactics.json` | Execution layer indexed by `(goal_type, tactic)`: syntax, pitfalls, diagnosis, and abandon rules. |
| Decision Tree | `agent/decision_tree.md` | Navigation layer for choosing proof approach and avoiding known traps. |

## Source Stores

| Store | File | Used by |
|---|---|---|
| Proof Tactics & Strategies | `sources/proof_tactics_and_strategies.jsonl` | Generic source records for proof guide strategies and syntax tips. |
| Goal State Categories | `sources/goal_state_categories.json` | Generic structural categories and tactic skeletons only. |

## Retrieval Flow

1. Read/search `agent/proof_guide.json` through `search_guide.py`.
2. Match the current goal to a strategy or structural pattern.
3. Use `slot_semantics`, `variants`, `typical_tactics`, and
   `reasoning_hints` as generic guidance.
4. Instantiate from the live session goal state. Count positions, derive
   bijections, and choose lemma hints from the target context.
5. Use `agent/ec_tactics.json` and `-diagnose` for tactic-form failures.

There is deliberately no fallback to a proof bank or stored per-lemma chain.

## Schema Notes

### `proof_guide.json`

Pattern body fields must be generic:
- `structural_description`
- `indicators`
- `slot_semantics`
- `variants`
- `typical_tactics`
- `common_failure`
- `fallback`
- `reasoning_hints`
- `smt_hints`

Every concrete object in these fields should be an EC stdlib name, a
single-letter schematic module name, or a `<slot>` placeholder defined in
`slot_semantics`.

Do not add `examples[]`, `slot_fills`, proof-file provenance, or tactic
templates. If an idea only makes sense for one lemma, generalize it before
putting it in the KB.

### `ec_tactics.json`

Per tactic entry:
- `syntax`: canonical tactic form
- `pitfalls[]`: cross-refs to decision-tree pitfalls
- `when_to_abandon`: when the tactic is a strategic mismatch
- `errors{}`: regex, diagnosis, fix, and `level`
- `smt_hints[]`: generic lemma names useful for residual goals

Error levels:
- `execution`: the tactic is conceptually right, but the form is wrong.
- `strategy`: the tactic does not fit the current goal; switch approach.

## Validation

The standalone KB lints (`kb_validator`, `kb_body_purity`,
`kb_no_exact_tactics`) have been removed. The invariants they checked are now
authoring conventions:

- **Body purity** — project-specific identifiers must not leak into generic
  pattern bodies.
- **No exact tactics** — proof-bank artifacts and per-lemma example fields must
  be absent from `knowledge/base`.

Eval-mode leakage is enforced at query time instead: `search_guide.search()`
self-redacts target-specific fields, so a KB entry that accidentally names the
target lemma is dropped from results rather than caught by a separate lint.

## Workflow Improvement Loop

1. The prover reports which generic patterns helped and what was missing.
2. The KB improver generalizes useful lessons into `proof_guide.json`,
   `ec_tactics.json`, or `decision_tree.md`.
3. Validators enforce reusable, example-free KB content.
4. Regression testing may use `workflow/proof_bank.jsonl`, which is outside
   `knowledge/base` and is not an agent-facing KB source.
