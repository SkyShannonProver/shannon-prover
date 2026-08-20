"""Validated read-only boundary for native EasyCrypt proof-state projection.

The OCaml companion replays the manager-owned context and accepted prefix, then
projects the installed EasyCrypt library's typed goal, local declarations, and
program AST.  This module authenticates the replay inputs and runtime, enforces
bounded output, validates the transport schema, and checks canonical goal
identity.  It deliberately does not lower the result into compiler IR.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.native_semantics.companion import (
    NATIVE_STATE_FRAME_PREFIX,
    NativeCompanionIdentity,
    build_and_identify_companion,
    parse_companion_result_frame,
)
from core.easycrypt.session.session_projection import active_goal_hash_from_raw


NATIVE_STATE_PROJECTION_PROTOCOL_VERSION = 2
DEFAULT_MAX_NODES = 4096
DEFAULT_MAX_DEPTH = 128
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_DIR = Path(__file__).resolve().parent
_JUDGMENT_KINDS = frozenset({
    "pure",
    "hoare_function",
    "hoare_statement",
    "bounded_hoare_function",
    "bounded_hoare_statement",
    "expectation_hoare_function",
    "expectation_hoare_statement",
    "equivalence_function",
    "equivalence_statement",
    "eager_equivalence",
    "probability",
})


@dataclass(frozen=True)
class NativeStateProjectionRequest:
    request_id: str
    context_file: Path
    history_file: Path
    include_dirs: tuple[Path, ...]
    expected_goal_identity: str
    expected_context_sha256: str
    expected_history_sha256: str
    max_nodes: int = DEFAULT_MAX_NODES
    max_depth: int = DEFAULT_MAX_DEPTH

    def __post_init__(self) -> None:
        if not self.request_id or self.request_id != self.request_id.strip():
            raise ValueError("native state request requires request_id")
        if not self.expected_goal_identity:
            raise ValueError("native state request requires open goal identity")
        for value in (
            self.expected_context_sha256,
            self.expected_history_sha256,
        ):
            if not _SHA256_RE.fullmatch(value):
                raise ValueError("native state request requires source hashes")
        if type(self.max_nodes) is not int or not 64 <= self.max_nodes <= 100000:
            raise ValueError("native state max_nodes is outside supported range")
        if type(self.max_depth) is not int or not 8 <= self.max_depth <= 512:
            raise ValueError("native state max_depth is outside supported range")

    def runtime_payload(self) -> dict[str, object]:
        return {
            "schema_version": NATIVE_STATE_PROJECTION_PROTOCOL_VERSION,
            "kind": "native_proof_state_projection_request",
            "request_id": self.request_id,
            "context_file": str(self.context_file.resolve()),
            "history_file": str(self.history_file.resolve()),
            "include_dirs": [str(path.resolve()) for path in self.include_dirs],
            "max_nodes": self.max_nodes,
            "max_depth": self.max_depth,
        }


@dataclass(frozen=True)
class NativeStateProjectionResult:
    request_id: str
    goal_before: str
    projection: dict[str, Any]
    runtime_identity: EasyCryptRuntimeIdentity
    companion_identity: NativeCompanionIdentity
    elapsed_ms: int

    def __post_init__(self) -> None:
        if not self.goal_before:
            raise ValueError("native state result requires goal_before")
        if type(self.projection) is not dict:
            raise ValueError("native state result requires projection")
        if self.elapsed_ms < 0:
            raise ValueError("native state result has invalid elapsed time")


def run_native_state_projection(
    request: NativeStateProjectionRequest,
    *,
    runtime_identity: EasyCryptRuntimeIdentity,
    timeout: int = 30,
) -> NativeStateProjectionResult:
    """Project one exact open state without mutating manager session files."""

    if timeout <= 0:
        raise ValueError("native state timeout must be positive")
    context = request.context_file.resolve()
    history = request.history_file.resolve()
    _validate_file_hash(context, request.expected_context_sha256, "context")
    _validate_file_hash(history, request.expected_history_sha256, "history")
    executable, companion = build_and_identify_companion(
        "native_state_projection_adapter",
        runtime_identity,
    )
    payload = json.dumps(
        request.runtime_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    started = time.perf_counter()
    try:
        process = subprocess.run(
            [str(executable)],
            cwd=str(_SOURCE_DIR),
            env=get_ec_env(),
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("native state companion failed to run") from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _validate_file_hash(context, request.expected_context_sha256, "context")
    _validate_file_hash(history, request.expected_history_sha256, "history")
    if process.returncode != 0:
        raise RuntimeError("native state companion exited unsuccessfully")
    if len(process.stdout.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise RuntimeError("native state companion response exceeds byte budget")
    raw = parse_companion_result_frame(
        process.stdout,
        prefix=NATIVE_STATE_FRAME_PREFIX,
    )
    result = _validated_result(
        raw,
        request=request,
        runtime_identity=runtime_identity,
        companion_identity=companion,
        elapsed_ms=elapsed_ms,
    )
    if active_goal_hash_from_raw(result.goal_before) != request.expected_goal_identity:
        raise RuntimeError("native state companion replayed a different goal")
    return result


def validate_native_projection(
    value: object,
    *,
    max_nodes: int,
) -> dict[str, Any]:
    """Validate the version-two typed projection and return a detached copy."""

    if type(value) is not dict:
        raise RuntimeError("native state projection must be an object")
    projection = dict(value)
    _require_exact_keys(projection, {
        "complete",
        "truncation_reasons",
        "node_count",
        "open_goal_count",
        "focused_goal",
        "local_declarations",
    }, "projection")
    if type(projection["complete"]) is not bool:
        raise RuntimeError("native state complete must be boolean")
    reasons = projection["truncation_reasons"]
    if type(reasons) is not list or any(type(item) is not str for item in reasons):
        raise RuntimeError("native state truncation_reasons must be strings")
    if projection["complete"] is not (not reasons):
        raise RuntimeError("native state completeness disagrees with truncation")
    nodes = projection["node_count"]
    if type(nodes) is not int or not 0 <= nodes <= max_nodes:
        raise RuntimeError("native state node_count is invalid")
    goals = projection["open_goal_count"]
    if type(goals) is not int or goals < 1:
        raise RuntimeError("native state requires at least one open goal")
    focused = projection["focused_goal"]
    if type(focused) is not dict:
        raise RuntimeError("native state focused_goal must be an object")
    _require_exact_keys(
        focused,
        {"judgment_kind", "formula", "programs", "procedures"},
        "focused_goal",
    )
    if focused["judgment_kind"] not in _JUDGMENT_KINDS:
        raise RuntimeError("native state judgment_kind is invalid")
    _validate_typed_node(focused["formula"], "formula")
    programs = focused["programs"]
    if type(programs) is not list:
        raise RuntimeError("native state programs must be a list")
    for index, program in enumerate(programs):
        if type(program) is not dict:
            raise RuntimeError(f"native state program[{index}] must be an object")
        _require_exact_keys(
            program,
            {"side", "role", "memory", "statement"},
            f"program[{index}]",
        )
        for field in ("side", "role", "memory"):
            if type(program[field]) is not str or not program[field]:
                raise RuntimeError(f"native state program[{index}].{field} is invalid")
        _validate_statement(program["statement"], f"program[{index}].statement")
    procedures = focused["procedures"]
    if type(procedures) is not list:
        raise RuntimeError("native state procedures must be a list")
    for index, procedure in enumerate(procedures):
        if type(procedure) is not dict:
            raise RuntimeError(f"native state procedure[{index}] must be an object")
        _require_exact_keys(
            procedure,
            {"side", "role", "procedure", "procedure_module"},
            f"procedure[{index}]",
        )
        if any(type(procedure[field]) is not str or not procedure[field]
               for field in ("side", "role", "procedure")):
            raise RuntimeError(f"native state procedure[{index}] is invalid")
        _validate_module_path(
            procedure["procedure_module"],
            f"procedure[{index}].procedure_module",
        )
    locals_value = projection["local_declarations"]
    if type(locals_value) is not list:
        raise RuntimeError("native state local_declarations must be a list")
    for index, declaration in enumerate(locals_value):
        if type(declaration) is not dict:
            raise RuntimeError(f"native state local[{index}] must be an object")
        if declaration.get("index") != index:
            raise RuntimeError("native state local declaration order is invalid")
        if type(declaration.get("name")) is not str or not declaration.get("name"):
            raise RuntimeError(f"native state local[{index}] requires name")
        if declaration.get("kind") not in {
            "variable", "memory", "module", "hypothesis", "abstract_statement"
        }:
            raise RuntimeError(f"native state local[{index}] kind is invalid")
        _validate_local_declaration(declaration, f"local[{index}]")
    return json.loads(json.dumps(projection, ensure_ascii=False))


def _validated_result(
    value: object,
    *,
    request: NativeStateProjectionRequest,
    runtime_identity: EasyCryptRuntimeIdentity,
    companion_identity: NativeCompanionIdentity,
    elapsed_ms: int,
) -> NativeStateProjectionResult:
    if type(value) is not dict:
        raise RuntimeError("native state result must be an object")
    raw = dict(value)
    if raw.get("schema_version") != NATIVE_STATE_PROJECTION_PROTOCOL_VERSION or (
        type(raw.get("schema_version")) is not int
    ):
        raise RuntimeError("native state result schema mismatch")
    if raw.get("kind") != "native_proof_state_projection_result":
        raise RuntimeError("native state result kind mismatch")
    if raw.get("status") != "accepted":
        raise RuntimeError(str(raw.get("message") or "unknown native state failure"))
    _require_exact_keys(raw, {
        "schema_version", "kind", "status", "request_id", "goal_before",
        "limits", "projection",
    }, "result")
    if raw.get("request_id") != request.request_id:
        raise RuntimeError("native state result request_id mismatch")
    if raw.get("limits") != {
        "max_nodes": request.max_nodes,
        "max_depth": request.max_depth,
    }:
        raise RuntimeError("native state result limits mismatch")
    goal_before = raw.get("goal_before")
    if type(goal_before) is not str or not goal_before:
        raise RuntimeError("native state result requires goal_before")
    projection = validate_native_projection(
        raw.get("projection"),
        max_nodes=request.max_nodes,
    )
    return NativeStateProjectionResult(
        request_id=request.request_id,
        goal_before=goal_before,
        projection=projection,
        runtime_identity=runtime_identity,
        companion_identity=companion_identity,
        elapsed_ms=elapsed_ms,
    )


def _validate_typed_node(value: object, label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"native state {label} must be an object")
    node = dict(value)
    if type(node.get("kind")) is not str or not node.get("kind"):
        raise RuntimeError(f"native state {label} requires kind")
    if type(node.get("complete")) is not bool:
        raise RuntimeError(f"native state {label} requires completeness")
    if node.get("kind") == "truncated":
        _require_exact_keys(node, {"kind", "complete", "reason"}, label)
        if node["complete"] is not False or type(node["reason"]) is not str:
            raise RuntimeError(f"native state {label} truncation is invalid")
        return
    for field in ("text", "type"):
        if type(node.get(field)) is not str:
            raise RuntimeError(f"native state {label}.{field} is invalid")
    children = node.get("children")
    if type(children) is not list:
        raise RuntimeError(f"native state {label}.children must be a list")
    child_roles = node.get("child_roles")
    if child_roles is not None and (
        type(child_roles) is not list
        or len(child_roles) != len(children)
        or any(type(role) is not str or not role for role in child_roles)
    ):
        raise RuntimeError(f"native state {label}.child_roles is invalid")
    if node["kind"] == "probability":
        for field in ("memory", "procedure"):
            if type(node.get(field)) is not str or not node.get(field):
                raise RuntimeError(
                    f"native state {label}.{field} is invalid"
                )
        _validate_module_path(
            node.get("procedure_module"),
            f"{label}.procedure_module",
        )
    for index, child in enumerate(children):
        _validate_typed_node(child, f"{label}.children[{index}]")
    _validate_json_tree(node, label)


def _validate_module_path(value: object, label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"native state {label} must be an object")
    module_path = dict(value)
    _require_exact_keys(
        module_path,
        {"term", "top_kind", "top_identity", "arguments"},
        label,
    )
    for field in ("term", "top_identity"):
        if type(module_path[field]) is not str or not module_path[field]:
            raise RuntimeError(f"native state {label}.{field} is invalid")
    if module_path["top_kind"] not in {"local", "concrete"}:
        raise RuntimeError(f"native state {label}.top_kind is invalid")
    arguments = module_path["arguments"]
    if type(arguments) is not list:
        raise RuntimeError(f"native state {label}.arguments must be a list")
    for index, argument in enumerate(arguments):
        _validate_module_path(argument, f"{label}.arguments[{index}]")


def _validate_statement(value: object, label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"native state {label} must be an object")
    statement = dict(value)
    if statement.get("kind") == "truncated":
        _validate_typed_node(statement, label)
        return
    _require_exact_keys(
        statement,
        {"kind", "complete", "structural_path", "text", "instructions"},
        label,
    )
    if statement["kind"] != "statement" or statement["complete"] is not True:
        raise RuntimeError(f"native state {label} header is invalid")
    if type(statement["text"]) is not str:
        raise RuntimeError(f"native state {label}.text is invalid")
    _validate_path(statement["structural_path"], label)
    instructions = statement["instructions"]
    if type(instructions) is not list:
        raise RuntimeError(f"native state {label}.instructions must be a list")
    for index, instruction in enumerate(instructions):
        _validate_instruction(instruction, f"{label}.instructions[{index}]")


def _validate_instruction(value: object, label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"native state {label} must be an object")
    instruction = dict(value)
    if instruction.get("kind") == "truncated":
        _validate_typed_node(instruction, label)
        return
    for field in ("kind", "text"):
        if type(instruction.get(field)) is not str or not instruction.get(field):
            raise RuntimeError(f"native state {label}.{field} is invalid")
    if instruction.get("complete") is not True:
        raise RuntimeError(f"native state {label} completeness is invalid")
    _validate_path(instruction.get("structural_path"), label)
    position = instruction.get("top_level_position")
    if position is not None and (type(position) is not int or position < 1):
        raise RuntimeError(f"native state {label} top-level position is invalid")
    kind = instruction["kind"]
    if kind == "assign":
        _validate_lvalue(instruction.get("target"), f"{label}.target")
        _validate_typed_node(instruction.get("value"), f"{label}.value")
    elif kind == "sample":
        _validate_lvalue(instruction.get("target"), f"{label}.target")
        _validate_typed_node(
            instruction.get("distribution"), f"{label}.distribution"
        )
    elif kind == "call":
        target = instruction.get("target")
        if target is not None:
            _validate_lvalue(target, f"{label}.target")
        if type(instruction.get("procedure")) is not str or not instruction.get(
            "procedure"
        ):
            raise RuntimeError(f"native state {label}.procedure is invalid")
        arguments = instruction.get("arguments")
        if type(arguments) is not list:
            raise RuntimeError(f"native state {label}.arguments must be a list")
        for index, argument in enumerate(arguments):
            _validate_typed_node(argument, f"{label}.arguments[{index}]")
    elif kind == "if":
        _validate_typed_node(instruction.get("condition"), f"{label}.condition")
        _validate_statement(
            instruction.get("then_statement"), f"{label}.then_statement"
        )
        _validate_statement(
            instruction.get("else_statement"), f"{label}.else_statement"
        )
    elif kind == "while":
        _validate_typed_node(instruction.get("condition"), f"{label}.condition")
        _validate_statement(instruction.get("body"), f"{label}.body")
    elif kind == "match":
        _validate_typed_node(
            instruction.get("scrutinee"), f"{label}.scrutinee"
        )
        branches = instruction.get("branches")
        if type(branches) is not list:
            raise RuntimeError(f"native state {label}.branches must be a list")
        for index, branch in enumerate(branches):
            if type(branch) is not dict or branch.get("index") != index:
                raise RuntimeError(f"native state {label}.branch[{index}] is invalid")
            bindings = branch.get("bindings")
            if type(bindings) is not list:
                raise RuntimeError(
                    f"native state {label}.branch[{index}].bindings is invalid"
                )
            _validate_statement(
                branch.get("body"), f"{label}.branch[{index}].body"
            )
    elif kind == "raise":
        _validate_typed_node(
            instruction.get("exception"), f"{label}.exception"
        )
    elif kind == "abstract":
        if type(instruction.get("identifier")) is not str or not instruction.get(
            "identifier"
        ):
            raise RuntimeError(f"native state {label}.identifier is invalid")
    else:
        raise RuntimeError(f"native state {label} instruction kind is invalid")
    _validate_json_tree(instruction, label)


def _validate_lvalue(value: object, label: str) -> None:
    if type(value) is not dict or value.get("kind") not in {"variable", "tuple"}:
        raise RuntimeError(f"native state {label} lvalue is invalid")
    variables = value.get("variables")
    if type(variables) is not list or not variables:
        raise RuntimeError(f"native state {label}.variables is invalid")
    for index, variable in enumerate(variables):
        if type(variable) is not dict:
            raise RuntimeError(f"native state {label}.variables[{index}] is invalid")
        _require_exact_keys(
            variable,
            {"kind", "identity", "display", "type"},
            f"{label}.variables[{index}]",
        )
        if variable["kind"] not in {"local", "global"} or any(
            type(variable[field]) is not str or not variable[field]
            for field in ("identity", "display", "type")
        ):
            raise RuntimeError(f"native state {label}.variables[{index}] is invalid")


def _validate_local_declaration(value: dict[str, Any], label: str) -> None:
    kind = value["kind"]
    common = {"index", "name", "kind"}
    if kind == "variable":
        _require_exact_keys(value, common | {"type", "definition"}, label)
        if type(value["type"]) is not str or not value["type"]:
            raise RuntimeError(f"native state {label}.type is invalid")
        if value["definition"] is not None:
            _validate_typed_node(value["definition"], f"{label}.definition")
    elif kind == "memory":
        _require_exact_keys(value, common | {"memory_type"}, label)
        if type(value["memory_type"]) is not str:
            raise RuntimeError(f"native state {label}.memory_type is invalid")
    elif kind == "module":
        _require_exact_keys(value, common | {"module_type", "restriction"}, label)
        if type(value["module_type"]) is not str or not value["module_type"]:
            raise RuntimeError(f"native state {label}.module_type is invalid")
        _validate_restriction(value["restriction"], f"{label}.restriction")
    elif kind == "hypothesis":
        _require_exact_keys(value, common | {"formula"}, label)
        _validate_typed_node(value["formula"], f"{label}.formula")
    elif kind == "abstract_statement":
        _require_exact_keys(value, common | {"uses"}, label)
        uses = value["uses"]
        if type(uses) is not dict:
            raise RuntimeError(f"native state {label}.uses is invalid")
        _require_exact_keys(uses, {"calls", "reads", "writes"}, f"{label}.uses")
        if type(uses["calls"]) is not list or any(
            type(item) is not str or not item for item in uses["calls"]
        ):
            raise RuntimeError(f"native state {label}.uses.calls is invalid")
        for field in ("reads", "writes"):
            if type(uses[field]) is not list:
                raise RuntimeError(f"native state {label}.uses.{field} is invalid")
            for index, variable in enumerate(uses[field]):
                if type(variable) is not dict:
                    raise RuntimeError(
                        f"native state {label}.uses.{field}[{index}] is invalid"
                    )
                _require_exact_keys(
                    variable,
                    {"kind", "identity", "display", "type"},
                    f"{label}.uses.{field}[{index}]",
                )


def _validate_restriction(value: object, label: str) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"native state {label} must be an object")
    _require_exact_keys(value, {"positive", "negative"}, label)
    for field in ("positive", "negative"):
        part = value[field]
        if field == "positive" and part is None:
            continue
        if type(part) is not dict:
            raise RuntimeError(f"native state {label}.{field} is invalid")
        _require_exact_keys(
            part, {"procedures", "modules"}, f"{label}.{field}"
        )
        for names in part.values():
            if type(names) is not list or any(
                type(item) is not str or not item for item in names
            ):
                raise RuntimeError(f"native state {label}.{field} is invalid")


def _validate_path(value: object, label: str) -> None:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise RuntimeError(f"native state {label} structural path is invalid")


def _validate_json_tree(value: object, label: str) -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_tree(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise RuntimeError(f"native state {label} has a non-string key")
            _validate_json_tree(item, f"{label}.{key}")
        return
    raise RuntimeError(f"native state {label} contains unsupported JSON value")


def _require_exact_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise RuntimeError(f"native state {label} fields mismatch")


def _validate_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or _sha256_file(path) != expected:
        raise RuntimeError(f"native state {label} file changed")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RuntimeError(f"cannot hash native dependency {path.name}") from exc
    return digest.hexdigest()
