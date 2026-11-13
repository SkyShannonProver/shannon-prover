"""Lock the one-way layering rule: ``core/`` never imports ``workflow/``.

This boundary is currently clean (verified 2026-08-19). The rule is cheap to
keep and expensive to win back, so it is asserted here instead of relying on
review. AST-based so docstrings/comments mentioning "workflow" don't trip it.
"""

import ast
from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parents[3] / "core"


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

    repo_root = Path(__file__).resolve().parents[3]
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


# ---------------------------------------------------------------------------
# The interleaved product is a module of the runtime trunk. Nothing else may
# depend on it, and it may use the rest of the trunk only through the modules
# listed here; adding one is a reviewed edit of this list.
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[3]
_INTERLEAVED_CODE = ("workflow/interleaved/", "experiments/interleaved_shannon/")
_INTERLEAVED_OWNED = _INTERLEAVED_CODE + ("tests/public/interleaved/", "tests/helpers/interleaved.py")
_FIRST_PARTY = {"core", "workflow", "eval_suite", "eval", "tools", "scripts", "experiments"}
INTERLEAVED_MAY_IMPORT = {
    "core.digests",
    "core.jsonio",
    "core.paths",
    "core.easycrypt.compiler_resource_loader",
    "core.easycrypt.ec_daemon_client",
    "core.easycrypt.ec_env",
    "core.easycrypt.ec_lifecycle",
    "core.easycrypt.eval_source_prep",
    "core.easycrypt.lemma_decls",
    "core.easycrypt.lemma_extract",
    "core.easycrypt.proof_text",
    "core.easycrypt.toolchain",
    "workflow.agents.ec_services",
    "workflow.node.outer_proof_handoff",
    "workflow.node.proof_node_manager",
    "workflow.node.proof_node_resume",
    "workflow.proc_lifecycle",
    "workflow.proof_tool.easycrypt_source_resource",
    "workflow.proof_tool.proof_tool_launch",
    "workflow.provider.provider_sessions",
    "workflow.schemas.prover_result",
    "workflow.tree.supervisor",
    "workflow.validation.claude_required_mcp_sentinel",
}


def _python_files(*prefixes: str):
    for prefix in prefixes:
        root = _REPO / prefix
        if root.is_dir():
            yield from sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: Path):
    """(module, imported names, line) for each import, relative ones resolved."""
    rel = path.relative_to(_REPO)
    package = list(rel.with_suffix("").parts[:-1])
    if rel.name == "__init__.py":
        package = list(rel.parent.parts)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, (), node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            yield module, tuple(alias.name for alias in node.names), node.lineno
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # importlib.import_module("...") and `python -m ...` arguments.
            if node.value.startswith("workflow.interleaved"):
                yield node.value.split()[0], (), node.lineno


def _owned_by_interleaved(rel: str) -> bool:
    return rel.startswith(_INTERLEAVED_OWNED)


def test_nothing_outside_interleaved_depends_on_it():
    offenders = []
    for path in _python_files("core", "workflow", "eval_suite", "tools", "scripts", "experiments", "tests"):
        rel = path.relative_to(_REPO).as_posix()
        if _owned_by_interleaved(rel) or rel == "tests/public/repo/test_layer_boundaries.py":
            continue
        for module, _names, line in _imports(path):
            if module == "workflow.interleaved" or module.startswith("workflow.interleaved."):
                offenders.append(f"{rel}:{line} {module}")
    assert not offenders, "only the interleaved module may import workflow.interleaved:\n  " + "\n  ".join(offenders)


def test_interleaved_uses_only_its_declared_trunk_modules():
    undeclared, private = [], []
    for path in _python_files(*_INTERLEAVED_CODE):
        rel = path.relative_to(_REPO).as_posix()
        for module, names, line in _imports(path):
            if module.split(".")[0] not in _FIRST_PARTY or module.startswith(
                    ("workflow.interleaved", "experiments.interleaved_shannon")):
                continue
            if module not in INTERLEAVED_MAY_IMPORT:
                undeclared.append(f"{rel}:{line} {module}")
            private += [f"{rel}:{line} {module}.{name}" for name in names if name.startswith("_")]
    assert not undeclared, ("interleaved imports trunk modules outside INTERLEAVED_MAY_IMPORT:\n  "
                            + "\n  ".join(undeclared))
    assert not private, "interleaved imports private trunk names:\n  " + "\n  ".join(private)


# ---------------------------------------------------------------------------
# The retired compiler (AGENTS.md) stays retired: its source trees do not
# exist and no file imports them. A static scan replaces the former
# subprocess probes, which could only fail once a retired path was recreated.
# ---------------------------------------------------------------------------

RETIRED_PATHS = (
    "core/easycrypt/analysis",
    "core/easycrypt/audit",
    "core/easycrypt/search",
    "core/easycrypt/session_agent_view.py",
    "core/easycrypt/session_prover_workspace_view.py",
    "core/easycrypt/session_workspace_view_manager.py",
    "workflow/proof_management/analyzers",
    "workflow/agents/proof_planner.py",
    "workflow/schemas/proof_plan.py",
    "tools/audit_harness",
    "tools/panel_audit",
    "playground",
)
RETIRED_MODULE_PREFIXES = (
    "core.easycrypt.analysis",
    "core.easycrypt.audit",
    "core.easycrypt.search",
    "core.easycrypt.session_agent_view",
    "core.easycrypt.session_prover_workspace_view",
    "core.easycrypt.session_workspace_view_manager",
    "workflow.proof_management.analyzers",
    "workflow.agents.proof_planner",
    "workflow.schemas.proof_plan",
    "workflow.surface_",
    "tools.audit_harness",
    "tools.panel_audit",
    "playground",
)


def test_retired_compiler_modules_are_absent_and_never_imported():
    present = [path for path in RETIRED_PATHS if (_REPO / path).exists()]
    present += [str(p.relative_to(_REPO)) for p in (_REPO / "workflow").glob("surface_*")]
    assert not present, "retired compiler paths exist again:\n  " + "\n  ".join(present)
    offenders = []
    for path in _python_files("core", "workflow", "eval_suite", "tools", "experiments", "scripts", "tests"):
        for module, _names, line in _imports(path):
            if any(module == p or module.startswith(p if p.endswith("_") else p + ".")
                   for p in RETIRED_MODULE_PREFIXES):
                offenders.append(f"{path.relative_to(_REPO)}:{line} {module}")
    assert not offenders, "imports of retired compiler modules:\n  " + "\n  ".join(offenders)
