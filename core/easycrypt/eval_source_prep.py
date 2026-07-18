"""Canonical evaluation source preparation.

Evaluation runs use an isolated source copy whose proof bodies are stripped
before the prover/agent can read them.  This module owns that contract:

    original project -> isolated proof-stripped project copy + manifest

Callers should not hand-edit target proof blocks.  The suite runner, narrative
tooling, and legacy prover paths all depend on the same proof-stripping core.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.lemma_decls import lemma_decl_lines, lemma_decl_matches
from core.easycrypt.proof_strip import replace_proofs


SOURCE_PREP_KIND = "eval_source_prep"
SOURCE_PREP_SCHEMA_VERSION = 1
PROOF_STRIPPED_PROJECT_CONTRACT = "proof_stripped_project"
RAW_ISOLATED_SOURCE_CONTRACT = "raw_isolated_source"


@dataclass(frozen=True)
class EvalSourcePrepResult:
    """Prepared source metadata returned to suite/orchestrator callers."""

    source_file: Path
    copy_root: Path
    isolated_file: Path
    isolated_root: Path
    manifest: dict[str, Any]


def prepare_eval_source(
    *,
    source_file: Path,
    target_lemma: str,
    output_dir: Path,
    copy_root: Path | None = None,
    strip_proofs: bool = True,
    write_manifest: bool = True,
) -> EvalSourcePrepResult:
    """Copy a target project/file into ``output_dir`` and apply eval stripping.

    ``strip_proofs=True`` is the canonical eval contract: every ``.ec``/``.eca``
    file in the isolated copy has proof bodies replaced with ``admit`` shells.
    The target lemma name is still required to be unique in the target file,
    because session open, write-back, and no-admit checks are name based.
    """
    source_file = Path(source_file)
    copy_root = Path(copy_root) if copy_root is not None else source_file
    output_dir = Path(output_dir)

    if not source_file.exists():
        raise FileNotFoundError(f"source file does not exist: {source_file}")
    if not copy_root.exists():
        raise FileNotFoundError(f"copy_root does not exist: {copy_root}")
    if copy_root.is_dir():
        rel_source = source_file.relative_to(copy_root)
        isolated_root = output_dir / "source" / copy_root.name
    else:
        rel_source = Path(source_file.name)
        isolated_root = output_dir / "source"

    isolated_file = isolated_root / rel_source
    assert_unique_eval_target(source_file, target_lemma)
    _copy_isolated_source(source_file, copy_root, isolated_root, isolated_file)

    stripped_files: list[dict[str, Any]] = []
    if strip_proofs:
        strip_root = isolated_root if copy_root.is_dir() else isolated_file.parent
        stripped_files = strip_eval_source_tree(strip_root)
        _assert_target_is_admit_shell(isolated_file, target_lemma)

    manifest = _source_manifest(
        source_file=source_file,
        copy_root=copy_root,
        isolated_file=isolated_file,
        isolated_root=isolated_root,
        target_lemma=target_lemma,
        strip_proofs=strip_proofs,
        stripped_files=stripped_files,
    )
    if write_manifest:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "source_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return EvalSourcePrepResult(
        source_file=source_file,
        copy_root=copy_root,
        isolated_file=isolated_file,
        isolated_root=isolated_root,
        manifest=manifest,
    )


def assert_unique_eval_target(source_file: Path, target_lemma: str) -> None:
    """Fail fast when a target lemma name is absent or ambiguous."""
    content = Path(source_file).read_text(encoding="utf-8")
    lines = lemma_decl_lines(content, target_lemma)
    if not lines:
        raise ValueError(f"lemma '{target_lemma}' is not declared in {source_file}")
    if len(lines) > 1:
        raise ValueError(
            f"lemma '{target_lemma}' is declared {len(lines)} times in "
            f"{source_file} (lines {', '.join(str(ln) for ln in lines)}); "
            "evaluation source prep requires a unique target declaration so "
            "session open, write-back, and no-admit checks all bind the same "
            "lemma. Rename the duplicate or split the file."
        )


def strip_eval_source_tree(root: Path) -> list[dict[str, Any]]:
    """Proof-strip every EasyCrypt source file under ``root``.

    Returns deterministic per-file metadata for the source manifest.
    """
    root = Path(root)
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix in {".ec", ".eca"}
    )
    out: list[dict[str, Any]] = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        stripped, count = replace_proofs(raw)
        if stripped != raw:
            path.write_text(stripped, encoding="utf-8")
        out.append({
            "path": str(path.relative_to(root)),
            "proofs_replaced": int(count),
            "raw_sha256": _sha256_text(raw),
            "stripped_sha256": _sha256_text(stripped),
        })
    return out


def replace_target_proof_with_admit(path: Path, lemma_name: str) -> bool:
    """Replace one target proof with an admit shell.

    This is for legacy repair/precheck paths.  Evaluation source preparation
    should use ``prepare_eval_source(strip_proofs=True)`` instead.
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    block = find_target_proof_block(content, lemma_name)
    if block is None:
        return False
    start, end = block
    indent = _leading_indent(content[start:end])
    replacement = f"{indent}proof.\n{indent}  admit.\n{indent}qed."
    path.write_text(content[:start] + replacement + content[end:], encoding="utf-8")
    return True


