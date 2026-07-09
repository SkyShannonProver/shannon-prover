# Knowledge

## Architecture

```
Legend:  [script.py] = Python auto
        «LLM» = LLM offline analysis (frozen, do not regenerate casually)
        (human) = manual annotation

Assembly — how agent/proof_guide.json is built:

  «LLM» analyzed traces ──────────► proof_tactics_and_strategies.jsonl ──┐
  «LLM» categorized structures ───► goal_state_categories.json ──────────┼► [build_proof_guide.py]
                                                                          v
                                                                agent/proof_guide.json
                                                                (single entry point)

Agent retrieval flow:
  1. Read agent/proof_guide.json (one file)
  2. Match strategy by crypto type → roadmap
  3. Match pattern by structural_description → generic template / variants
  4. Instantiate from the live session goal state
  See AGENT.md for detailed usage guide.
```

KB policy: `knowledge/base` must not contain concrete lemma proof scripts,
proof-bank entries, goal-state replay chains, or per-lemma examples. This is an
authoring convention (the `kb_no_exact_tactics` lint has been removed; eval-mode
leakage is prevented at query time by `search_guide.search()`'s self-redaction).

## Quick Start: Adding a New Trace

When you (or a collaborator) have a new Claude Code session that contains proof work,
follow these steps to integrate it into the pipeline.

**Step 1: Copy raw session and process**
```bash
.venv/bin/python -m knowledge.session_trace.extract copy-raw
.venv/bin/python -m knowledge.session_trace.extract process
```
This copies new session JSONLs from `~/.claude/projects/` into `session_trace/data/` and
processes them into per-session traces in `session_trace/processed/`.

Note: `PROJECT_HASH` in `extract.py` is derived from the project path and differs per machine
(e.g. `-Users-<you>-...` vs `-Users-othername-...`). Update it to match `ls ~/.claude/projects/`.

**Step 2: Add problem boundaries (manual)**

Edit `session_trace/splits_manual.json` — add an entry for the new session:
```json
"<session_id>": [
  {"start_step": 0, "end_step": <last_step>, "file": "<file>.ec", "lemmas": ["<lemma_name>"], "description": "<what was proved>"}
]
```

To find the right step numbers, check the processed session file:
```bash
python3 -c "
import json
with open('knowledge/session_trace/processed/<session_id>.json') as f:
    trace = json.load(f)
for s in trace['steps']:
    um = s.get('user_message', '')
    targets = set(a.get('target_file','') for a in s.get('attempts',[]) if a.get('target_file'))
    if um or targets:
        print(f'  [{s[\"step_index\"]}] {\"USER: \"+um[:80] if um else \"\"} {\"TARGETS: \"+str(targets) if targets else \"\"}')
"
```

**Step 3: Organize by problem + update summaries**
```bash
.venv/bin/python -m knowledge.session_trace.extract organize && \
.venv/bin/python -m knowledge.analyze
```

**What gets updated:**
- `session_trace/processed/by_problem/` — new per-problem trace with auto-detected outcome
- `knowledge/README.md` — all auto-generated tables updated

## Pipeline Commands

| Command | What it does |
|---|---|
| `knowledge.session_trace.extract copy-raw` | Copy new sessions from `~/.claude/` → `session_trace/data/` |
| `knowledge.session_trace.extract process` | Process raw sessions → `session_trace/processed/<session>.json` |
| `knowledge.session_trace.extract organize` | Split by problem → `processed/by_problem/` (uses `splits_manual.json`) |
| `knowledge.base.search kb --goal-shape pr_eq` | Search KB by goal shape |
| `knowledge.analyze` | Update all auto-generated sections in this README |

---

## base/ -- Knowledge Base

See [base/DESIGN.md](base/DESIGN.md) for design rationale.

Agent-facing stores:

<!-- BEGIN:kb_summary -->
Agent-facing stores (3-layer architecture):

- **`agent/proof_guide.json`** (strategy layer, agent entry point): 10 strategies, 45 EC syntax tips, 34 patterns, 18 closer idioms. Searchable via `search_guide.py`.
- **`agent/ec_tactics.json`** (execution layer): Indexed by (goal_type, tactic). Syntax forms, error diagnosis with strategy/execution classification, smt_hints. Used by `-goal-info` and `-diagnose`.
- **`agent/decision_tree.md`** (navigation): Pitfalls (P1-P14), recipes (R1-R10), navigation tree from goal shape → matching pattern/recipe.

Build-time sources:

- **`sources/proof_tactics_and_strategies.jsonl`** (35 entries): Goal shapes, tactic combos, strategies, EC syntax hints.
- **`sources/goal_state_categories.json`** (18 categories): Structural proof categories with indicators and generic tactics.
<!-- END:kb_summary -->

```bash
# Search KB by goal shape
.venv/bin/python -m knowledge.base.search kb --goal-shape pr_eq

# Search KB for strategies
.venv/bin/python -m knowledge.base.search kb --type strategy

# Search by tags
.venv/bin/python -m knowledge.base.search kb --tags swap mu_not
```

## Traces

Two types of proof traces, collected from different sources, serving different purposes.

## expert_trace/ -- Collector-Gathered Traces

**Source:** `collector.py` runs an interactive proof session where a human expert guides an LLM through an EasyCrypt proof. Each tactic step is recorded.

**Format:** Per-session directory with `trace.json` (full session) and `trace.jsonl` (incremental steps).

**Schema** (defined in `expert_trace/schema.py`):
- `EnvironmentState` -- what EasyCrypt sees: goal before/after, tactic sent, accepted/rejected, error
- `AgentDiagnosis` -- what the LLM outputs: plan, rationale, alternatives (short, structured JSON)
- `HumanIntervention` -- expert guidance: type, technique, intent, scope

**What it captures:** The _actions_ and _outcomes_ of a proof attempt -- which tactic was tried, whether it worked, what the expert said to do next.

**What it lacks:** The LLM's deep reasoning -- the chain-of-thought that led to choosing a tactic. `AgentDiagnosis.rationale` is a one-liner; the actual multi-paragraph reasoning is not recorded.

**Usage:**
```bash
uv run python -m knowledge.expert_trace.collector \
    --file path/to/proof.ec --lemma lemma_name --expert "Name"
```

## session_trace/ -- Codex / Claude Code Thinking Traces

**Source:** Claude Code session logs (`~/.claude/projects/<project-hash>/*.jsonl`), specifically the `{"type": "thinking"}` content blocks from assistant messages.

### Directory Layout

```
session_trace/
├── extract.py          # Extraction + organize (no AI needed)
├── pipeline.py         # AI pipeline: classify + split (for scaling to new sessions)
├── splits_manual.json  # Hand-annotated problem boundaries
├── data/               # Raw session JSONLs (gitignored, copied from ~/.claude/)
├── classified/         # LLM classification results (gitignored, for pipeline.py)
└── processed/
    ├── <session>.json  # Per-session structured traces (proof-solving sessions only)
    └── by_problem/     # Per-problem traces, organized by .ec file
        ├── elgamal/
        ├── br93/
        ├── PIR/
        └── ...
```

### Scripts

**`extract.py`** -- Main tool, no API key needed.
Note: `PROJECT_HASH` in `extract.py` is derived from the project path and differs per machine
(e.g. `-Users-<you>-...` vs `-Users-othername-...`). Update it to match `ls ~/.claude/projects/`.
```bash
# Copy raw sessions from ~/.claude/ into data/
uv run python -m knowledge.session_trace.extract copy-raw

# Process into per-session structured traces
uv run python -m knowledge.session_trace.extract process

# Split into per-problem traces (uses splits_manual.json)
uv run python -m knowledge.session_trace.extract organize

# All three stages
uv run python -m knowledge.session_trace.extract all
```

**`pipeline.py`** -- AI-powered pipeline for scaling (requires `ANTHROPIC_API_KEY` in `.env`).
Use this when you have new sessions and don't want to annotate splits by hand:
```bash
# Full pipeline: fetch -> classify -> split -> organize
uv run python -m knowledge.session_trace.pipeline all

# Individual stages
uv run python -m knowledge.session_trace.pipeline fetch      # copy raw + basic extract
uv run python -m knowledge.session_trace.pipeline classify   # LLM classifies sessions
uv run python -m knowledge.session_trace.pipeline split      # LLM splits by problem
uv run python -m knowledge.session_trace.pipeline organize   # write per-problem traces

# Preview what the LLM will see (no API calls)
uv run python -m knowledge.session_trace.pipeline classify --dry-run
```

Pipeline stages:

| Stage | What it does | Needs API key? | Output |
|-------|-------------|----------------|--------|
| `fetch` | Copy raw sessions from `~/.claude/` + basic extraction | No | `data/*.jsonl`, `processed/<session>.json` |
| `classify` | LLM reads session summary, labels `proof_solving` / `config` / `planning` | Yes | `classified/<session>.json` |
| `split` | LLM reads step timeline, identifies problem boundaries (file + lemmas + step range) | Yes | `classified/splits/<session>.json` |
| `organize` | Uses split annotations to write per-problem traces | No | `processed/by_problem/<ec_file>/<session>_<lemma>.json` |

### processed/ -- Per-Session Structured Traces

Only proof-solving sessions are kept. Each file is one session:

Per-session traces:
```
session_id, ec_files, problem_description, timestamp
steps[]:
  - thinking:         full chain-of-thought (the "why")
  - thinking_summary: first 200 chars for quick scanning
  - user_message:     human prompt that triggered this step
  - tool_calls[]:
      tool_name:      Bash / Read / Edit / Grep / ...
      summary:        "read DiffieHellman.ec", "apply tactic: rewrite ..."
      result_snippet: first 500 chars of result
      is_error:       true/false
  - attempts[]:
      tactic_or_edit:     the proof code written
      target_file:        which .ec file
      success:            true/false/null
      error_snippet:      EC error if failed
      ec_output_snippet:  EC output if succeeded
  - files_read:       ["DiffieHellman.ec", "Group.ec"]
  - files_searched:   ["log_pow", "*.ec"]
```

<!-- BEGIN:sessions_table -->
Current proof-solving sessions (19 sessions, 29 problem traces):

| Session | Steps | Thinking | Problems |
|---------|-------|----------|----------|
| b3113200 | 291 | 187K | PIR |
| 8cab03b1 | 617 | 187K | elgamal, br93, Dice4_6, PRG, hashed_elgamal_std, hashed_elgamal_generic, bad_abs, cramer_shoup, PIR |
| 201f8f87 | 243 | 143K | SchnorrPK |
| b9ddef1e | 265 | 132K | PIR, Pedersen |
| c3c430bf | 195 | 71K | Pedersen |
| a7f3df82 | 381 | 64K | elgamal, hashed_elgamal_std, hashed_elgamal_generic, Dice4_6, br93 |
| 9bbbe5a8 | 128 | 52K | cramer_shoup |
| 9342ac77 | 94 | 40K | PIR |
| 2a29cad9 | 448 | 39K | AEAD.ec, AdvAbsVal.ec, AllCore.ec, Array.ec, Bigalg.ec, Bigop.ec |
| b3793d9c | 326 | 36K | cramer_shoup |
| 6dae61b3 | 52 | 23K | PRG |
| bd1e1b05 | 19 | 8K | Dice4_6.ec, PIR.ec, PRG.ec, Pedersen.ec, SigmaProtocol.ec, bad_abs.ec |
| 8212a8f4 | 6 | 4K | Dice4_6.ec, PIR.ec, PRG.ec, Pedersen.ec, bad_abs.ec, br93.ec |
| 900f8064 | 18 | 3K | PIR.ec |
| a9af4b61 | 33 | 3K | AllCore.ec, DDH.ec, my_proof.ec, problem.ec, proof.ec |
| b881625f | 16 | 2K | AEAD.ec, AdvAbsVal.ec, AllCore.ec, Array.ec, Bigalg.ec, Binomial.ec |
| 41a9690f | 15 | 2K | DiffieHellman.ec, Group.ec, elgamal.ec, proof.ec |
| 2c3d1dad | 3 | 1K | PIR.ec |
| 2aec3dfe | 1 | 1K |  |
<!-- END:sessions_table -->

### processed/by_problem/ -- Per-Problem Traces

Each trace has an auto-detected `outcome` field:
- **success** -- EC file compiles to 100%, no admits in final edit
- **partial** -- EC file compiles, but last edit still contains `admit` (some lemmas unproved)
- **fail** -- critical errors or stuck at end
- **unknown** -- no EC check found in the segment

> For proof status, remaining admits, and stuck points, see [PLAN.md](../PLAN.md).

<!-- BEGIN:by_problem_table -->
Per-problem traces:

- **Steps**: number of agent turns (one turn = thinking + tool calls). Not all steps produce attempts -- many are reading files, searching, or pure reasoning.
- **Tools**: total tool invocations (Bash, Read, Edit, Grep, Glob, etc.)
- **Thinking**: total chain-of-thought characters (proxy for reasoning effort)
- **Searches**: Read/Grep/Glob on `easycrypt-src/` files (source code lookups)
- **Attempts (ok/fail)**: tactic or edit attempts that EasyCrypt accepted / rejected
- **Model**: which LLM generated this proof
- **Note**: heuristic tag based on metric patterns (TODO: replace with LLM classification)

| Problem | Trace | Model | Outcome | Steps | Tools | Thinking | Searches | Attempts (ok/fail) | Note |
|---|---|---|---|---|---|---|---|---|---|
| Dice4_6 | [8cab03b1](session_trace/processed/by_problem/Dice4_6/8cab03b1_all.json) | opus | partial | 57 | 41 | 15K | 0 | 16/8 |  |
| Dice4_6 | [a7f3df82](session_trace/processed/by_problem/Dice4_6/a7f3df82_all.json) | sonnet | success | 8 | 8 | 0 | 2 | 3/0 | quick solve |
| PIR | [8cab03b1](session_trace/processed/by_problem/PIR/8cab03b1_all.json) | opus | partial | 51 | 43 | 5K | 0 | 10/0 |  |
| PIR | [9342ac77](session_trace/processed/by_problem/PIR/9342ac77_PIR_correct.json) | opus | partial | 69 | 48 | 33K | 3 | 35/4 |  |
| PIR | [9342ac77](session_trace/processed/by_problem/PIR/9342ac77_PIR_s_uniform.json) | opus | success | 20 | 16 | 6K | 0 | 8/4 |  |
| PIR | [b3113200](session_trace/processed/by_problem/PIR/b3113200_Pr_PIR_s.json) | opus | success | 291 | 190 | 187K | 45 | 57/10 | struggled, source lookups |
| PIR | [b9ddef1e](session_trace/processed/by_problem/PIR/b9ddef1e_PIR_s__uniform.json) | opus | partial | 6 | 5 | 757 | 0 | 1/0 |  |
| PIR | [b9ddef1e](session_trace/processed/by_problem/PIR/b9ddef1e_PIR_s_uniform.json) | opus | partial | 87 | 65 | 93K | 10 | 37/11 | struggled, source lookups |
| PIR | [b9ddef1e](session_trace/processed/by_problem/PIR/b9ddef1e_Pr_PIR_s.json) | opus | partial | 16 | 13 | 31K | 0 | 8/0 | planning-heavy |
| PIR | [b9ddef1e](session_trace/processed/by_problem/PIR/b9ddef1e_is_restr_addS.json) | opus | success | 21 | 17 | 6K | 0 | 3/3 |  |
| PRG | [6dae61b3](session_trace/processed/by_problem/PRG/6dae61b3_all.json) | opus | success | 52 | 34 | 23K | 3 | 16/1 |  |
| PRG | [8cab03b1](session_trace/processed/by_problem/PRG/8cab03b1_all.json) | opus | success | 60 | 49 | 7K | 0 | 28/3 |  |
| Pedersen | [b9ddef1e](session_trace/processed/by_problem/Pedersen/b9ddef1e_all.json) | opus | success | 132 | 131 | 123 | 12 | 50/24 | trial-and-error, source lookups |
| Pedersen | [c3c430bf](session_trace/processed/by_problem/Pedersen/c3c430bf_all.json) | opus | success | 195 | 133 | 71K | 11 | 99/9 | struggled, source lookups |
| SchnorrPK | [201f8f87](session_trace/processed/by_problem/SchnorrPK/201f8f87_schnorr_proof_of_knowledge_completeness_ll_schnorr.json) | opus | success | 231 | 160 | 143K | 5 | 102/15 | struggled |
| bad_abs | [8cab03b1](session_trace/processed/by_problem/bad_abs/8cab03b1_all.json) | opus | success | 27 | 19 | 6K | 0 | 6/1 |  |
| br93 | [8cab03b1](session_trace/processed/by_problem/br93/8cab03b1_all.json) | opus | partial | 116 | 82 | 40K | 8 | 41/7 | struggled, source lookups |
| br93 | [a7f3df82](session_trace/processed/by_problem/br93/a7f3df82_all.json) | sonnet | success | 78 | 57 | 40K | 0 | 29/1 |  |
| cramer_shoup | [8cab03b1](session_trace/processed/by_problem/cramer_shoup/8cab03b1_adv_DDH_DDH_ex_CCA_DDH0.json) | opus | fail | 69 | 51 | 15K | 2 | 22/8 |  |
| cramer_shoup | [9bbbe5a8](session_trace/processed/by_problem/cramer_shoup/9bbbe5a8_CramerShoup_correct.json) | opus | partial | 51 | 42 | 14K | 10 | 5/0 | source lookups |
| cramer_shoup | [9bbbe5a8](session_trace/processed/by_problem/cramer_shoup/9bbbe5a8_adv_DDH_DDH_ex.json) | opus | partial | 64 | 49 | 35K | 4 | 7/2 | planning-heavy |
| cramer_shoup | [b3793d9c](session_trace/processed/by_problem/cramer_shoup/b3793d9c_CCA_DDH0.json) | opus | success | 91 | 89 | 1K | 0 | 24/13 | trial-and-error |
| cramer_shoup | [b3793d9c](session_trace/processed/by_problem/cramer_shoup/b3793d9c_continuation.json) | opus | unknown | 40 | 40 | 0 | 0 | 29/4 | trial-and-error |
| elgamal | [8cab03b1](session_trace/processed/by_problem/elgamal/8cab03b1_ddh1_gb_Gb_half.json) | opus | partial | 79 | 51 | 61K | 3 | 31/1 |  |
| elgamal | [a7f3df82](session_trace/processed/by_problem/elgamal/a7f3df82_all.json) | sonnet | success | 105 | 103 | 2K | 2 | 83/7 | trial-and-error |
| hashed_elgamal_generic | [8cab03b1](session_trace/processed/by_problem/hashed_elgamal_generic/8cab03b1_all.json) | opus | partial | 48 | 37 | 6K | 0 | 13/0 |  |
| hashed_elgamal_generic | [a7f3df82](session_trace/processed/by_problem/hashed_elgamal_generic/a7f3df82_all.json) | sonnet | success | 28 | 27 | 662 | 0 | 19/1 |  |
| hashed_elgamal_std | [8cab03b1](session_trace/processed/by_problem/hashed_elgamal_std/8cab03b1_all.json) | opus | success | 71 | 49 | 25K | 0 | 25/0 |  |
| hashed_elgamal_std | [a7f3df82](session_trace/processed/by_problem/hashed_elgamal_std/a7f3df82_all.json) | sonnet | success | 78 | 76 | 1K | 11 | 35/1 | trial-and-error, source lookups |
<!-- END:by_problem_table -->

## Discovery

Analysis of reasoning traces to understand where the agent struggles, what it spends time on,
and what a knowledge base should contain.

**To regenerate**: `uv run python -m knowledge.analyze` or `.venv/bin/python -m knowledge.analyze`

<!-- BEGIN:discovery_stats -->
Data: 10 proof-solving sessions, 29 problem traces,
138 failed attempts, 69 long thinking blocks (>3K chars).

### Where the agent fails

| Error type | Count | What happens |
|---|---|---|
| nothing_to_rewrite | 27 | Agent tries `rewrite` but goal doesn't syntactically match the expected pattern |
| cannot_prove_goal_strict | 26 | `by smt()` or `by auto` can't close the sub-goal; needs manual decomposition or hint lemmas |
| uncategorized | 25 | Miscellaneous |
| proof_script_context_error | 12 | Tactic executed outside proof context (proof already ended or not started) |
| measure_computation | 8 | smt can't evaluate `mu [1..6] (...)` over finite sets; needs manual `have` steps |
| cannot_close_by | 8 | `by tactic` didn't close goal in one step |
| parse_error | 7 | Tactic syntax wrong |
| cannot_find_lemma_or_pattern | 6 | Referenced a non-existent lemma name or `Pr [...]` rewrite pattern |
| unknown_name | 4 | Used an identifier not in scope |
| type_error | 3 | Type mismatch in tactic arguments |
| nothing_to_introduce | 3 | `move=>` with nothing to introduce |
| cannot_apply | 3 | `apply` target doesn't match goal |
| tool_usage_error | 2 | manager/backend tool command format error |
| wrong_goal_shape_for_tactic | 2 | Tactic expects a different goal form |
| swap_not_independent | 2 | `swap` fails because statements have read/write dependency |

Top 3 account for 56% of all 138 failures. None are 'wrong strategy' failures -- the agent chose the right approach but got stuck on execution details.

### What the agent spends long thinking on (69 blocks >3K chars)

| Category | Count | What the agent is doing | Can KB help? | Examples |
|---|---|---|---|---|
| planning_approach | 69 | Deciding overall proof strategy | Yes: `strategy` entries | [Dice4_6 step 240](session_trace/processed/by_problem/Dice4_6/8cab03b1_all.json), [PIR step 14](session_trace/processed/by_problem/PIR/9342ac77_PIR_correct.json), [PRG step 21](session_trace/processed/by_problem/PRG/6dae61b3_all.json) |
| algebraic_reasoning | 60 | Hand-computing group algebra and verifying equalities | Partially: smt hint lemmas | [Dice4_6 step 240](session_trace/processed/by_problem/Dice4_6/8cab03b1_all.json), [PIR step 14](session_trace/processed/by_problem/PIR/9342ac77_PIR_correct.json), [PRG step 21](session_trace/processed/by_problem/PRG/6dae61b3_all.json) |
| understanding_program | 54 | Tracing EasyCrypt program line by line | Limited: checklists | [PIR step 14](session_trace/processed/by_problem/PIR/9342ac77_PIR_correct.json), [Pedersen step 9](session_trace/processed/by_problem/Pedersen/c3c430bf_all.json), [SchnorrPK step 11](session_trace/processed/by_problem/SchnorrPK/201f8f87_schnorr_proof_of_knowledge_completeness_ll_schnorr.json) |
| bijection_construction | 33 | Constructing the bijection function for `rnd` | Yes: bijection templates | [PIR step 82](session_trace/processed/by_problem/PIR/b3113200_Pr_PIR_s.json), [Pedersen step 9](session_trace/processed/by_problem/Pedersen/c3c430bf_all.json), [SchnorrPK step 12](session_trace/processed/by_problem/SchnorrPK/201f8f87_schnorr_proof_of_knowledge_completeness_ll_schnorr.json) |
| debugging_error | 30 | Understanding why a tactic failed | Yes: `common_failure` + `fallback` | [PIR step 50](session_trace/processed/by_problem/PIR/b3113200_Pr_PIR_s.json), [Pedersen step 9](session_trace/processed/by_problem/Pedersen/c3c430bf_all.json), [SchnorrPK step 12](session_trace/processed/by_problem/SchnorrPK/201f8f87_schnorr_proof_of_knowledge_completeness_ll_schnorr.json) |
| swap_alignment | 19 | Figuring out program statement reordering | Partially: swap rules | [PIR step 58](session_trace/processed/by_problem/PIR/b3113200_Pr_PIR_s.json), [Pedersen step 98](session_trace/processed/by_problem/Pedersen/c3c430bf_all.json), [SchnorrPK step 140](session_trace/processed/by_problem/SchnorrPK/201f8f87_schnorr_proof_of_knowledge_completeness_ll_schnorr.json) |
| searching_lemma_syntax | 22 | Looking for EasyCrypt-specific syntax | Yes: `ec_syntax` entries | [PIR step 28](session_trace/processed/by_problem/PIR/9342ac77_PIR_correct.json), [br93 step 138](session_trace/processed/by_problem/br93/a7f3df82_all.json), [cramer_shoup step 83](session_trace/processed/by_problem/cramer_shoup/9bbbe5a8_CramerShoup_correct.json) |

Key finding: the agent mostly struggles with **execution details** (algebraic reasoning, bijection construction, swap alignment), not with choosing the wrong strategy.

### How often the agent reads EasyCrypt source code, and whether it helps

29 problem traces, 49 EC source reads total.

| Metric | Count |
|---|---|
| Problems where agent read EC source | 15 / 29 (51%) |
| Total EC source reads | 49 |
| Reads followed by success (within 3 steps) | 14 / 49 (28%) |
| Reads NOT followed by success | 35 / 49 (71%) |

**When source reads help**: agent looks up a **specific lemma name or syntax**, finds it, and immediately uses it (targeted reads).

**When source reads don't help**: agent reads theory files at the **start of a proof** for background understanding (DiffieHellman.ec, Group.ec, etc.) -- payoff is indirect and delayed.

**Implication for KB**: The KB's `smt_hints` field partially replaces targeted lemma lookups -- if the agent knows which lemmas to try, it doesn't need to grep through theory files.

### Implications for knowledge base design

1. The KB should provide not just 'which tactic to use' but also **reasoning hints**
   (why the bijection works, which smt lemmas to use, what to do when a tactic fails).

2. Each tactic combo candidate should include:
   - `template`: the tactic sequence
   - `reasoning_hints`: why this works, key algebraic steps
   - `smt_hints`: lemma names to pass to smt (expD, expM, addrK, etc.)
   - `common_failure`: most likely error when using this combo
   - `fallback`: what to try when it fails

3. Error recovery should be co-located with patterns, not stored separately.
   The agent needs a comprehensive view: "try X, if it fails with Y, do Z instead."

4. Bijection templates are high-value KB content -- 33/69 long thinking blocks involve constructing bijections, and the same patterns repeat across proofs.
<!-- END:discovery_stats -->

## Comparison

| | expert_trace | session_trace/data | session_trace/processed |
|---|---|---|---|
| Content | tactic + goal state + result | raw Claude Code session logs | organized proof steps with thinking + tool calls + attempts |
| Granularity | one record per tactic | one JSONL per session | one step per LLM turn |
| Reasoning | one-line rationale | raw thinking blocks (unstructured) | thinking + associated tool calls + success/fail |
| Source | collector.py (API calls) | Claude Code (~/.claude/) | extracted from data/ |
| Good for | tactic success rate, proof replay | full raw data preservation | understanding proof strategies, training data |
