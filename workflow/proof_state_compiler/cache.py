"""Material identity and bounded reuse for compiler-service results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from core.easycrypt.proof_state_compiler.compiler import ProofStateCompiler
from core.easycrypt.proof_state_compiler.contracts import (
    CandidateSurface,
    CertificationResult,
    CompilerInvocationContext,
    LoadedDeclaration,
    ProvenanceRef,
    ResourceLoadPlan,
    StateRef,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
    freeze_json_object,
)
from workflow.proof_state_compiler.input_gateway import LiveCompilerInput
from workflow.proof_state_compiler.activation import ActivationPlan


_ResultT = TypeVar("_ResultT")


# Stable telemetry vocabulary for the three implemented reuse mechanisms.
# These are deliberately service-instance scopes: none authorizes cross-node,
# cross-evaluation, or global reuse of proof-state semantic results.
EXACT_OBSERVATION_CACHE_SCOPE = "service_instance_exact_observation"
MATERIAL_CERTIFICATION_CACHE_SCOPE = "service_instance_material_proof_state"
RESOURCE_ENVIRONMENT_CACHE_SCOPE = "service_instance_resource_environment"


@dataclass(frozen=True)
class ExactObservationCacheEntry(Generic[_ResultT]):
    key: str
    value: _ResultT
    origin_environment_id: str


@dataclass
class ExactObservationCompilerCache(Generic[_ResultT]):
    """Reuse a whole result only for the same manager observation identity."""

    _entry: ExactObservationCacheEntry[_ResultT] | None = None

    def get(self, key: str) -> ExactObservationCacheEntry[_ResultT] | None:
        entry = self._entry
        return entry if entry is not None and entry.key == key else None

    def store(
        self,
        *,
        key: str,
        value: _ResultT,
        origin_environment_id: str,
    ) -> None:
        self._entry = ExactObservationCacheEntry(
            key=key,
            value=value,
            origin_environment_id=origin_environment_id,
        )


@dataclass(frozen=True)
class MaterialProofStateFingerprint:
    """Semantic compiler-input identity, independent of view refreshes."""

    sha256: str

    def __post_init__(self) -> None:
        if (
            len(self.sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.sha256)
        ):
            raise ValueError("material proof-state fingerprint must be SHA-256")


@dataclass(frozen=True)
class MaterialCertificationCacheEntry:
    """Verifier results reusable after a fresh material-state equivalence check."""

    key: str
    material_state_sha256: str
    certifications: tuple[CertificationResult, ...]
    origin_state_ref: StateRef
    origin_input_provenance: ProvenanceRef
    origin_environment_id: str


@dataclass
class MaterialStateCertificationCache:
    """Bounded cache for expensive checks, never for current-state provenance."""

    max_entries: int = 32
    _entries: dict[str, MaterialCertificationCacheEntry] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.max_entries <= 0:
            raise ValueError("material certification cache must be bounded")

    def get(self, key: str) -> MaterialCertificationCacheEntry | None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._entries[key] = entry
        return entry

    def store(
        self,
        *,
        key: str,
        material_state_sha256: str,
        certifications: tuple[CertificationResult, ...],
        origin_state_ref: StateRef,
        origin_input_provenance: ProvenanceRef,
        origin_environment_id: str,
    ) -> None:
        if any(item.state_ref != origin_state_ref for item in certifications):
            raise ValueError("cached certifications cross origin StateRef")
        entry = MaterialCertificationCacheEntry(
            key=key,
            material_state_sha256=material_state_sha256,
            certifications=certifications,
            origin_state_ref=origin_state_ref,
            origin_input_provenance=origin_input_provenance,
            origin_environment_id=origin_environment_id,
        )
        self._entries.pop(key, None)
        self._entries[key] = entry
        while len(self._entries) > self.max_entries:
            oldest = next(iter(self._entries))
            del self._entries[oldest]


@dataclass(frozen=True)
class ResourceEnvironmentCacheEntry:
    """Immutable verifier-resolved P2 inputs reusable across proof states."""

    key: str
    loaded_declarations: tuple[LoadedDeclaration, ...]
    load_report: tuple[FrozenJsonObject, ...]
    origin_environment_id: str


@dataclass
class ResourceEnvironmentCache:
    """Bounded service/session-local cache for stable declaration environments.

    This cache never stores a proof-state compilation or certification.  Its
    entries are only immutable, hash-checked frontend resources obtained from
    a previously validated runtime load response.
    """

    max_entries: int = 32
    _entries: dict[str, ResourceEnvironmentCacheEntry] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.max_entries <= 0:
            raise ValueError("resource environment cache must be bounded")

    def get(self, key: str) -> ResourceEnvironmentCacheEntry | None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            # Dict insertion order is the bounded LRU order.
            self._entries[key] = entry
        return entry

    def store(
        self,
        *,
        key: str,
        loaded_declarations: tuple[LoadedDeclaration, ...],
        load_report: tuple[dict[str, object], ...],
        origin_environment_id: str,
    ) -> None:
        entry = ResourceEnvironmentCacheEntry(
            key=key,
            loaded_declarations=loaded_declarations,
            load_report=tuple(freeze_json_object(item) for item in load_report),
            origin_environment_id=origin_environment_id,
        )
        self._entries.pop(key, None)
        self._entries[key] = entry
        while len(self._entries) > self.max_entries:
            oldest = next(iter(self._entries))
            del self._entries[oldest]


def exact_observation_cache_key(
    live: LiveCompilerInput,
    *,
    history: tuple[str, ...],
    compiler: ProofStateCompiler,
    activation_plan: ActivationPlan,
    invocation_context: CompilerInvocationContext,
) -> str:
    """Hash a complete observation while excluding only read occurrence IDs.

    A cached result retains its original authoritative provenance and verifier
    witness. The caller must first obtain a fresh event-bound input and may
    reuse only when this complete observation identity is unchanged.
    """

    snapshot = live.snapshot
    state = snapshot.state_ref
    payload = {
        "state": state.identity_payload(),
        "target": {
            "source_file": snapshot.target.source_file,
            "lemma": snapshot.target.lemma,
        },
        "snapshot": {
            "goal_lines": list(snapshot.goal_lines),
            "goal_count": snapshot.goal_count,
            "goal_count_known": snapshot.goal_count_known,
            "closed": snapshot.closed,
            "native_state": _native_state_payload(live),
        },
        "committed_history": list(history),
        "invocation_context_sha256": invocation_context.identity_sha256,
        "source_units": [
            {
                "source_ref": unit.source_ref,
                "source_sha256": unit.source_sha256,
            }
            for unit in live.environment.source_units
        ],
        "easycrypt_runtime_identity_sha256": (
            live.environment.easycrypt_runtime.semantic_identity_sha256
            if live.environment.easycrypt_runtime is not None
            else ""
        ),
        "initial_loaded_declarations": [
            {
                "symbol": item.symbol,
                "source_ref": item.source_ref,
                "declaration_sha256": item.declaration_sha256,
            }
            for item in live.environment.loaded_declarations
        ],
        "native_semantic_observations": _native_semantic_payloads(
            live,
            include_request_identity=True,
        ),
        "compiler_features": [
            {
                "feature_id": item.spec.feature_id,
                "gate_status": item.spec.gate.status,
                "experiment_id": item.spec.gate.experiment_id,
                "certification_policy": item.spec.certification_policy,
                "execution_gate_id": item.execution_gate.gate_id,
                "execution_lifetime": item.execution_gate.lifetime,
                "produces_recovery_handoff": (
                    item.execution_gate.produces_recovery_handoff
                ),
                "accepts_recovery_handoff": (
                    item.execution_gate.accepts_recovery_handoff
                ),
            }
            for item in compiler.features
        ],
        # This cache stores P1-P4 plus certifications, never admission or
        # presentation. Audit and treatment may therefore share this identity
        # when their active pass/certification sets are identical.
        "activation": {
            "pass_feature_ids": list(activation_plan.pass_feature_ids),
            "certification_feature_ids": list(
                activation_plan.certification_feature_ids
            ),
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def material_proof_state_fingerprint(
    live: LiveCompilerInput,
    *,
    history: tuple[str, ...],
) -> MaterialProofStateFingerprint:
    """Identify the proof state seen by analysis and exact-tactic checking.

    ``state_version`` and input event provenance are observation identities,
    not proof semantics.  They are deliberately absent.  Session lineage,
    committed prefix, exact goal/scope/program data, history, and every source
    or declaration hash remain material and therefore fail closed on drift.
    """

    snapshot = live.snapshot
    state = snapshot.state_ref
    payload = {
        "state": {
            "session_id": state.session_id,
            "goal_identity": state.goal_identity,
            "goal_identity_required": state.goal_identity_required,
            "committed_prefix_identity": state.committed_prefix_identity,
        },
        "target": {
            "source_file": snapshot.target.source_file,
            "lemma": snapshot.target.lemma,
        },
        "snapshot": {
            "goal_lines": list(snapshot.goal_lines),
            "goal_count": snapshot.goal_count,
            "goal_count_known": snapshot.goal_count_known,
            "closed": snapshot.closed,
            "native_state": _native_state_payload(live),
        },
        "committed_history": list(history),
        "source_units": [
            {
                "source_ref": unit.source_ref,
                "source_sha256": unit.source_sha256,
            }
            for unit in live.environment.source_units
        ],
        "easycrypt_runtime_identity_sha256": (
            live.environment.easycrypt_runtime.semantic_identity_sha256
            if live.environment.easycrypt_runtime is not None
            else ""
        ),
        "loaded_declarations": [
            {
                "symbol": item.symbol,
                "source_ref": item.source_ref,
                "declaration_sha256": item.declaration_sha256,
            }
            for item in live.environment.loaded_declarations
        ],
        "native_semantic_observations": _native_semantic_payloads(
            live,
            include_request_identity=False,
        ),
    }
    return MaterialProofStateFingerprint(_sha256_json(payload))


def material_certification_cache_key(
    fingerprint: MaterialProofStateFingerprint,
    candidates: CandidateSurface,
    *,
    eligible_feature_ids: tuple[str, ...],
) -> str:
    """Bind reusable checks to exact candidate payloads and policies."""

    eligible = set(eligible_feature_ids)
    payload = {
        "material_state_sha256": fingerprint.sha256,
        "eligible_feature_ids": list(eligible_feature_ids),
        "actions": [
            {
                "candidate_id": item.candidate_id,
                "feature_id": item.feature_id,
                "intent": item.intent,
                "payload_sha256": frozen_json_sha256(item.payload),
                "certification_policy": item.certification_policy,
                "unresolved_premises": list(item.unresolved_premises),
            }
            for item in candidates.actions
            if item.feature_id in eligible
        ],
    }
    return _sha256_json(payload)


def material_resource_environment_cache_key(
    live: LiveCompilerInput,
    *,
    plan: ResourceLoadPlan,
    compiler: ProofStateCompiler,
    activation_plan: ActivationPlan,
) -> str:
    """Identify stable declaration inputs independently of proof-state identity.

    A service instance is already manager-session scoped, but session and
    target identities remain explicit so this key is safe to inspect and test.
    State version, goal text, history, and per-read event occurrences are
    intentionally absent: only P2 resource authority is reused.
    """

    snapshot = live.snapshot
    payload = {
        "session_id": snapshot.state_ref.session_id,
        "target": {
            "source_file": snapshot.target.source_file,
            "lemma": snapshot.target.lemma,
        },
        "source_units": [
            {
                "source_ref": unit.source_ref,
                "source_sha256": unit.source_sha256,
            }
            for unit in live.environment.source_units
        ],
        "easycrypt_runtime_identity_sha256": (
            live.environment.easycrypt_runtime.semantic_identity_sha256
            if live.environment.easycrypt_runtime is not None
            else ""
        ),
        "requests": [
            request.identity_payload()
            for request in plan.requests
        ],
        "pass_feature_ids": list(activation_plan.pass_feature_ids),
        "compiler_features": [
            {
                "feature_id": item.spec.feature_id,
                "gate_status": item.spec.gate.status,
                "experiment_id": item.spec.gate.experiment_id,
                "execution_gate_id": item.execution_gate.gate_id,
                "execution_lifetime": item.execution_gate.lifetime,
                "produces_recovery_handoff": (
                    item.execution_gate.produces_recovery_handoff
                ),
                "accepts_recovery_handoff": (
                    item.execution_gate.accepts_recovery_handoff
                ),
            }
            for item in compiler.features
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _native_semantic_payloads(
    live: LiveCompilerInput,
    *,
    include_request_identity: bool,
) -> list[dict[str, object]]:
    """Return native facts at exact-observation or material-state identity."""

    payloads = [{
        "feature_id": item.feature_id,
        "producer_id": item.producer_id,
        "query_kind": item.query_kind,
        "query_payload": item.query.to_payload(),
        "evaluation_prefix": list(item.evaluation_prefix),
        "status": item.status,
        "result_formula": item.result_formula,
        "descriptor": (
            item.descriptor.to_payload() if item.descriptor is not None else {}
        ),
        "structured_error": item.structured_error.to_dict(),
        "runtime_identity_sha256": item.runtime_identity_sha256,
        "companion_identity_sha256": item.companion_identity_sha256,
    } for item in live.environment.native_semantic_observations]
    if include_request_identity:
        for payload, item in zip(
            payloads,
            live.environment.native_semantic_observations,
        ):
            payload["request_id"] = item.request_id
            payload["request_identity_sha256"] = (
                item.request_identity_sha256
            )
    return payloads


def _native_state_payload(live: LiveCompilerInput) -> dict[str, object] | None:
    """Return material typed state without event-occurrence identity."""

    native = live.snapshot.native_state
    if native is None:
        return None
    return {
        "projection": native.projection.to_dict(),
        "runtime_identity_sha256": native.runtime_identity_sha256,
        "companion_identity_sha256": native.companion_identity_sha256,
    }
