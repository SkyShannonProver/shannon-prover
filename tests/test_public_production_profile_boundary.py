"""Production boundaries must work in an independently exported checkout."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from workflow.proof_state_compiler.profile_registry import PRODUCTION_PROFILE_IDS
from workflow.proof_state_compiler.release_manifest import production_release_manifest


ROOT = Path(__file__).resolve().parents[1]

def test_public_orchestrator_help_does_not_advertise_research_profiles() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "workflow.orchestrator", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--research-surface-profile" not in result.stdout
    assert "_audit" not in result.stdout

def test_production_manifest_contains_only_treatment_activations() -> None:
    manifest = production_release_manifest()
    assert manifest.profile_ids == tuple(sorted(PRODUCTION_PROFILE_IDS))
    assert manifest.feature_ids
    assert len(manifest.feature_ids) == 7
    assert "accepted_contract_retention" not in manifest.feature_ids
    assert "losslessness_certificate_application" not in manifest.feature_ids
    assert "program_operation_readiness" not in manifest.feature_ids

def test_production_import_does_not_load_research_registry() -> None:
    script = (
        "import json,sys; "
        "from workflow.proof_state_compiler.release_manifest import "
        "production_release_manifest; production_release_manifest(); "
        "print(json.dumps(sorted(x for x in sys.modules if "
        "'proof_state_compiler_research' in x)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == []
