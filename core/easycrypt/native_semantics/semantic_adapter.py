"""Validated process boundary for tagged native EasyCrypt semantic queries.

This module is retained prover infrastructure.  It builds a small OCaml
companion against the opam-installed ``easycrypt.ecLib``, verifies that the
library and the manager's EasyCrypt executable report the same build, replays
one manager-owned context/prefix in a separate read-only process, and validates
the structured response.  Feature activation, StateRef/event authority,
candidate selection, admission, and presentation remain outside this module.
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
    NATIVE_SEMANTIC_FRAME_PREFIX,
    NativeCompanionIdentity,
    build_and_identify_companion,
    parse_companion_result_frame,
)
from core.easycrypt.session_projection import active_goal_hash_from_raw


NATIVE_SEMANTIC_PROTOCOL_VERSION = 17
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_QUERY_KINDS = frozenset({
    "proof_term_elaboration",
    "attempt_diagnostic",
    "selected_application_binding_set",
    "tactic_prefix_diagnostic",
})
_STATUSES = frozenset({"accepted", "rejected"})
_SOURCE_DIR = Path(__file__).resolve().parent


def _valid_qualified_symbol(value: object) -> bool:
    return type(value) is str and bool(value) and all(
        part
        and (part[0].isalpha() or part[0] == "_")
        and all(char.isalnum() or char in "_'" for char in part)
        for part in value.split(".")
    )


@dataclass(frozen=True)
class NativeSemanticQuery:
    request_id: str
    query_kind: str
    payload: dict[str, object]
    evaluation_prefix: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id or self.request_id != self.request_id.strip():
            raise ValueError("native proof-term query requires request_id")
        if self.query_kind not in _QUERY_KINDS:
            raise ValueError("native semantic query kind is unsupported")
        if (
            type(self.evaluation_prefix) is not tuple
            or any(
                type(item) is not str
                or not item
                or item != item.strip()
                or not item.endswith(".")
                or "\n" in item
                or "\r" in item
                for item in self.evaluation_prefix
            )
        ):
            raise ValueError("native semantic query evaluation prefix is invalid")
        validate_native_query_payload(self.query_kind, self.payload)

    def runtime_payload(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "evaluation_prefix": list(self.evaluation_prefix),
            "query_kind": self.query_kind,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class NativeSemanticBatchRequest:
    batch_id: str
    context_file: Path
    history_file: Path
    include_dirs: tuple[Path, ...]
    queries: tuple[NativeSemanticQuery, ...]
    expected_goal_identity: str
    expected_context_sha256: str
    expected_history_sha256: str

    def __post_init__(self) -> None:
        if not self.batch_id or self.batch_id != self.batch_id.strip():
            raise ValueError("native semantic batch requires batch_id")
        if not self.queries or len(self.queries) > 8:
            raise ValueError("native semantic batch size is invalid")
        request_ids = tuple(item.request_id for item in self.queries)
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("native semantic batch has duplicate request IDs")
        if not self.expected_goal_identity:
            raise ValueError("native semantic batch requires open goal identity")
        for value in (
            self.expected_context_sha256,
            self.expected_history_sha256,
        ):
            if not _SHA256_RE.fullmatch(value):
                raise ValueError("native semantic batch requires source hashes")

    def runtime_payload(self) -> dict[str, object]:
        return {
            "schema_version": NATIVE_SEMANTIC_PROTOCOL_VERSION,
            "kind": "native_semantic_batch_request",
            "batch_id": self.batch_id,
            "context_file": str(self.context_file.resolve()),
            "history_file": str(self.history_file.resolve()),
            "include_dirs": [str(path.resolve()) for path in self.include_dirs],
            "requests": [item.runtime_payload() for item in self.queries],
        }


@dataclass(frozen=True)
class NativeSemanticResult:
    request_id: str
    evaluation_prefix: tuple[str, ...]
    query_kind: str
    payload: dict[str, object]
    status: str
    result_formula: str
    descriptor: dict[str, Any]
    structured_error: dict[str, Any]
    elapsed_ms: int

    def __post_init__(self) -> None:
        if (
            type(self.evaluation_prefix) is not tuple
            or any(
                type(item) is not str
                or not item
                or item != item.strip()
                or not item.endswith(".")
                for item in self.evaluation_prefix
            )
        ):
            raise ValueError("native semantic result context is invalid")
        if self.status not in _STATUSES:
            raise ValueError("native semantic result has invalid status")
        if self.status == "accepted":
            if not self.descriptor or self.structured_error or (
                self.query_kind == "proof_term_elaboration"
                and not self.result_formula
            ) or (
                self.query_kind != "proof_term_elaboration"
                and bool(self.result_formula)
            ):
                raise ValueError("accepted native semantic result has invalid payload")
        elif self.result_formula or self.descriptor or not self.structured_error:
            raise ValueError("rejected native result has invalid payload")
        if self.elapsed_ms < 0:
            raise ValueError("native semantic result has invalid elapsed time")


@dataclass(frozen=True)
class NativeSemanticBatchResult:
    batch_id: str
    goal_before: str
    results: tuple[NativeSemanticResult, ...]
    runtime_identity: EasyCryptRuntimeIdentity
    companion_identity: NativeCompanionIdentity
    cache_state: str
    build_elapsed_ms: int
    execution_elapsed_ms: int
    elapsed_ms: int

    def __post_init__(self) -> None:
        if not self.batch_id or not self.goal_before or not self.results:
            raise ValueError("native semantic batch result is incomplete")
        if self.cache_state not in {"cold", "warm"}:
            raise ValueError("native semantic batch cache state is invalid")
        if any(value < 0 for value in (
            self.build_elapsed_ms,
            self.execution_elapsed_ms,
            self.elapsed_ms,
        )):
            raise ValueError("native semantic batch elapsed time is invalid")
        if self.elapsed_ms < self.build_elapsed_ms + self.execution_elapsed_ms:
            raise ValueError("native semantic batch phase timings are inconsistent")


def run_native_semantic_batch(
    request: NativeSemanticBatchRequest,
    *,
    runtime_identity: EasyCryptRuntimeIdentity,
    timeout: int = 30,
) -> NativeSemanticBatchResult:
    """Replay once and run one bounded ordered native semantic batch."""

    if timeout <= 0:
        raise ValueError("native semantic batch timeout must be positive")
    context = request.context_file.resolve()
    history = request.history_file.resolve()
    _validate_file_hash(context, request.expected_context_sha256, "context")
    _validate_file_hash(history, request.expected_history_sha256, "history")
    executable_path = (
        _SOURCE_DIR / "_build" / "default" / "native_semantic_adapter.exe"
    )
    before_build = _binary_fingerprint(executable_path)
    total_started = time.perf_counter()
    build_started = time.perf_counter()
    executable, companion = build_and_identify_companion(
        "native_semantic_adapter",
        runtime_identity,
    )
    build_elapsed_ms = int((time.perf_counter() - build_started) * 1000)
    after_build = _binary_fingerprint(executable)
    cache_state = (
        "warm"
        if before_build is not None and before_build == after_build
        else "cold"
    )
    payload = json.dumps(
        request.runtime_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    execution_started = time.perf_counter()
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
        raise RuntimeError("native semantic batch companion failed to run") from exc
    execution_elapsed_ms = int(
        (time.perf_counter() - execution_started) * 1000
    )
    elapsed_ms = int((time.perf_counter() - total_started) * 1000)
    _validate_file_hash(context, request.expected_context_sha256, "context")
    _validate_file_hash(history, request.expected_history_sha256, "history")
    if process.returncode != 0:
        raise RuntimeError("native semantic batch companion exited unsuccessfully")
    raw = parse_companion_result_frame(
        process.stdout,
        prefix=NATIVE_SEMANTIC_FRAME_PREFIX,
    )
    result = _validated_batch_result(
        raw,
        request=request,
        runtime_identity=runtime_identity,
        companion_identity=companion,
        cache_state=cache_state,
        build_elapsed_ms=build_elapsed_ms,
        execution_elapsed_ms=execution_elapsed_ms,
        elapsed_ms=elapsed_ms,
    )
    observed_goal_identity = active_goal_hash_from_raw(result.goal_before)
    if observed_goal_identity != request.expected_goal_identity:
        raise RuntimeError("native semantic batch replayed a different goal")
    return result


def _validated_batch_result(
    value: object,
    *,
    request: NativeSemanticBatchRequest,
    runtime_identity: EasyCryptRuntimeIdentity,
    companion_identity: NativeCompanionIdentity,
    cache_state: str,
    build_elapsed_ms: int,
    execution_elapsed_ms: int,
    elapsed_ms: int,
) -> NativeSemanticBatchResult:
    if type(value) is not dict:
        raise RuntimeError("native semantic batch result must be an object")
    raw = dict(value)
    if raw.get("schema_version") != NATIVE_SEMANTIC_PROTOCOL_VERSION or (
        type(raw.get("schema_version")) is not int
    ):
        raise RuntimeError("native semantic batch result schema mismatch")
    if raw.get("kind") != "native_semantic_batch_result":
        raise RuntimeError("native semantic batch result kind mismatch")
    if raw.get("status") in {"contract_error", "adapter_error"}:
        message = str(raw.get("message") or "unknown native adapter failure")
        raise RuntimeError(message)
    if raw.get("batch_id") != request.batch_id:
        raise RuntimeError("native semantic batch identity mismatch")
    goal_before = raw.get("goal_before")
    if type(goal_before) is not str or not goal_before:
        raise RuntimeError("native semantic batch requires goal_before")
    members = raw.get("results")
    if type(members) is not list or len(members) != len(request.queries):
        raise RuntimeError("native semantic batch result cardinality mismatch")
    results = tuple(
        _validated_member(raw_member, query=query)
        for raw_member, query in zip(members, request.queries)
    )
    return NativeSemanticBatchResult(
        batch_id=request.batch_id,
        goal_before=goal_before,
        results=results,
        runtime_identity=runtime_identity,
        companion_identity=companion_identity,
        cache_state=cache_state,
        build_elapsed_ms=build_elapsed_ms,
        execution_elapsed_ms=execution_elapsed_ms,
        elapsed_ms=elapsed_ms,
    )


def _binary_fingerprint(path: Path) -> tuple[int, int, str] | None:
    """Classify companion reuse without weakening its content identity."""

    if not path.is_file():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, _sha256_file(path)


def _validated_member(
    value: object,
    *,
    query: NativeSemanticQuery,
) -> NativeSemanticResult:
    if type(value) is not dict:
        raise RuntimeError("native semantic batch member must be an object")
    raw = dict(value)
    for name, expected in (
        ("request_id", query.request_id),
        ("evaluation_prefix", list(query.evaluation_prefix)),
        ("query_kind", query.query_kind),
        ("payload", query.payload),
    ):
        if raw.get(name) != expected:
            raise RuntimeError(f"native semantic member {name} mismatch")
    if raw.get("status") not in _STATUSES:
        raise RuntimeError("native semantic member status is invalid")
    status = str(raw["status"])
    error = raw.get("structured_error", {})
    if type(error) is not dict:
        raise RuntimeError("native semantic member error must be an object")
    descriptor = raw.get("descriptor", {})
    if type(descriptor) is not dict:
        raise RuntimeError("native semantic member descriptor must be an object")
    if status == "accepted":
        descriptor = {
            "proof_term_elaboration": validate_proof_term_descriptor,
            "selected_application_binding_set": (
                validate_selected_application_binding_set_descriptor
            ),
            "attempt_diagnostic": lambda value: validate_attempt_descriptor(
                value, query=query
            ),
            "tactic_prefix_diagnostic": (
                lambda value: validate_tactic_prefix_descriptor(
                    value, query=query
                )
            ),
        }[query.query_kind](descriptor)
    elif descriptor:
        raise RuntimeError("rejected native semantic member carried descriptor")
    member_elapsed_ms = raw.get("elapsed_ms")
    if type(member_elapsed_ms) is not int or member_elapsed_ms < 0:
        raise RuntimeError("native semantic member elapsed time is invalid")
    return NativeSemanticResult(
        request_id=query.request_id,
        evaluation_prefix=query.evaluation_prefix,
        query_kind=query.query_kind,
        payload=dict(query.payload),
        status=status,
        result_formula=str(raw.get("result_formula") or ""),
        descriptor=dict(descriptor),
        structured_error=dict(error),
        elapsed_ms=member_elapsed_ms,
    )


def validate_native_query_payload(
    query_kind: str,
    payload: dict[str, object],
) -> None:
    if type(payload) is not dict:
        raise ValueError("native semantic query payload must be an object")
    if query_kind == "proof_term_elaboration":
        if set(payload) != {"operation", "application_term"} or payload.get(
            "operation"
        ) not in {"apply", "exact", "call", "conseq"}:
            raise ValueError("native proof-term payload is invalid")
        term = payload.get("application_term")
        if type(term) is not str or not term or term != term.strip():
            raise ValueError("native proof-term payload requires exact application")
        return
    if query_kind == "attempt_diagnostic":
        expected = {"rejected_tactic", "observed_outcome_kind"}
        if set(payload) != expected:
            raise ValueError("native diagnostic payload fields are invalid")
        tactic = payload.get("rejected_tactic")
        if type(tactic) is not str or not tactic or tactic != tactic.strip():
            raise ValueError("native diagnostic payload requires exact tactic")
        if payload.get("observed_outcome_kind") not in {
            "rejected", "no_progress"
        }:
            raise ValueError("native diagnostic payload requires manager outcome")
        return
    if query_kind == "selected_application_binding_set":
        if set(payload) != {
            "operation", "selected_resource", "module_candidates"
        } or payload.get("operation") not in {"apply", "exact"}:
            raise ValueError("native binding-set payload fields are invalid")
        resource = payload.get("selected_resource")
        candidates = payload.get("module_candidates")
        if (
            not _valid_qualified_symbol(resource)
            or type(candidates) is not list
            or not candidates
            or len(candidates) > 96
            or candidates != sorted(set(candidates))
            or any(
                type(item) is not str
                or not item
                or item != item.strip()
                or len(item) > 512
                or any(char in item for char in "\n\r;")
                for item in candidates
            )
        ):
            raise ValueError("native binding-set payload is invalid")
        return
    if query_kind != "tactic_prefix_diagnostic":
        raise ValueError("native semantic query kind is unsupported")
    if set(payload) != {"rejected_tactic", "candidate_prefixes"}:
        raise ValueError("native tactic-prefix payload fields are invalid")
    tactic = payload.get("rejected_tactic")
    prefixes = payload.get("candidate_prefixes")
    if (
        type(tactic) is not str
        or not tactic
        or tactic != tactic.strip()
        or not tactic.endswith(".")
        or type(prefixes) is not list
        or not 1 <= len(prefixes) <= 8
        or any(
            type(item) is not str
            or not item
            or item != item.strip()
            or not item.endswith(".")
            or item == tactic
            for item in prefixes
        )
        or len(prefixes) != len(set(prefixes))
    ):
        raise ValueError("native tactic-prefix payload is invalid")


def validate_tactic_prefix_descriptor(
    value: dict[str, Any],
    *,
    query: NativeSemanticQuery,
) -> dict[str, Any]:
    """Validate a complete native result for one bounded prefix population."""

    required = {
        "rejected_tactic",
        "candidate_prefixes",
        "prefix_effects",
        "accepted_prefixes",
        "boundary_tactic",
        "boundary_attempt",
        "native_failure_kind",
        "native_error_message",
        "boundary_failure_kind",
        "boundary_error_message",
        "goal_kind",
    }
    candidates = value.get("candidate_prefixes")
    effects = value.get("prefix_effects")
    accepted = value.get("accepted_prefixes")
    boundary_tactic = value.get("boundary_tactic")
    boundary_attempt = value.get("boundary_attempt")
    if (
        set(value) != required
        or query.query_kind != "tactic_prefix_diagnostic"
        or value.get("rejected_tactic")
        != query.payload.get("rejected_tactic")
        or candidates != query.payload.get("candidate_prefixes")
        or type(candidates) is not list
        or not 1 <= len(candidates) <= 8
        or any(type(item) is not str for item in candidates)
        or len(candidates) != len(set(candidates))
        or type(effects) is not list
        or len(effects) != len(candidates)
        or any(item not in {
            "accepted_changed", "accepted_no_progress", "rejected"
        } for item in effects)
        or type(accepted) is not list
        or any(type(item) is not str for item in accepted)
        or len(accepted) != len(set(accepted))
        or any(item not in candidates for item in accepted)
        or accepted != [
            item for item, effect in zip(candidates, effects)
            if effect != "rejected"
        ]
        or type(boundary_tactic) is not str
        or bool(boundary_tactic) and (
            boundary_tactic != boundary_tactic.strip()
            or not boundary_tactic.endswith(".")
        )
        or boundary_attempt is not None
        and type(boundary_attempt) is not dict
        or type(value.get("native_failure_kind")) is not str
        or not value.get("native_failure_kind")
        or type(value.get("native_error_message")) is not str
        or not value.get("native_error_message")
        or type(value.get("boundary_failure_kind")) is not str
        or not value.get("boundary_failure_kind")
        or type(value.get("boundary_error_message")) is not str
        or not value.get("boundary_error_message")
        or type(value.get("goal_kind")) is not str
        or not value.get("goal_kind")
    ):
        raise RuntimeError("native tactic-prefix descriptor is invalid")
    if boundary_attempt is not None:
        contiguous_effect = ""
        for effect in effects:
            if effect == "rejected":
                break
            contiguous_effect = effect
        if contiguous_effect not in {
            "accepted_no_progress", "accepted_changed"
        } or not boundary_tactic:
            raise RuntimeError("native tactic-prefix handoff is invalid")
        validate_attempt_descriptor(
            boundary_attempt,
            query=NativeSemanticQuery(
                request_id="nested-prefix-boundary",
                query_kind="attempt_diagnostic",
                payload={
                    "rejected_tactic": boundary_tactic,
                    "observed_outcome_kind": "rejected",
                },
            ),
        )
    return dict(value)


def validate_attempt_descriptor(
    value: dict[str, Any],
    *,
    query: NativeSemanticQuery,
) -> dict[str, Any]:
    required = {
        "operation_family",
        "rejected_tactic",
        "exact_resource",
        "argument_kinds",
        "side",
        "positions",
        "native_diagnostic_status",
        "native_failure_kind",
        "native_error_message",
        "attempt_outcome",
        "goal_kind",
        "application_head",
        "proof_term",
        "relation_bridge",
        "relation_bridge_choice",
        "phl_transitivity_boundary",
        "eager_while_dialect",
        "pure_tail_rewrite",
        "intro_pattern_realization",
        "application_syntax_repair",
    }
    if set(value) != required:
        raise RuntimeError("native attempted-operation descriptor fields are invalid")
    family = value.get("operation_family")
    if family not in {
        "apply", "exact", "call", "conseq", "transitivity", "change",
        "eager", "rewrite", "intro_pattern",
    }:
        raise RuntimeError("native attempted-operation family is invalid")
    if value.get("rejected_tactic") != query.payload.get("rejected_tactic"):
        raise RuntimeError("native attempted-operation tactic identity drifted")
    resource = value.get("exact_resource")
    if type(resource) is not str:
        raise RuntimeError("native attempted-operation resource is invalid")
    argument_kinds = value.get("argument_kinds")
    if type(argument_kinds) is not list or any(
        type(item) is not str or not item for item in argument_kinds
    ):
        raise RuntimeError("native attempted-operation arguments are invalid")
    if value.get("side") not in {"", "left", "right"}:
        raise RuntimeError("native attempted-operation side is invalid")
    positions = value.get("positions")
    if type(positions) is not list or any(
        type(item) is not int or item < 0 for item in positions
    ):
        raise RuntimeError("native attempted-operation positions are invalid")
    outcome = value.get("attempt_outcome")
    failure_kind = value.get("native_failure_kind")
    error_message = value.get("native_error_message")
    diagnostic_status = value.get("native_diagnostic_status")
    if (
        outcome not in {"accepted", "rejected", "no_progress"}
        or diagnostic_status not in {
            "blocker", "no_blocker", "indeterminate"
        }
        or type(failure_kind) is not str
        or type(error_message) is not str
    ):
        raise RuntimeError("native attempted-operation outcome is invalid")
    if outcome != query.payload.get("observed_outcome_kind"):
        raise RuntimeError("native attempt outcome diverged from manager event")
    if outcome == "rejected" and diagnostic_status == "no_blocker":
        raise RuntimeError("rejected native attempt has no native blocker")
    if outcome == "accepted" and diagnostic_status != "no_blocker":
        raise RuntimeError("accepted native attempt carried a diagnostic")
    if diagnostic_status == "no_blocker" and (
        failure_kind or error_message
    ):
        raise RuntimeError("no-blocker native attempt carried an error")
    if diagnostic_status != "no_blocker" and not failure_kind:
        raise RuntimeError("native attempted-operation diagnostic is empty")
    if diagnostic_status == "indeterminate" and (
        failure_kind != "native_assertion"
    ):
        raise RuntimeError("native indeterminate diagnostic kind is invalid")
    if bool(failure_kind) is not bool(error_message):
        raise RuntimeError("native attempted-operation error is incomplete")
    if type(value.get("goal_kind")) is not str or not value.get("goal_kind"):
        raise RuntimeError("native attempted-operation goal kind is invalid")
    proof_term = value.get("proof_term")
    application_head = value.get("application_head")
    relation_bridge = value.get("relation_bridge")
    relation_bridge_choice = value.get("relation_bridge_choice")
    phl_boundary = value.get("phl_transitivity_boundary")
    eager_while = value.get("eager_while_dialect")
    pure_tail_rewrite = value.get("pure_tail_rewrite")
    intro_pattern_realization = value.get("intro_pattern_realization")
    application_syntax = value.get("application_syntax_repair")
    if application_head is not None:
        if type(application_head) is not dict or not resource:
            raise RuntimeError("native attempted-operation head is invalid")
        value = dict(value)
        value["application_head"] = validate_application_head_descriptor(
            application_head
        )
    if proof_term is not None:
        if type(proof_term) is not dict or family not in {
            "apply", "exact", "call", "conseq"
        }:
            raise RuntimeError("native attempted-operation proof term is invalid")
        value = dict(value)
        value["proof_term"] = validate_proof_term_descriptor(proof_term)
    if relation_bridge is not None:
        if type(relation_bridge) is not dict or family not in {
            "transitivity", "change"
        } or resource or proof_term is not None or application_head is not None:
            raise RuntimeError("native attempted relation bridge is invalid")
        value = dict(value)
        value["relation_bridge"] = validate_relation_bridge_descriptor(
            relation_bridge,
            source_operation=str(family),
        )
    if relation_bridge_choice is not None:
        if (
            type(relation_bridge_choice) is not dict
            or family != "transitivity"
            or resource
            or proof_term is not None
            or application_head is not None
            or relation_bridge is not None
        ):
            raise RuntimeError("native attempted relation choice is invalid")
        value = dict(value)
        value["relation_bridge_choice"] = (
            validate_relation_bridge_choice_descriptor(
                relation_bridge_choice,
                source_operation=str(family),
            )
        )
    if phl_boundary is not None:
        if (
            type(phl_boundary) is not dict
            or family != "transitivity"
            or resource
            or proof_term is not None
            or application_head is not None
            or relation_bridge is not None
            or relation_bridge_choice is not None
        ):
            raise RuntimeError("native attempted PHL boundary is invalid")
        value = dict(value)
        value["phl_transitivity_boundary"] = (
            validate_phl_transitivity_boundary_descriptor(phl_boundary)
        )
    if eager_while is not None:
        if (
            type(eager_while) is not dict
            or family != "eager"
            or resource
            or proof_term is not None
            or application_head is not None
            or relation_bridge is not None
            or relation_bridge_choice is not None
            or phl_boundary is not None
            or value.get("side")
            or value.get("positions")
        ):
            raise RuntimeError("native attempted eager dialect is invalid")
        value = dict(value)
        value["eager_while_dialect"] = validate_eager_while_descriptor(
            eager_while
        )
    if pure_tail_rewrite is not None:
        if (
            type(pure_tail_rewrite) is not dict
            or family != "rewrite"
            or not resource
            or proof_term is not None
            or application_head is not None
            or relation_bridge is not None
            or relation_bridge_choice is not None
            or phl_boundary is not None
            or eager_while is not None
            or value.get("side")
            or value.get("positions")
        ):
            raise RuntimeError("native attempted pure-tail rewrite is invalid")
        value = dict(value)
        value["pure_tail_rewrite"] = validate_pure_tail_rewrite_descriptor(
            pure_tail_rewrite,
            selected_resource=str(resource),
        )
    if intro_pattern_realization is not None:
        if (
            type(intro_pattern_realization) is not dict
            or family != "intro_pattern"
            or resource
            or proof_term is not None
            or application_head is not None
            or relation_bridge is not None
            or relation_bridge_choice is not None
            or phl_boundary is not None
            or eager_while is not None
            or pure_tail_rewrite is not None
            or application_syntax is not None
            or value.get("side")
            or value.get("positions")
        ):
            raise RuntimeError("native attempted intro-pattern repair is invalid")
        value = dict(value)
        value["intro_pattern_realization"] = (
            validate_intro_pattern_realization_descriptor(
                intro_pattern_realization
            )
        )
    if application_syntax is not None:
        if (
            type(application_syntax) is not dict
            or family != "call"
            or not resource
            or proof_term is not None
            or application_head is None
            or relation_bridge is not None
            or relation_bridge_choice is not None
            or phl_boundary is not None
            or eager_while is not None
            or pure_tail_rewrite is not None
            or intro_pattern_realization is not None
            or value.get("argument_kinds")
            or value.get("side")
            or value.get("positions")
        ):
            raise RuntimeError(
                "native application syntax repair changed attempted identity"
            )
        value = dict(value)
        value["application_syntax_repair"] = (
            validate_application_syntax_repair_descriptor(
                application_syntax,
                selected_resource=str(resource),
            )
        )
    return dict(value)


def validate_intro_pattern_realization_descriptor(
    value: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "source_operation",
        "surface_operation",
        "attempted_pattern_kind",
        "binder_names",
        "candidate_tactic",
        "failure_kind",
        "selected_pattern_count",
    }
    binders = value.get("binder_names")
    candidate = value.get("candidate_tactic")
    if (
        set(value) != required
        or value.get("source_operation") != "intro_pattern"
        or value.get("surface_operation") != "move"
        or value.get("attempted_pattern_kind") != "nested_case"
        or type(binders) is not list
        or not 2 <= len(binders) <= 32
        or len(binders) != len(set(binders))
        or any(type(item) is not str or not item for item in binders)
        or type(candidate) is not str
        or not candidate.endswith(".")
        or value.get("failure_kind")
        != "intro_pattern_structure_mismatch"
        or value.get("selected_pattern_count") != 1
    ):
        raise RuntimeError("native intro-pattern repair identity is invalid")
    return dict(value)


def validate_application_syntax_repair_descriptor(
    value: dict[str, Any],
    *,
    selected_resource: str,
) -> dict[str, Any]:
    required = {
        "source_operation",
        "selected_resource",
        "module_argument_position",
        "module_term_text",
        "candidate_application_term",
        "candidate_tactic",
        "candidate_argument_kinds",
        "failure_kind",
        "resolved_candidate_count",
    }
    if set(value) != required:
        raise RuntimeError("native application syntax repair fields are invalid")
    module_term = value.get("module_term_text")
    application = value.get("candidate_application_term")
    tactic = value.get("candidate_tactic")
    arguments = value.get("candidate_argument_kinds")
    if (
        value.get("source_operation") != "call"
        or value.get("selected_resource") != selected_resource
        or value.get("module_argument_position") != 1
        or type(module_term) is not str
        or not module_term
        or type(application) is not str
        or not application.startswith(selected_resource + " ")
        or f"(<: {module_term})" not in application
        or tactic != f"call ({application})."
        or type(arguments) is not list
        or not arguments
        or arguments[0] != "module"
        or any(type(item) is not str or not item for item in arguments)
        or value.get("failure_kind")
        != "application_module_argument_syntax"
        or value.get("resolved_candidate_count") != 1
        or any(
            token in tactic
            for token in (";", "\n", "\r", '"', "(*", "*)", "|")
        )
    ):
        raise RuntimeError("native application syntax repair is invalid")
    return dict(value)


def validate_pure_tail_rewrite_descriptor(
    value: dict[str, Any],
    *,
    selected_resource: str,
) -> dict[str, Any]:
    required = {
        "source_operation",
        "selected_resource",
        "target_kind",
        "target_name",
        "candidate_tactic",
        "failure_kind",
        "accepted_target_count",
    }
    if set(value) != required:
        raise RuntimeError("native pure-tail rewrite fields are invalid")
    target_name = value.get("target_name")
    if (
        value.get("source_operation") != "rewrite"
        or value.get("selected_resource") != selected_resource
        or value.get("target_kind") != "hypothesis"
        or type(target_name) is not str
        or not target_name
        or value.get("candidate_tactic")
        != f"rewrite {selected_resource} in {target_name}."
        or value.get("failure_kind") != "rewrite_target_mismatch"
        or value.get("accepted_target_count") != 1
    ):
        raise RuntimeError("native pure-tail rewrite identity is invalid")
    return dict(value)


def validate_relation_bridge_descriptor(
    value: dict[str, Any],
    *,
    source_operation: str,
) -> dict[str, Any]:
    required = {
        "source_operation",
        "relation_family",
        "intermediate_text",
        "intermediate_type",
        "candidate_tactic",
        "failure_kind",
        "source_target_present",
        "source_target_convertible_to_current_goal",
        "source_target_right_convertible_to_current_right",
    }
    if set(value) != required or value.get("source_operation") != source_operation:
        raise RuntimeError("native relation-bridge identity is invalid")
    relation_family = value.get("relation_family")
    if relation_family not in {"real_le", "int_le"}:
        raise RuntimeError("native relation-bridge family is unsupported")
    for field in (
        "intermediate_text",
        "intermediate_type",
        "candidate_tactic",
        "failure_kind",
    ):
        if type(value.get(field)) is not str or not value.get(field):
            raise RuntimeError("native relation-bridge text is incomplete")
    if not str(value["candidate_tactic"]).endswith("."):
        raise RuntimeError("native relation-bridge candidate is not a tactic")
    expected_failure = {
        "transitivity": "formula_transitivity_surface_mismatch",
        "change": "change_target_not_convertible",
    }[source_operation]
    expected_type, certificate_family = {
        "real_le": ("real", "ler_trans"),
        "int_le": ("int", "Int.lez_trans"),
    }[relation_family]
    expected_candidate = (
        f"apply ({certificate_family} {value['intermediate_text']}); first last."
    )
    if (
        value["intermediate_type"] != expected_type
        or value["failure_kind"] != expected_failure
        or value["candidate_tactic"] != expected_candidate
        or (relation_family == "int_le" and source_operation != "transitivity")
    ):
        raise RuntimeError("native relation-bridge certificate is invalid")
    flags = tuple(
        value.get(field)
        for field in (
            "source_target_present",
            "source_target_convertible_to_current_goal",
            "source_target_right_convertible_to_current_right",
        )
    )
    if any(type(flag) is not bool for flag in flags):
        raise RuntimeError("native relation-bridge flags are invalid")
    if source_operation == "transitivity" and any(flags):
        raise RuntimeError("transitivity bridge claimed a change target")
    if source_operation == "change" and flags != (True, False, True):
        raise RuntimeError("change bridge lacks convertibility evidence")
    return dict(value)


def validate_relation_bridge_choice_descriptor(
    value: dict[str, Any],
    *,
    source_operation: str,
) -> dict[str, Any]:
    required = {
        "source_operation",
        "relation_family",
        "goal_left_text",
        "intermediate_text",
        "goal_right_text",
        "intermediate_type",
        "failure_kind",
        "choices",
    }
    if set(value) != required or value.get("source_operation") != source_operation:
        raise RuntimeError("native relation-choice identity is invalid")
    if (
        source_operation != "transitivity"
        or value.get("relation_family") != "real_lt"
        or value.get("intermediate_type") != "real"
        or value.get("failure_kind")
        != "formula_transitivity_surface_mismatch"
    ):
        raise RuntimeError("native relation-choice family is unsupported")
    for field in ("goal_left_text", "intermediate_text", "goal_right_text"):
        if type(value.get(field)) is not str or not value.get(field):
            raise RuntimeError("native relation-choice text is incomplete")
    choices = value.get("choices")
    expected = (
        ("ler_lt_trans", "<=", "<"),
        ("ltr_le_trans", "<", "<="),
        ("ltr_trans", "<", "<"),
    )
    if type(choices) is not list or len(choices) != len(expected):
        raise RuntimeError("native relation choices are incomplete")
    intermediate = value["intermediate_text"]
    for item, (family, left_relation, right_relation) in zip(choices, expected):
        if type(item) is not dict or set(item) != {
            "certificate_family",
            "left_relation",
            "right_relation",
            "candidate_tactic",
        }:
            raise RuntimeError("native relation choice fields are invalid")
        if item != {
            "certificate_family": family,
            "left_relation": left_relation,
            "right_relation": right_relation,
            "candidate_tactic": (
                f"apply ({family} {intermediate}); first last."
            ),
        }:
            raise RuntimeError("native relation choice is not canonical")
    return dict(value)


def validate_phl_transitivity_boundary_descriptor(
    value: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "source_operation",
        "attempted_form",
        "current_goal_form",
        "side",
        "failure_kind",
    }
    attempted_form = value.get("attempted_form")
    current_goal_form = value.get("current_goal_form")
    side = value.get("side")
    if (
        set(value) != required
        or value.get("source_operation") != "transitivity"
        or attempted_form not in {"function", "statement"}
        or current_goal_form not in {"function", "statement"}
        or attempted_form == current_goal_form
        or side not in {"", "left", "right"}
        or (attempted_form == "function" and side)
        or (attempted_form == "statement" and not side)
        or value.get("failure_kind") != "phl_transitivity_boundary_mismatch"
    ):
        raise RuntimeError("native PHL transitivity boundary is invalid")
    return dict(value)


def validate_eager_while_descriptor(
    value: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "source_operation",
        "eager_subform",
        "attempted_shape",
        "failure_kind",
        "candidates",
    }
    attempted_shape = value.get("attempted_shape")
    failure_kind = value.get("failure_kind")
    candidates = value.get("candidates")
    if (
        set(value) != required
        or value.get("source_operation") != "eager"
        or value.get("eager_subform") != "while"
        or attempted_shape not in {
            "explicit_statement_contract", "invariant"
        }
        or failure_kind not in {
            "eager_while_dialect_mismatch",
            "eager_while_guard_mismatch",
        }
        or type(candidates) is not list
        or len(candidates) > 2
    ):
        raise RuntimeError("native eager-while descriptor is incomplete")
    if failure_kind == "eager_while_dialect_mismatch" and (
        attempted_shape != "explicit_statement_contract"
    ):
        raise RuntimeError("native eager dialect mismatch has the wrong shape")
    if failure_kind == "eager_while_guard_mismatch" and (
        attempted_shape != "invariant" or candidates
    ):
        raise RuntimeError("native eager guard mismatch carried candidates")
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        if type(item) is not dict or set(item) != {
            "invariant_text", "candidate_tactic"
        }:
            raise RuntimeError("native eager-while candidate fields are invalid")
        invariant = item.get("invariant_text")
        tactic = item.get("candidate_tactic")
        if (
            type(invariant) is not str
            or not invariant
            or tactic != f"eager while ({invariant})."
            or (invariant, tactic) in seen
        ):
            raise RuntimeError("native eager-while candidate is invalid")
        seen.add((invariant, tactic))
    return dict(value)


def validate_application_head_descriptor(
    value: dict[str, Any],
) -> dict[str, Any]:
    """Validate one native head shape without claiming an application."""

    if set(value) != {
        "resolved_head", "input_mode", "input_arguments", "slots", "result"
    }:
        raise RuntimeError("native application-head fields are invalid")
    _validate_resolved_head(value.get("resolved_head"))
    if value.get("input_mode") not in {"explicit", "implicit"}:
        raise RuntimeError("native application-head input mode is invalid")
    inputs = value.get("input_arguments")
    if type(inputs) is not list:
        raise RuntimeError("native application-head inputs must be a list")
    for position, item in enumerate(inputs, start=1):
        if type(item) is not dict or set(item) != {
            "position", "syntax_kind", "explicit_hole", "source_spelling"
        }:
            raise RuntimeError("native application-head input is invalid")
        if item.get("position") != position or item.get("syntax_kind") not in {
            "hole", "formula", "memory", "module", "proof", "proof_tactic"
        } or type(item.get("explicit_hole")) is not bool:
            raise RuntimeError("native application-head input value is invalid")
        if item.get("explicit_hole") is not (item.get("syntax_kind") == "hole"):
            raise RuntimeError("native application-head hole marker is invalid")
        spelling = item.get("source_spelling")
        if type(spelling) is not str or spelling and (
            not _valid_qualified_symbol(spelling)
            or item.get("syntax_kind") not in {"formula", "module"}
        ):
            raise RuntimeError("native application-head spelling is invalid")
    slots = value.get("slots")
    if type(slots) is not list:
        raise RuntimeError("native application-head slots must be a list")
    for position, item in enumerate(slots, start=1):
        if type(item) is not dict or item.get("position") != position:
            raise RuntimeError("native application-head slot order is invalid")
        kind = item.get("kind")
        if kind not in {"formula", "memory", "module", "proof"}:
            raise RuntimeError("native application-head slot kind is invalid")
        _validate_expected_argument(
            {key: item[key] for key in item if key != "position"},
            kind=kind,
        )
    _validate_formula_descriptor(value.get("result"))
    return dict(value)


def validate_proof_term_descriptor(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and detach one accepted native application descriptor."""
    required = {
        "resolved_head",
        "input_mode",
        "input_arguments",
        "explicit_hole_count",
        "implicit_argument_count",
        "arguments",
        "can_concretize",
        "residual_proof_premises",
        "result",
        "result_convertible_to_current_goal",
    }
    if set(value) != required:
        raise RuntimeError("native proof-term descriptor fields are invalid")
    head = value.get("resolved_head")
    if type(head) is not dict or set(head) != {
        "kind", "identity", "type_arguments"
    }:
        raise RuntimeError("native proof-term resolved head is invalid")
    if head.get("kind") not in {"global", "local"} or not head.get("identity"):
        raise RuntimeError("native proof-term resolved head identity is invalid")
    type_arguments = head.get("type_arguments")
    if type(type_arguments) is not list or any(
        type(item) is not str for item in type_arguments
    ):
        raise RuntimeError("native proof-term head type arguments are invalid")
    if value.get("input_mode") not in {"explicit", "implicit"}:
        raise RuntimeError("native proof-term input mode is invalid")
    inputs = value.get("input_arguments")
    if type(inputs) is not list:
        raise RuntimeError("native proof-term input arguments must be a list")
    for position, item in enumerate(inputs, start=1):
        if type(item) is not dict or set(item) != {
            "position", "syntax_kind", "explicit_hole", "source_spelling"
        }:
            raise RuntimeError("native proof-term input argument is invalid")
        if item.get("position") != position or item.get("syntax_kind") not in {
            "hole", "formula", "memory", "module", "proof", "proof_tactic"
        } or type(item.get("explicit_hole")) is not bool:
            raise RuntimeError("native proof-term input argument value is invalid")
        if item.get("explicit_hole") is not (item.get("syntax_kind") == "hole"):
            raise RuntimeError("native proof-term input hole marker is invalid")
        spelling = item.get("source_spelling")
        if type(spelling) is not str or spelling and (
            not _valid_qualified_symbol(spelling)
            or item.get("syntax_kind") not in {"formula", "module"}
        ):
            raise RuntimeError("native proof-term input spelling is invalid")
    holes = value.get("explicit_hole_count")
    implicits = value.get("implicit_argument_count")
    if type(holes) is not int or holes != sum(
        bool(item["explicit_hole"]) for item in inputs
    ):
        raise RuntimeError("native proof-term explicit hole count is invalid")
    if type(implicits) is not int or implicits < 0:
        raise RuntimeError("native proof-term implicit argument count is invalid")
    arguments = value.get("arguments")
    if type(arguments) is not list or len(arguments) != len(inputs) + implicits:
        raise RuntimeError("native proof-term elaborated argument count is invalid")
    proof_holes: set[int] = set()
    for position, item in enumerate(arguments, start=1):
        if type(item) is not dict or set(item) != {
            "position", "actual", "expected"
        } or item.get("position") != position:
            raise RuntimeError("native proof-term argument descriptor is invalid")
        actual = item.get("actual")
        expected = item.get("expected")
        if type(actual) is not dict or type(expected) is not dict:
            raise RuntimeError("native proof-term argument kinds are invalid")
        kind = actual.get("kind")
        if kind not in {"formula", "memory", "module", "proof"} or (
            expected.get("kind") != kind
        ) or type(actual.get("hole")) is not bool:
            raise RuntimeError("native proof-term argument kind mismatch")
        _validate_argument_value(actual, kind=kind)
        _validate_expected_argument(expected, kind=kind)
        if kind == "proof" and actual["hole"]:
            proof_holes.add(position)
        if kind != "proof" and actual["hole"]:
            raise RuntimeError("native non-proof argument remained a hole")
    residuals = value.get("residual_proof_premises")
    if type(residuals) is not list:
        raise RuntimeError("native residual proof premises must be a list")
    residual_positions = set()
    for item in residuals:
        if type(item) is not dict or set(item) != {
            "argument_position", "formula"
        }:
            raise RuntimeError("native residual proof premise is invalid")
        residual_positions.add(item.get("argument_position"))
        _validate_formula_descriptor(item.get("formula"))
    if residual_positions != proof_holes:
        raise RuntimeError("native residual premises disagree with proof holes")
    _validate_formula_descriptor(value.get("result"))
    if type(value.get("result_convertible_to_current_goal")) is not bool:
        raise RuntimeError(
            "native proof-term result/current-goal relation is invalid"
        )
    if value.get("can_concretize") is not True:
        raise RuntimeError("native descriptor is not fully concretized")
    return dict(value)


