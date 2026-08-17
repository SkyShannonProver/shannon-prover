"""One-call diagnostic for the frozen Codex JSONL provider boundary.

This is not a proof-state-compiler efficacy experiment.  It sends no project
source or proof state and exists only to identify the exact provider events
emitted by the same OpenAI/Codex invocation used by one-step micros.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from workflow.codex_event_protocol import CODEX_EXEC_JSONL_CONTRACT
from workflow.validation.proof_state_compiler_one_step_model import (
    git_identity,
    run_model,
)


ROOT = Path(__file__).resolve().parents[2]
MODEL_BACKEND = "openai"
MODEL = "gpt-5.6-sol"
EFFORT = "high"
PROMPT = (
    "This is a provider-protocol smoke test with no proof state. Return the "
    "single submit-ready EasyCrypt tactic `trivial.` in the required JSON "
    "schema. Do not use any tool."
)


def run_protocol_smoke(root: Path = ROOT) -> dict[str, Any]:
    provenance = git_identity(root)
    if provenance.get("dirty") is not False:
        raise RuntimeError("Codex protocol smoke requires a clean worktree")
    identity = _codex_cli_identity()
    result = run_model(
        PROMPT,
        backend=MODEL_BACKEND,
        model=MODEL,
        effort=EFFORT,
        cwd=root,
    )
    audit = result.get("provider_event_audit")
    audit = audit if isinstance(audit, Mapping) else {}
    passed = bool(
        result.get("returncode") == 0
        and not result.get("error")
        and result.get("tools_observed") == []
        and str(result.get("tactic") or "").strip()
        and audit.get("contract") == CODEX_EXEC_JSONL_CONTRACT
        and audit.get("protocol_valid") is True
        and audit.get("provider_errors") == []
        and audit.get("protocol_unknowns") == []
        and audit.get("tool_item_types") == []
    )
    return {
        "schema_version": 1,
        "kind": "proof_state_compiler_codex_protocol_smoke",
        "git": provenance,
        "model_backend": MODEL_BACKEND,
        "model": MODEL,
        "effort": EFFORT,
        "tools_enabled": False,
        "source_or_proof_state_sent": False,
        "external_model_calls": 1,
        "provider_event_contract": CODEX_EXEC_JSONL_CONTRACT,
        "provider_identity": identity,
        "result": result,
        "passed": passed,
    }


def _codex_cli_identity() -> dict[str, Any]:
    executable = shutil.which("codex") or "codex"
    completed = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "executable_name": Path(executable).name,
        "version_returncode": completed.returncode,
        "version": completed.stdout.strip() or completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        output.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("protocol smoke output must stay inside project") from exc
    result = run_protocol_smoke()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
