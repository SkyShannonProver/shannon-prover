"""Bounded EasyCrypt namespace adapter for compiler resource loading.

This is manager-internal compiler plumbing. It asks EasyCrypt itself to
``print theory`` or ``print`` an exact qualified symbol, then extracts only the
declaration names/bodies requested by a bounded compiler load plan. It does not
guess clone prefixes, scan source text as a semantic fallback, search sibling
lemmas, or render agent-facing lookup advice.

EasyCrypt currently exposes these queries through its command language rather
than a stable external JSON API. The adapter therefore brackets native printer
output with impossible-name anchors. The native environment remains the name
resolution and elaboration authority; this module only frames and parses the
printer response.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from core.easycrypt.ec_env import get_ec_env


_ANCHOR = "__shannon_compiler_namespace_anchor_zXyQ__"
_IDENTIFIER = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*$"
)
_SECTION_HEADER = re.compile(
    r"^\* In \[(modules|theories|operators or predicates|lemmas or axioms|"
    r"module types|types)\]:\s*$",
    re.MULTILINE,
)
_NO_SUCH_OBJECT = re.compile(
    r"^\s*\|?\s*no such object in any category\s*$", re.MULTILINE
)
_THEORY_DECLARATION = re.compile(
    r"^(?:\s*\(\*\s*import\s*\*\)\s*)?\s*(?:local\s+)?"
    r"(module(?:\s+type)?|theory|op|pred|abbrev|lemma|axiom|type)\s+"
    r"([A-Za-z_][A-Za-z0-9_']*)",
    re.MULTILINE,
)


def list_theory_members(
    scope: str,
    context_file: Path,
    include_dirs: Iterable[Path],
    *,
    timeout: float = 60,
) -> dict:
    """Return declaration names from EasyCrypt's exact ``print theory``."""

    normalized = str(scope or "").strip()
    if not _IDENTIFIER.fullmatch(normalized):
        return _member_failure(normalized, "error", "invalid theory identifier")
    if not context_file.is_file():
        return _member_failure(normalized, "error", "context file is unavailable")
    probe = _write_probe(
        context_file,
        [f"print {_ANCHOR}.", f"print theory {normalized}.", f"print {_ANCHOR}."],
    )
    try:
        output = _run_easycrypt(probe, include_dirs, timeout=timeout, emacs=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _member_failure(normalized, "error", str(exc))
    finally:
        _unlink(probe)
    anchors = list(_NO_SUCH_OBJECT.finditer(output))
    if len(anchors) < 2:
        return _member_failure(normalized, "miss", "EasyCrypt did not print the theory")
    block = output[anchors[-2].end():anchors[-1].start()]
    cleaned = _strip_emacs_prefixes(block)
    base = normalized.split(".")[-1]
    if not re.search(
        rf"\b(?:local\s+)?theory\s+{re.escape(base)}\b", cleaned
    ):
        return _member_failure(normalized, "miss", "name is not a printable theory")
    by_kind: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for match in _THEORY_DECLARATION.finditer(cleaned):
        kind = match.group(1).replace("module type", "module_type")
        kind = kind.replace("module_type", "module type")
        name = match.group(2)
        key = kind, name
        if key in seen or (kind == "theory" and name == base):
            continue
        seen.add(key)
        by_kind.setdefault(kind, []).append(name)
    return {
        "scope": normalized,
        "status": "ok",
        "by_kind": by_kind,
        "total": sum(len(names) for names in by_kind.values()),
        "error": "",
    }


def load_exact_declarations(
    symbols: Iterable[str],
    context_file: Path,
    include_dirs: Iterable[Path],
    *,
    timeout: float = 60,
) -> dict[str, dict]:
    """Ask EasyCrypt to print exactly the supplied qualified symbols.

    Misses remain misses. In particular, this function never adds clone
    prefixes or substitutes a source-scanned declaration.
    """

    requested = tuple(dict.fromkeys(str(item or "").strip() for item in symbols))
    results: dict[str, dict] = {}
    valid = []
    for symbol in requested:
        if not _IDENTIFIER.fullmatch(symbol):
            results[symbol] = {
                "requested": symbol,
                "status": "error",
                "resolved": "",
                "kind": "",
                "body": "",
                "error": "invalid EasyCrypt identifier",
            }
        else:
            valid.append(symbol)
    if not valid:
        return results
    if not context_file.is_file():
        return {
            **results,
            **{
                symbol: {
                    "requested": symbol,
                    "status": "error",
                    "resolved": "",
                    "kind": "",
                    "body": "",
                    "error": "context file is unavailable",
                }
                for symbol in valid
            },
        }
    commands: list[str] = []
    for symbol in valid:
        commands.extend((f"print {_ANCHOR}.", f"print {symbol}."))
    commands.append(f"print {_ANCHOR}.")
    probe = _write_probe(context_file, commands)
    try:
        output = _run_easycrypt(probe, include_dirs, timeout=timeout, emacs=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            **results,
            **{
                symbol: {
                    "requested": symbol,
                    "status": "error",
                    "resolved": "",
                    "kind": "",
                    "body": "",
                    "error": str(exc),
                }
                for symbol in valid
            },
        }
    finally:
        _unlink(probe)
    blocks = _split_exact_print_blocks(output, len(valid))
    for index, symbol in enumerate(valid):
        parsed = _parse_declaration_block(
            blocks[index] if index < len(blocks) else "", symbol
        )
        results[symbol] = parsed or {
            "requested": symbol,
            "status": "miss",
            "resolved": "",
            "kind": "",
            "body": "",
            "error": "",
        }
    return results


def _write_probe(context_file: Path, commands: list[str]) -> Path:
    source = context_file.read_text(encoding="utf-8", errors="replace")
    descriptor, raw_path = tempfile.mkstemp(prefix="shannon_ec_namespace_", suffix=".ec")
    path = Path(raw_path)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(source)
        if not source.endswith("\n"):
            stream.write("\n")
        stream.write("\n".join(commands))
        stream.write("\n")
    return path


def _run_easycrypt(
    probe: Path,
    include_dirs: Iterable[Path],
    *,
    timeout: float,
    emacs: bool,
) -> str:
    command = ["easycrypt", "cli", "-emacs"] if emacs else ["easycrypt"]
    for directory in include_dirs:
        command.extend(("-I", str(directory)))
    if emacs:
        with probe.open("rb") as stream:
            completed = subprocess.run(
                command,
                stdin=stream,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=get_ec_env(),
            )
    else:
        completed = subprocess.run(
            [*command, str(probe)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=get_ec_env(),
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise OSError(
            "EasyCrypt namespace query exited nonzero"
            + (f": {detail[-2000:]}" if detail else "")
        )
    return completed.stdout


def _split_exact_print_blocks(output: str, count: int) -> list[str]:
    """Split anchor/target output without interpreting a missed target."""

    anchors = list(_NO_SUCH_OBJECT.finditer(output))
    if not anchors:
        return [""] * count
    blocks: list[str] = []
    cursor = 0
    for _ in range(count):
        if cursor >= len(anchors):
            blocks.append("")
            continue
        start = anchors[cursor].end()
        cursor += 1
        if cursor >= len(anchors):
            blocks.append(output[start:])
            continue
        between = output[start:anchors[cursor].start()]
        # A hit contains a printer section before the next anchor. A miss emits
        # its own no-such-object occurrence, so the region is empty and that
        # occurrence is consumed as the target before the following anchor.
        if _SECTION_HEADER.search(between):
            blocks.append(between)
        else:
            blocks.append("")
            cursor += 1
    return blocks


def _parse_declaration_block(block: str, symbol: str) -> dict | None:
    base = symbol.split(".")[-1]
    patterns = (
        rf"\bmodule\s+(?:type\s+)?{re.escape(base)}\s*[\(={{ ]",
        rf"\b(?:local\s+)?theory\s+{re.escape(base)}\.",
        rf"\b(?:local\s+)?(?:op|pred|abbrev)\s+{re.escape(base)}\b",
        rf"\b(?:local\s+)?(?:lemma|equiv|axiom)\s+{re.escape(base)}[:\s\[]",
        rf"\btype\s+{re.escape(base)}\b",
    )
    if not block or not any(re.search(pattern, block) for pattern in patterns):
        return None
    header = _SECTION_HEADER.search(block)
    section = header.group(1) if header else ""
    kind = {
        "modules": "module",
        "theories": "theory",
        "operators or predicates": "operator",
        "lemmas or axioms": "lemma",
        "module types": "module_type",
        "types": "type",
    }.get(section, "declaration")
    # The ``* In [...]`` line is EasyCrypt display metadata, not declaration
    # syntax. Keep it for kind classification above, but never hand it to a
    # compiler feature or agent as copyable source.
    body = block[header.end():].strip() if header else block.strip()
    return {
        "requested": symbol,
        "status": "resolved",
        "resolved": symbol,
        "kind": kind,
        "body": body,
        "error": "",
    }


def _strip_emacs_prefixes(block: str) -> str:
    return "\n".join(
        line[2:] if line.startswith(("| ", "+ ")) else line
        for line in block.splitlines()
    )


def _member_failure(scope: str, status: str, error: str) -> dict:
    return {
        "scope": scope,
        "status": status,
        "by_kind": {},
        "total": 0,
        "error": error,
    }


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
