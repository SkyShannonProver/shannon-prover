"""Layering contract: core/ must never import workflow/.

The dependency direction is workflow -> core (CLAUDE.md's manager boundary).
This invariant was restored once (narrative_safety -> proof_strip) and broken
once (session_workspace_view_manager importing workflow.context_intents,
fixed by moving context_intents into core), so it is now pinned by AST scan:
any `import workflow...` / `from workflow...` anywhere under core/ — including
lazy imports inside functions — fails this test.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)


def _workflow_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "workflow" or alias.name.startswith("workflow."):
                    hits.append(f"{path.relative_to(ROOT)}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0 and (mod == "workflow" or mod.startswith("workflow.")):
                hits.append(f"{path.relative_to(ROOT)}:{node.lineno} from {mod}")
    return hits


def test_core_never_imports_workflow():
    violations: list[str] = []
    for path in sorted((ROOT / "core").rglob("*.py")):
        violations.extend(_workflow_imports(path))
    assert not violations, (
        "core/ must not import workflow/ (dependency direction is workflow -> core):\n"
        + "\n".join(violations)
    )


if __name__ == "__main__":
    test_core_never_imports_workflow()
    print("layering contract OK")