def validate_selected_application_binding_set_descriptor(
    value: dict[str, Any],
) -> dict[str, Any]:
    """Validate one native-owned bounded same-resource binding search."""

    required = {
        "operation",
        "selected_resource",
        "resolved_head",
        "module_slot_count",
        "candidate_module_term_count",
        "candidate_check_count",
        "typed_binding_count",
        "checked_completion_count",
        "population_complete",
        "checked_completions",
        "reason",
    }
    if set(value) != required:
        raise RuntimeError("native binding-set descriptor fields are invalid")
    operation = value.get("operation")
    resource = value.get("selected_resource")
    if operation not in {"apply", "exact"} or (
        type(resource) is not str or not resource
    ):
        raise RuntimeError("native binding-set identity is invalid")
    head = value.get("resolved_head")
    _validate_resolved_head(head)
    if str(head.get("identity") or "").rsplit(".", 1)[-1] != resource.rsplit(".", 1)[-1]:
        raise RuntimeError("native binding set resolved another theorem")
    counts = tuple(
        value.get(name)
        for name in (
            "module_slot_count",
            "candidate_module_term_count",
            "candidate_check_count",
            "typed_binding_count",
            "checked_completion_count",
        )
    )
    if (
        any(type(item) is not int or item < 0 for item in counts)
        or counts[0] < 1
        or counts[1] < 1
        or not 1 <= counts[2] <= 4096
        or counts[4] > counts[3]
    ):
        raise RuntimeError("native binding-set counts are invalid")
    complete = value.get("population_complete")
    reason = value.get("reason")
    if (
        type(complete) is not bool
        or type(reason) is not str
        or complete == bool(reason)
    ):
        raise RuntimeError("native binding-set completeness is invalid")
    completions = value.get("checked_completions")
    if type(completions) is not list:
        raise RuntimeError("native binding-set completions are invalid")
    if not complete and (counts[4] or completions):
        raise RuntimeError("incomplete native binding set exposed a prefix")
    if complete and counts[4] <= 4:
        if len(completions) != counts[4]:
            raise RuntimeError("small native binding set lost completions")
    elif completions:
        raise RuntimeError("oversized native binding set exposed a prefix")
    terms: list[str] = []
    for item in completions:
        if type(item) is not dict or set(item) != {
            "application_term", "candidate_tactic", "tactic_effect", "descriptor"
        }:
            raise RuntimeError("native checked application fields are invalid")
        term = item.get("application_term")
        if (
            type(term) is not str
            or not term
            or term != term.strip()
            or item.get("candidate_tactic") != f"{operation} ({term})."
            or item.get("tactic_effect") != "accepted_changed"
        ):
            raise RuntimeError("native checked application identity is invalid")
        descriptor = item.get("descriptor")
        if type(descriptor) is not dict:
            raise RuntimeError("native checked application descriptor is invalid")
        validate_proof_term_descriptor(descriptor)
        if operation in {"apply", "exact"} and (
            descriptor.get("result_convertible_to_current_goal") is not True
        ):
            raise RuntimeError("native checked application is not applicable")
        terms.append(term)
    if terms != sorted(set(terms)):
        raise RuntimeError("native checked applications are not canonical")
    return dict(value)


