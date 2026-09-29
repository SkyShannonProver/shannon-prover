"""Lock the one-way layering rule: ``core/`` never imports ``workflow/``.

This boundary is currently clean (verified 2026-08-19). The rule is cheap to
keep and expensive to win back, so it is asserted here instead of relying on
review. AST-based so docstrings/comments mentioning "workflow" don't trip it.
"""

import ast
from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parent.parent / "core"


def test_core_never_imports_workflow():
    offenders = []
    for path in sorted(_CORE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "workflow" or alias.name.startswith("workflow."):
                        offenders.append(f"{path}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                module = node.module or ""
                if module == "workflow" or module.startswith("workflow."):
                    offenders.append(f"{path}:{node.lineno}")
    assert not offenders, (
        "core/ must never import workflow/ (one-way layering); offenders: "
        + ", ".join(offenders)
    )


def test_every_module_root_constant_points_at_the_repo_root():
    """Parent-count root paths silently drift when a module moves one package
    deeper — the restructure broke four of them at once (MCP children died on
    PYTHONPATH, the manager resolved session dirs under workflow/). Import
    every production module that exposes a *(PROJECT|REPO)_ROOT* constant and
    anchor it on pyproject.toml."""
    import importlib
    import pkgutil

    import workflow
    import core

    repo_root = Path(__file__).resolve().parent.parent
    checked = 0
    for pkg in (workflow, core):
        for info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            if any(part in info.name for part in (".runs", "__main__")):
                continue
            try:
                module = importlib.import_module(info.name)
            except Exception:
                continue  # optional deps / entry-point-only modules
            for attr in ("PROJECT_ROOT", "_PROJECT_ROOT", "REPO_ROOT", "_REPO_ROOT"):
                value = getattr(module, attr, None)
                if isinstance(value, Path):
                    assert value == repo_root, (
                        f"{info.name}.{attr} = {value} is not the repo root"
                    )
                    checked += 1
    assert checked >= 8, f"only {checked} root constants found — sweep broken?"
