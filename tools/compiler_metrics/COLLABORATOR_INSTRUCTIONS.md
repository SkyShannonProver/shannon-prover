# Running the L1-vs-L4 surface ablation + auto-generating the figure

Paste this whole file to your Claude. It runs the chosen lemmas under **both**
surface profiles (L1 = bare goal, no compiler; L4 = full proof-state compiler),
then produces the 4-panel comparison figure **automatically** — you never open a
bundle by hand.

This is the **L1/L4 ablation**, NOT the adaptive mode.

---

## 0. One-time setup

```bash
# Use the default branch: it has the surface profiles, the metrics scripts,
# AND the per-turn token-fix that panel ④ needs.
cd <repo>                       # the crypto-agent-pipeline checkout
git fetch origin
git checkout big-project-driver
git pull --ff-only origin mcp-v0

# EasyCrypt env (opam switch is "easycrypt" by default)
eval "$(opam env --switch=easycrypt)"
```

**Sandbox note:** if you run inside an OS sandbox, `smt()` can fail with
"cannot start & connect to why3server" (the sandbox blocks the `nice()` syscall
`why3server` needs). Run **unsandboxed** / with escalation for these runs.

**Do not `git push`.** Just commit locally if asked.

---

## 1. Pick the lemmas (one suite JSON)

Copy the template and edit the `targets` list:

```bash
cp tools/compiler_metrics/ablation_suite_template.json eval/suites/my_ablation.json
```

Each target needs:

| field            | meaning                                                              |
|------------------|---------------------------------------------------------------------|
| `id`             | any unique label for this row (used in artifact paths)              |
| `file`           | path to the `.ec` file containing the lemma                         |
| `lemma`          | exact lemma name to prove                                            |
| `include_dir`    | EasyCrypt include path (usually `easycrypt-src/theories`)           |
| `copy_root`      | **only for multi-file projects** — the dir to copy so imports resolve |
| `timeout_minutes`| per-target cap (see §2)                                              |

The suite defaults already set `eval_mode: true` + `strip_proofs: true`,
so the prover is **blinded to the existing answer** — required for a clean
ablation. Leave those on.

---

## 1b. Bringing lemmas over from another repo (e.g. XMSS)

Your corpus lives in **other local checkouts** (XMSS, etc.). To make a lemma
runnable here you "vendor" its EasyCrypt files into `eval/examples/` so its
imports resolve, then point a target at it. Copy from your **local clone**, do
NOT fetch from GitHub.

**1. Copy the whole development dir** — not just the one `.ec`: EasyCrypt needs
every sibling the file `require import`s.
```bash
# whole project (multi-file dev): copy the dir
cp -R /path/to/xmss-checkout/proof  eval/examples/XMSS
# OR a single self-contained file (only stdlib imports):
cp /path/to/xmss-checkout/Foo.ec   eval/examples/XMSS_Foo.ec
```

**2. Add a target** in your suite JSON:
```json
{
  "id": "xmss_<lemma>",
  "file": "eval/examples/XMSS/<TheFile>.ec",
  "lemma": "<exact_lemma_name>",
  "copy_root": "eval/examples/XMSS",
  "include_dir": "easycrypt-src/theories"
}
```
- `copy_root` = the vendored project dir. The whole tree is copied per run, and
  **the file's own directory is auto-added to EasyCrypt's include path**, so
  `require import <Sibling>` resolves with no extra config.
- `include_dir` = the EC stdlib theories (`easycrypt-src/theories`).
- Single self-contained file? Set `file` to it and drop `copy_root` (it defaults
  to the file).
- **Leave proofs in the file** — eval mode proof-strips the isolated project
  copy; the prover never sees proof bodies. The original stays intact.