def _validate_formula_descriptor(value: object) -> None:
    if type(value) is not dict:
        raise RuntimeError("native formula descriptor must be an object")
    required = {"kind", "text", "type"}
    allowed = required | {"procedure", "comparison", "lossless", "boundary"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise RuntimeError("native formula descriptor fields are invalid")
    if any(
        type(value.get(field)) is not str or not value.get(field)
        for field in required
    ):
        raise RuntimeError("native formula descriptor values are invalid")
    if "procedure" in value and type(value["procedure"]) is not str:
        raise RuntimeError("native formula procedure is invalid")
    if "comparison" in value and type(value["comparison"]) is not str:
        raise RuntimeError("native formula comparison is invalid")
    if "lossless" in value and type(value["lossless"]) is not bool:
        raise RuntimeError("native formula lossless marker is invalid")
    if "boundary" in value:
        _validate_formula_boundary_descriptor(value["boundary"])


def _validate_formula_boundary_descriptor(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "role", "procedure_identity", "module"
    }:
        raise RuntimeError("native formula boundary fields are invalid")
    if (
        value.get("role") != "relation_left_probability"
        or type(value.get("procedure_identity")) is not str
        or not value.get("procedure_identity")
    ):
        raise RuntimeError("native formula boundary values are invalid")
    _validate_module_term_descriptor(value.get("module"))


def _validate_module_term_descriptor(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "term", "top_kind", "top_identity", "arguments"
    }:
        raise RuntimeError("native module term fields are invalid")
    if (
        type(value.get("term")) is not str
        or not value.get("term")
        or value.get("top_kind") not in {"local", "concrete"}
        or type(value.get("top_identity")) is not str
        or not value.get("top_identity")
        or type(value.get("arguments")) is not list
    ):
        raise RuntimeError("native module term values are invalid")
    for argument in value["arguments"]:
        _validate_module_term_descriptor(argument)


def _validate_argument_value(value: dict[str, Any], *, kind: str) -> None:
    common = {"kind", "hole"}
    if kind == "formula":
        if set(value) != common | {"formula"} or value["hole"]:
            raise RuntimeError("native formula argument value is invalid")
        _validate_formula_descriptor(value["formula"])
        return
    if kind in {"memory", "module"}:
        if (
            set(value) != common | {"identity"}
            or value["hole"]
            or type(value["identity"]) is not str
            or not value["identity"]
        ):
            raise RuntimeError(f"native {kind} argument value is invalid")
        return
    if value["hole"]:
        if not set(value).issubset(common | {"formula"}):
            raise RuntimeError("native proof-hole value is invalid")
        if "formula" in value:
            _validate_formula_descriptor(value["formula"])
        return
    if set(value) != common | {"head"}:
        raise RuntimeError("native proof argument value is invalid")
    _validate_resolved_head(value["head"])


def _validate_expected_argument(value: dict[str, Any], *, kind: str) -> None:
    if kind == "proof":
        if set(value) == {"kind", "name", "formula"}:
            _validate_formula_descriptor(value["formula"])
        elif set(value) == {"kind", "name", "type"} and (
            value.get("type") == "bool"
        ):
            pass
        else:
            raise RuntimeError("native expected proof argument is invalid")
    elif (
        set(value) != {"kind", "name", "type"}
        or type(value.get("type")) is not str
        or not value["type"]
    ):
        raise RuntimeError("native expected forall argument is invalid")
    if type(value.get("name")) is not str:
        raise RuntimeError("native expected argument name is invalid")


def _validate_resolved_head(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "kind", "identity", "type_arguments"
    }:
        raise RuntimeError("native resolved proof head is invalid")
    if value.get("kind") not in {"global", "local"} or (
        type(value.get("identity")) is not str or not value["identity"]
    ):
        raise RuntimeError("native resolved proof head identity is invalid")
    types = value.get("type_arguments")
    if type(types) is not list or any(type(item) is not str for item in types):
        raise RuntimeError("native resolved proof head types are invalid")


def _validate_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or _sha256_file(path) != expected:
        raise RuntimeError(f"native proof-term {label} file changed")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RuntimeError(f"cannot hash native dependency {path.name}") from exc
    return digest.hexdigest()
