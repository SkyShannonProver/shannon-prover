from __future__ import annotations

from pathlib import Path

import pytest

from core.easycrypt.eval_source_prep import prepare_eval_source
from workflow.proof_tool.easycrypt_source_resource import (
    EasyCryptSourceResource,
    SOURCE_READ_MAX_LINES,
    SOURCE_RESOURCE_MANIFEST_ENV,
)


def _resource(tmp_path: Path):
    project = tmp_path / "repo"
    task = project / "task"
    task.mkdir(parents=True)
    target = task / "Target.ec"
    target.write_text(
        "require \"Sibling\".\n"
        "lemma helper : true.\nproof.\n  trivial.\nqed.\n\n"
        "lemma target : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    (task / "Sibling.eca").write_text(
        "lemma sibling_helper : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    theories = project / "easycrypt-src" / "theories"
    theories.mkdir(parents=True)
    (theories / "Distr.ec").write_text(
        "lemma mu_ge0 : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    prepared = prepare_eval_source(
        source_file=target,
        target_lemma="target",
        output_dir=project / "artifacts" / "eval_source",
        copy_root=task,
        strip_proofs=True,
    )
    events: list[dict] = []
    resource = EasyCryptSourceResource.from_environment(
        project_root=project,
        source_file=prepared.isolated_file.relative_to(project),
        target_lemma="target",
        include_dir=theories.relative_to(project),
        environ={
            SOURCE_RESOURCE_MANIFEST_ENV: str(
                (project / "artifacts" / "eval_source" / "source_manifest.json")
                .relative_to(project)
            )
        },
        emit=events.append,
    )
    assert resource is not None
    return project, prepared, resource, events


def test_manager_source_resource_reads_only_attested_task_and_theories(
    tmp_path: Path,
) -> None:
    project, prepared, resource, events = _resource(tmp_path)

    target = resource.read({
        "path": str(prepared.isolated_file.relative_to(project)),
        "start_line": 1,
        "end_line": 20,
    }, call_id="call-target")
    assert not target.is_error
    assert "— lines 1-" in target.text
    assert "1 | require \"Sibling\"." in target.text
    assert "admit." in target.text
    assert "trivial." not in target.text
    assert "Target.ec" in target.text

    sibling = resource.read({
        "path": str(
            (prepared.isolated_root / "Sibling.eca").relative_to(project)
        ),
    })
    assert not sibling.is_error
    assert "sibling_helper" in sibling.text

    theory = resource.read({
        "path": "easycrypt-src/theories/Distr.ec",
    })
    assert not theory.is_error
    assert "mu_ge0" in theory.text
    assert [event["status"] for event in events] == [
        "served", "served", "served"
    ]


def test_manager_source_resource_renders_copy_ready_source_map(
    tmp_path: Path,
) -> None:
    project, prepared, resource, _events = _resource(tmp_path)

    source_map = resource.render_source_map()

    target_path = prepared.isolated_file.relative_to(project).as_posix()
    sibling_path = (
        prepared.isolated_root / "Sibling.eca"
    ).relative_to(project).as_posix()
    assert f"`{target_path}` — active target" in source_map
    assert f"`{sibling_path}`" in source_map
    assert "`easycrypt-src/theories/`" in source_map
    assert resource.target_path == target_path
    assert resource.target_sha256


def test_manager_source_resource_rejects_escape_and_manifest_drift(
    tmp_path: Path,
) -> None:
    project, prepared, resource, events = _resource(tmp_path)
    outside = project / "easycrypt-src" / "examples" / "Answer.ec"
    outside.parent.mkdir(parents=True)
    outside.write_text("lemma answer : true.\n", encoding="utf-8")

    escaped = resource.read({"path": "easycrypt-src/examples/Answer.ec"})
    assert escaped.is_error
    assert "outside" in escaped.text

    absolute = resource.read({"path": str(outside.resolve())})
    assert absolute.is_error
    assert "repository-relative" in absolute.text

    prepared.isolated_file.write_text(
        prepared.isolated_file.read_text(encoding="utf-8") + "\n(* drift *)\n",
        encoding="utf-8",
    )
    drifted = resource.read({
        "path": str(prepared.isolated_file.relative_to(project)),
    })
    assert drifted.is_error
    assert "drifted" in drifted.text
    assert [event["status"] for event in events] == [
        "rejected", "rejected", "rejected"
    ]


def test_manager_source_resource_bounds_line_ranges(tmp_path: Path) -> None:
    project, prepared, resource, _events = _resource(tmp_path)
    path = str(prepared.isolated_file.relative_to(project))

    invalid = resource.read({
        "path": path,
        "start_line": 1,
        "end_line": SOURCE_READ_MAX_LINES + 1,
    })
    assert invalid.is_error
    assert "at most" in invalid.text

    unknown = resource.read({"path": path, "grep": "lemma"})
    assert unknown.is_error
    assert "unknown fields" in unknown.text

    first_line = resource.read({
        "path": path,
        "start_line": 1,
        "end_line": 1,
    })
    assert first_line.text.endswith(
        "More lines available; continue at start_line=2."
    )


def test_manager_source_search_returns_bounded_copy_ready_lexical_matches(
    tmp_path: Path,
) -> None:
    project, prepared, resource, events = _resource(tmp_path)

    task = resource.search({
        "query": "lemma",
        "scope": "task",
        "max_results": 2,
        "context_lines": 1,
    }, call_id="search-task")
    assert not task.is_error
    assert "Literal EasyCrypt source search" in task.text
    assert "Target.ec:" in task.text
    assert "Sibling.eca:" in task.text
    assert "lexical candidates, not resolved declarations" in task.text

    library = resource.search({
        "query": "MU_GE0",
        "scope": "libraries",
        "case_sensitive": False,
    }, call_id="search-library")
    assert not library.is_error
    assert "easycrypt-src/theories/Distr.ec:1: lemma mu_ge0" in library.text

    target_path = prepared.isolated_file.relative_to(project).as_posix()
    exact_file = resource.search({
        "query": "target",
        "path": target_path,
    })
    assert not exact_file.is_error
    assert f"{target_path}:" in exact_file.text
    assert [event["event"] for event in events] == [
        "easycrypt.source_resource.search",
        "easycrypt.source_resource.search",
        "easycrypt.source_resource.search",
    ]
    assert events[1]["query"] == "MU_GE0"
    assert events[1]["locations"] == ["easycrypt-src/theories/Distr.ec:1"]


def test_manager_source_search_rejects_regex_escape_and_drift(
    tmp_path: Path,
) -> None:
    project, prepared, resource, _events = _resource(tmp_path)

    literal = resource.search({"query": "mu_.*", "scope": "libraries"})
    assert not literal.is_error
    assert "0 matches" in literal.text

    escaped = resource.search({
        "query": "lemma",
        "path": "easycrypt-src/examples/Answer.ec",
    })
    assert escaped.is_error
    assert "outside" in escaped.text

    prepared.isolated_file.write_text(
        prepared.isolated_file.read_text(encoding="utf-8") + "\n(* drift *)\n",
        encoding="utf-8",
    )
    drifted = resource.search({"query": "target", "scope": "task"})
    assert drifted.is_error
    assert "drifted" in drifted.text


def test_manager_exact_declaration_resolution_is_native_and_non_mutating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _project, _prepared, resource, events = _resource(tmp_path)
    calls: list[tuple[tuple[str, ...], Path, tuple[Path, ...]]] = []

    def resolve(symbols, context_file, include_dirs, *, timeout=60.0):
        calls.append((tuple(symbols), context_file, tuple(include_dirs)))
        return {
            "Distr.mu_ge0": {
                "requested": "Distr.mu_ge0",
                "status": "resolved",
                "resolved": "Distr.mu_ge0",
                "kind": "lemma",
                "body": "lemma mu_ge0 (d : 'a distr) : 0%r <= mu d predT.",
                "error": "",
            },
            "Distr.missing": {
                "requested": "Distr.missing",
                "status": "miss",
                "resolved": "",
                "kind": "",
                "body": "",
                "error": "",
            },
        }

    monkeypatch.setattr(
        "core.easycrypt.compiler_namespace_adapter.load_exact_declarations",
        resolve,
    )
    found = resource.resolve_declaration(
        {"symbol": "Distr.mu_ge0"}, call_id="resolve-found"
    )
    assert not found.is_error
    assert "EasyCrypt-native declaration resolved" in found.text
    assert "resolved: `Distr.mu_ge0`" in found.text
    assert "current proof state remains owned" in found.text

    missing = resource.resolve_declaration(
        {"symbol": "Distr.missing"}, call_id="resolve-missing"
    )
    assert not missing.is_error
    assert "did not resolve the exact declaration" in missing.text

    invalid = resource.resolve_declaration({"symbol": "mu_ge0; print secret"})
    assert invalid.is_error
    assert "exact EasyCrypt identifier" in invalid.text
    assert calls[0][0] == ("Distr.mu_ge0",)
    assert calls[0][1] == resource.isolated_file
    assert calls[0][2] == (resource.isolated_root, *resource.include_roots)
    assert [event["status"] for event in events] == [
        "resolved", "miss", "rejected"
    ]
