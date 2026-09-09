"""Package an explicitly selected proof library for the static browser.

This is a lexical source-navigation index, not an EasyCrypt semantic service.
Verification claims come from the curated catalog, never from finding ``qed``.
No raw run directory is scanned or copied.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil


def mask_noncode(source: str) -> str:
    """Mask nested comments and quoted strings without moving source offsets."""
    out = list(source)
    depth, quoted, i = 0, False, 0
    while i < len(source):
        pair = source[i:i + 2]
        if not quoted and pair == "(*":
            depth += 1
            out[i:i + 2] = "  "
            i += 2
            continue
        if depth and pair == "*)":
            depth -= 1
            out[i:i + 2] = "  "
            i += 2
            continue
        if not depth and source[i] == '"':
            quoted = not quoted
            out[i] = " "
        elif quoted and source[i] == "\\" and i + 1 < len(source):
            out[i:i + 2] = "  "
            i += 2
            continue
        elif (depth or quoted) and source[i] != "\n":
            out[i] = " "
        i += 1
    return "".join(out)


def index_source(source: str, file_id: str, role: str) -> dict:
    masked = mask_noncode(source)
    candidates = list(re.finditer(
        r"(?m)^[ \t]*(?:(?:local|global|export)[ \t]+)?lemma[ \t]+([A-Za-z_][A-Za-z0-9_']*)",
        masked,
    ))
    # A clone substitution such as `lemma addrA <- addbA` is not a new lemma.
    declarations = [m for m in candidates
                    if not re.match(r"\s*(?:<-|=)", masked[m.end():])]
    line_at = lambda offset: source.count("\n", 0, offset) + 1
    begin = source.find("SCRATCHPAD BEGIN")
    end = source.find("SCRATCHPAD END", max(0, begin))
    lemmas = []
    for i, match in enumerate(declarations):
        limit = declarations[i + 1].start() if i + 1 < len(declarations) else len(source)
        chunk = masked[match.start():limit]
        proof = re.search(r"\bproof(?:\s+strict)?\.", chunk)
        inline = re.search(r"\bby\b", chunk)
        finish = re.search(r"\bqed\.", chunk[proof.end():]) if proof else None
        item = {"id": f"{file_id}-{line_at(match.start())}", "name": match[1],
                "start": line_at(match.start()), "end": line_at(match.start()),
                "proofStart": None, "bodyLines": None, "origin": role}
        if role == "Completed target file":
            if match[1] == "conclusion":
                item["origin"] = "Fixed target · agent-written proof"
            elif begin >= 0 and begin < match.start() < end:
                item["origin"] = "Agent-added helper in the designated scratchpad"
            else:
                item["origin"] = "Declaration in the supplied model"
        if inline and (not proof or inline.start() < proof.start()):
            terminator = re.search(r"\.(?=\s|$)", chunk[inline.end():])
            if terminator:
                proof_offset = match.start() + inline.start()
                finish_offset = match.start() + inline.end() + terminator.end()
                item.update(proofStart=line_at(proof_offset), end=line_at(finish_offset - 1),
                            proofForm="inline",
                            bodyLines=len(source[proof_offset:finish_offset].splitlines()),
                            statement=source[match.start():proof_offset].rstrip(),
                            proof=source[proof_offset:finish_offset])
        elif proof and finish:
            proof_offset = match.start() + proof.start()
            finish_offset = match.start() + proof.end() + finish.start()
            item.update(proofStart=line_at(proof_offset), end=line_at(finish_offset + 3),
                        bodyLines=len(source[match.start() + proof.end():finish_offset].strip().splitlines()))
            # Preserve both halves even when proof. is on the statement's line.
            item["statement"] = source[match.start():proof_offset].rstrip()
            item["proof"] = source[proof_offset:finish_offset + 4]
        lemmas.append(item)
    return {"lines": source.splitlines(), "lemmas": lemmas}


def confined(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or not path.parts:
        raise ValueError(f"Invalid proof-library path: {relative}")
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Proof-library path escapes its root: {relative}")
    if any(p.is_symlink() for p in [target, *target.parents] if p != root.parent):
        raise ValueError(f"Symlinks are not proof-library inputs: {relative}")
    return target


def validate_process_story(story: dict, indexed: dict, default_file: str) -> None:
    """Validate curated narrative and links; this does not certify its claims."""
    def require_text(obj: dict, *keys: str) -> None:
        if any(not isinstance(obj.get(key), str) or not obj[key].strip() for key in keys):
            raise ValueError("Missing process-story text")

    def check_reference(ref: dict) -> None:
        matches = [lemma for lemma in indexed.get(ref.get("file"), {}).get("lemmas", [])
                   if lemma["name"] == ref.get("lemma")]
        if len(matches) != 1:
            raise ValueError(f"Unresolved or ambiguous process-story lemma: {ref}")

    if story.get("schema_version") != 1 or not story.get("stages"):
        raise ValueError("Unsupported process story")
    require_text(story, "title", "deck", "orderNote")
    require_text(story["provenance"], "commit", "tracePath", "blob", "note")
    for stat in story["stats"]:
        require_text(stat, "value", "label")
    for stage in story["stages"]:
        require_text(stage, "title", "work")
        if not stage.get("paragraphs") or any(not isinstance(p, str) or not p.strip()
                                               for p in stage["paragraphs"]):
            raise ValueError("Empty process-story stage")
        for ref in stage["references"]:
            check_reference(ref)
        for excerpt in stage["evidence"]:
            require_text(excerpt, "text", "item")
            if excerpt["kind"] not in {"agent_message", "check"} or not isinstance(excerpt["line"], int) or excerpt["line"] < 1:
                raise ValueError("Invalid process-story trace reference")
    require_text(story["jobs"], "note", "sourceNote")
    seen_jobs = set()
    for job in story["jobs"]["merged"] + story["jobs"]["other"]:
        require_text(job, "id", "lemma", "duration", "result")
        if job["id"] in seen_jobs:
            raise ValueError("Duplicate process-story job")
        seen_jobs.add(job["id"])
        check_reference({"file": default_file, "lemma": job["lemma"]})


def package_library(pack: Path | None, output: Path) -> int:
    catalog = {"schema_version": 1, "cases": []}
    pending = []
    if pack is not None:
        pack = pack.resolve()
        catalog = json.loads((pack / "catalog.json").read_text(encoding="utf-8"))
        if catalog.get("schema_version") != 1 or not isinstance(catalog.get("cases"), list):
            raise ValueError("Unsupported proof-library catalog")
        seen_cases = set()
        for case in catalog["cases"]:
            case_id = case["id"]
            if not re.fullmatch(r"[a-z0-9-]+", case_id) or case_id in seen_cases:
                raise ValueError("Invalid or duplicate case id")
            seen_cases.add(case_id)
            indexed, seen_files, seen_paths = {}, set(), set()
            for item in case["files"]:
                file_id = item["id"]
                if not re.fullmatch(r"[a-z0-9-]+", file_id) or file_id in seen_files:
                    raise ValueError("Invalid or duplicate file id")
                if item["path"] in seen_paths:
                    raise ValueError("Duplicate proof-library output path")
                seen_files.add(file_id)
                seen_paths.add(item["path"])
                confined(output, item["path"])
                if Path(item["path"]).suffix not in {".ec", ".eca"}:
                    raise ValueError("Proof-library downloads must be EasyCrypt source files")
                source = confined(pack, item["source"])
                data = source.read_bytes()
                if hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise ValueError(f"Proof-library hash mismatch: {item['path']}")
                relative = f"{case_id}/files/{item['path']}"
                confined(output, relative)
                indexed[file_id] = {**index_source(data.decode("utf-8"), file_id, item["role"]),
                                    "path": item["path"], "role": item["role"],
                                    "sha256": item["sha256"], "download": relative}
                pending.append((source, relative))
            if case["defaultFile"] not in seen_files:
                raise ValueError("Case default file is missing")
            if case.get("process_source"):
                story = json.loads(confined(pack, case["process_source"]).read_text(encoding="utf-8"))
                validate_process_story(story, indexed, case["defaultFile"])
                case["processStory"] = story
            elif "processStory" in case:
                validate_process_story(case["processStory"], indexed, case["defaultFile"])
            pending.append((indexed, f"{case_id}/source.json"))
    # Validate all hashes and paths before producing any files.
    output.mkdir(parents=True, exist_ok=True)
    for content, relative in pending:
        target = confined(output, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, Path):
            shutil.copyfile(content, target)
        else:
            target.write_text(json.dumps(content, ensure_ascii=True) + "\n", encoding="utf-8")
    # Keep archive Git paths and local input locations out of served metadata.
    public_catalog = {**catalog, "cases": [{**{k: v for k, v in case.items() if k != "process_source"}, "files": [
        {k: v for k, v in item.items() if k in {"id", "path", "role", "sha256"}}
        for item in case["files"]]} for case in catalog["cases"]]}
    text = json.dumps(public_catalog, ensure_ascii=True).replace("<", "\\u003c")
    (output / "catalog.js").write_text("window.SHANNON_CASE_STUDIES = " + text + ";\n", encoding="utf-8")
    return len(catalog["cases"])