def find_target_proof_block(
    content: str,
    lemma_name: str,
) -> tuple[int, int] | None:
    """Find a target proof block by name in EasyCrypt source text."""
    matches = lemma_decl_matches(content, lemma_name)
    if not matches:
        return None

    def needs_proving(match: Any) -> bool:
        after = content[match.end():match.end() + 500]
        return "admit" in after[:300] or "proof." in after[:300]

    match = next((m for m in matches if needs_proving(m)), matches[0])
    rest = content[match.start():]
    next_start = _next_declaration_offset(rest)
    if next_start is not None:
        rest = rest[:next_start]

    proof_pos = rest.find("proof.")
    if proof_pos >= 0:
        qed_pos = rest.find("qed.", proof_pos)
        if qed_pos >= 0:
            return match.start() + proof_pos, match.start() + qed_pos + len("qed.")

    admit_pos = _standalone_admit_offset(rest)
    if admit_pos is not None:
        return match.start() + admit_pos[0], match.start() + admit_pos[1]
    return None


def _copy_isolated_source(
    source_file: Path,
    copy_root: Path,
    isolated_root: Path,
    isolated_file: Path,
) -> None:
    if copy_root.is_file():
        isolated_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, isolated_file)
        return
    shutil.copytree(
        copy_root,
        isolated_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            ".ec_session_*",
            "*.eco",
            "__pycache__",
        ),
    )
    if not isolated_file.exists():
        raise FileNotFoundError(f"isolated target file was not copied: {isolated_file}")


def _assert_target_is_admit_shell(path: Path, lemma_name: str) -> None:
    content = Path(path).read_text(encoding="utf-8")
    block = find_target_proof_block(content, lemma_name)
    if block is None:
        raise ValueError(
            f"target lemma '{lemma_name}' in {path} did not produce a proof shell "
            "after evaluation proof stripping"
        )
    start, end = block
    if "admit." not in content[start:end]:
        raise ValueError(
            f"target lemma '{lemma_name}' in {path} is not admit-only after "
            "evaluation proof stripping"
        )


def _source_manifest(
    *,
    source_file: Path,
    copy_root: Path,
    isolated_file: Path,
    isolated_root: Path,
    target_lemma: str,
    strip_proofs: bool,
    stripped_files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_PREP_SCHEMA_VERSION,
        "kind": SOURCE_PREP_KIND,
        "source_contract": (
            PROOF_STRIPPED_PROJECT_CONTRACT if strip_proofs
            else RAW_ISOLATED_SOURCE_CONTRACT
        ),
        "original_file": str(source_file),
        "copy_root": str(copy_root),
        "isolated_file": str(isolated_file),
        "isolated_root": str(isolated_root),
        "target_lemma": str(target_lemma),
        "strip_proofs": bool(strip_proofs),
        "stripped_file_count": len(stripped_files),
        "proofs_replaced_total": sum(
            int(item.get("proofs_replaced") or 0) for item in stripped_files
        ),
        "stripped_files": stripped_files,
    }


def _next_declaration_offset(text: str) -> int | None:
    lines = text.splitlines(keepends=True)
    offset = 0
    for idx, line in enumerate(lines):
        if idx > 0 and _is_bounded_declaration_start(line):
            return offset
        offset += len(line)
    return None


def _is_bounded_declaration_start(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(line) - len(line.lstrip(" ")) > 2:
        return False
    heads = (
        "local lemma ",
        "local theorem ",
        "local equiv ",
        "local hoare ",
        "local phoare ",
        "lemma ",
        "theorem ",
        "equiv ",
        "hoare ",
        "phoare ",
        "axiom ",
        "op ",
        "type ",
        "module ",
        "clone ",
        "section",
        "end section",
    )
    if not stripped.startswith(heads):
        return False
    # A real declaration names what it declares. Statement *continuation*
    # lines can start with the anonymous judgment forms `equiv [ ... ]`,
    # `hoare [ ... ]`, `phoare [ ... ]` at low indent (e.g. Perm3.simul_bad's
    # `initialisation ... => \n equiv [ ... ]`); treating those as the next
    # declaration truncates the proof-block search before `proof.` and makes
    # the target look shell-less. Require an identifier after the keyword.
    m = re.match(
        r"(?:local\s+)?(?:lemma|theorem|equiv|hoare|phoare)\s+(?P<next>\S)",
        stripped,
    )
    if m and not (m.group("next").isalpha() or m.group("next") == "_"):
        return False
    return True


def _standalone_admit_offset(text: str) -> tuple[int, int] | None:
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == "admit.":
            start = offset + line.index("admit.")
            return start, start + len("admit.")
        offset += len(line)
    return None


def _leading_indent(text: str) -> str:
    line = text.splitlines()[0] if text.splitlines() else ""
    return line[:len(line) - len(line.lstrip(" \t"))]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "EvalSourcePrepResult",
    "PROOF_STRIPPED_PROJECT_CONTRACT",
    "RAW_ISOLATED_SOURCE_CONTRACT",
    "SOURCE_PREP_KIND",
    "assert_unique_eval_target",
    "find_target_proof_block",
    "prepare_eval_source",
    "replace_target_proof_with_admit",
    "strip_eval_source_tree",
]
