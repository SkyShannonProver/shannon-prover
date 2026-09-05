"""Default outer-agent prompt for product projects without a custom prompt."""

from __future__ import annotations

from workflow.interleaved.project import InterleavedProject


def render_default_prompt(project: InterleavedProject) -> str:
    verifier = project.verifier or "workflow/interleaved/verify.py"
    return f"""# Interleaved Shannon proof-construction task

Complete `{project.final_lemma}` in `{project.target_file}` and leave the target
as a complete machine-checked EasyCrypt development with no `admit.`. You are
the outer proof-construction agent: own the cross-lemma decomposition, add
coherent helper lemmas, assemble the whole proof, and run whole-file checks.

You may delegate an outer-defined helper lemma, but never the final lemma, to a
managed Shannon node. Use only the scheduler commands below; do not launch the
inner runner or inspect its private lane/session artifacts directly.

```bash
.venv/bin/python workflow/interleaved/jobs.py submit \\
  --lemma HELPER --timeout-minutes 20
.venv/bin/python workflow/interleaved/jobs.py status
.venv/bin/python workflow/interleaved/jobs.py wait \\
  --after-sequence CURSOR --timeout-seconds 30
.venv/bin/python workflow/interleaved/jobs.py collect --job-id JOB_ID
.venv/bin/python workflow/interleaved/jobs.py cancel --job-id JOB_ID
```

For a partial proof handoff, write a concise strategy note inside `{{{{RUN_DIR}}}}`
and add `--handoff-current --strategy-note PATH` to `submit`. Respect every
active boundary lease: while a job is live, do not edit its lemma declaration,
prefix, or proof body. A verified job is not merged until `collect` succeeds.
An incomplete job may return a manager-derived accepted prefix and checkpoint;
use those as evidence, not as proof success.

Check the evolving project with:

```bash
.venv/bin/python {verifier} --check
```

Finish only after the final verifier passes. EasyCrypt, the scheduler-owned
canonical node result, and the whole-file verifier are the authorities; log
text, `qed.` text, and a model's confidence are not proof.

{{{{CONTINUATION_CONTEXT}}}}
"""