**3. Confirm it LOADS before running the suite** (fast loop for missing deps) —
this is the exact check the suite's preflight does:
```bash
eval "$(opam env --switch=easycrypt)"
easycrypt -I easycrypt-src/theories -I eval/examples/XMSS eval/examples/XMSS/<TheFile>.ec
```
- Clean exit (no error) ⇒ the suite will load it too. Done.
- `cannot locate theory X` / unresolved `require` ⇒ X is an extra dependency NOT
  in the stdlib. Copy X's `.ec`(s) into `eval/examples/XMSS/` as well, then
  re-run the check. Repeat until clean. (XMSS-style devs often pull in extra
  word/hash/Jasmin-style theory libs — vendor **every** theory the file
  transitively requires into the same project dir, since only one `include_dir`
  is honored besides the file's own dir.)

**4. The suite's built-in preflight** compile-checks each target before proving;
a target that still can't load is **skipped with the exact reason printed**, so a
missing dependency never burns a silent empty run.

---

## 2. Run the ablation

```bash
python3 -m eval_suite.run \
    --suite eval/suites/my_ablation.json \
    --profiles l1_goal_projection,l4_checked_action_surface \
    --timeout-minutes 90
```

- `--profiles` runs **exactly** L1 and L4 (ignores any other profile on the branch).
- `--repeats 3` (optional) runs each cell 3× to average out LLM noise.

### On the time limit (set it generous; let the agent give up on its own)
Each target gets **1 prove attempt** (`max_iterations: 1`). Within that attempt
the agent **self-terminates** — it emits a "blocked / giving up" report when it
judges itself stuck, typically **well under** the cap. So the timeout is a
**safety net for true hangs**, not the normal stop condition.

Set it **comfortably above** the hardest lemma's expected solve time so a real
solve is never truncated. **`--timeout-minutes 90`** is a good default (our
hardest proved lemma so far needed ~44 min). If a lemma is genuinely huge, bump
that one target's `timeout_minutes` in the suite. A run that ends "not proved"
**before** the cap = a real give-up; one that ends exactly **at** the cap = it
hit the wall (rerun with a larger cap if you expected it to solve).

### Where output lands
`eval_suite.run` **auto-builds a bundle per run** into:
```
agent_view_runs/<lemma>/<timestamp>__<commit>/
```
(That's the post-run timeline+view+token artifact. You don't touch it directly.)

---

## 3. Pull the figure (turnkey — no manual bundle reading)

From the **repo root**, after the runs finish:

```bash
python3 tools/compiler_metrics/stuck_pipeline.py all
```

It auto-discovers every bundle under `./agent_view_runs`, computes the metrics,
and writes:

```
tools/compiler_metrics/stuck_out/stuck_clean_subset.png   <- the 4-panel figure
tools/compiler_metrics/stuck_out/metrics.json             <- every metric, per run
```
…and prints a per-run table to the terminal.

Point it elsewhere if your bundles are not under the repo root:
```bash
python3 tools/compiler_metrics/stuck_pipeline.py all /abs/path/to/agent_view_runs
# or:  BUNDLE_ROOTS="/dir1:/dir2" python3 tools/compiler_metrics/stuck_pipeline.py all
# not sure where the bundles are? scan the whole repo recursively:
python3 tools/compiler_metrics/stuck_pipeline.py all .
```

### >>> WHAT TO DELIVER TO THE USER <<<
The single deliverable is the **figure**, a PNG at this exact path:
```
tools/compiler_metrics/stuck_out/stuck_clean_subset.png
```
**Open/display that PNG and give it to the user**, and tell them its path. Also
mention the printed per-run table (or `tools/compiler_metrics/stuck_out/metrics.json`)
if they want the raw numbers. The user wants the figure — surface it, don't just
say "done."

---

## 4. What the 4 panels mean

Read **③ first** — it's the control.

- **③ Error-generation rate (CONTROL — expect ≈ equal).** Of the model's
  distinct tactic ideas, the fraction wrong on first try (cheap probes counted).
  Measures the *model*, not the tool. L1≈L4 ⇒ same-strength model in both arms,
  so any difference in the other panels is the **surface**, not luck.
- **① Committed rejects / progress step (↓ better).** Real tactics EasyCrypt
  rejected, per forward step — how often it wastes a *committed* move.
- **② Blind-retry depth (↓ better).** Total committed tactics that got rejected
  ("blind" = committed without probing first).
- **④ Destructive token share (↓ better).** % of the model's output tokens spent
  on dead-ends (rejected commits + restarts); cheap probing/inspecting excluded.
  **Uses real per-turn tokens** when present (mcp-v0). If you see
  "% of think-time (proxy)" in the axis, your bundles predate the token-fix —
  re-run on mcp-v0.

**Takeaway the figure makes:** ③ shows the model errs equally often in both arms
→ ①②④ show the compiler makes each error far **cheaper** (fewer destructive
commits, less blind retrying, less token waste). The compiler reduces error
**cost**, not error **rate**.

The figure uses the **same-commit + both-proved** subset (the fair "cost of
mistakes" comparison). A lemma that proved in only one arm won't appear in the
PNG, but all its numbers are still in the printed table and `metrics.json`.

---

## 5. Troubleshooting

| symptom | fix |
|---|---|
| `smt(): cannot start & connect to why3server` | run unsandboxed / with escalation (see §0) |
| panel ④ axis says "proxy" | you're not on mcp-v0 (no token-fix) — checkout mcp-v0 and re-run the lemmas |
| `clean_chart: NO lemma has BOTH a proved L1 and a proved L4 run` | a lemma must prove in *both* arms to enter the figure; check the printed table for which arm failed |
| a run was killed before the bundle was written | rebuild it: `python3 -m workflow.validation.run_report_bundle <run_iteration_dir> --timestamp <TS>` |
| no bundles found | run `stuck_pipeline.py all` from the repo root, or pass the bundle dir explicitly (§3) |
