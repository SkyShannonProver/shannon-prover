"""Cross-layer identity laws for the proof-state compiler foundation."""

from dataclasses import replace

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts import (
    DeclarationLoadRequest,
    EvidenceRef,
    ResourceLoadPlan,
    TargetRef,
    TransitionRef,
)
from workflow.proof_state_compiler.activation import ActivationPlan
from workflow.proof_state_compiler.cache import (
    material_resource_environment_cache_key,
)
from workflow.proof_state_compiler.input_gateway import LiveCompilerInput
from tests.proof_state_compiler_test_support import native_state


def _live_input() -> LiveCompilerInput:
    state_ref = StateRef(
        session_id="identity-foundation-session",
        state_version=4,
        goal_identity="identity-goal",
        goal_identity_required=True,
        committed_prefix_identity="p" * 64,
    )
    provenance = ProvenanceRef(
        producer="identity.fixture",
        authority="compiler.input.produced",
        source_sha256="a" * 64,
        artifact_ref="compiler_inputs/identity.json",
        source_event_id="identity-input-event",
        source_event_sequence=4,
        authoritative=True,
    )
    return LiveCompilerInput(
        snapshot=AuthoritativeSnapshotInput(
            state_ref=state_ref,
            provenance=provenance,
            target=TargetRef("eval/identity.ec", "identity"),
            transition=TransitionRef("inspected", state_ref, provenance.artifact_ref),
            goal_lines=("Current goal", "--------", "true"),
            goal_count=1,
            goal_count_known=True,
            closed=False,
            native_state=native_state(state_ref),
        ),
        environment=CompilationEnvironment("identity-environment", ()),
        source_snapshot_id="identity-snapshot",
    )


def _request(symbol: str) -> DeclarationLoadRequest:
    return DeclarationLoadRequest(
        request_id="same-request-id",
        producer_id="identity.request-producer",
        query_kind="symbol_declarations",
        scope="",
        declaration_kinds=("lemma",),
        member_name_terms=(),
        max_results=1,
        evidence_refs=(EvidenceRef(
            evidence_id="identity-evidence",
            source_kind="projected_goal",
            source_ref="compiler_inputs/identity.json#goal",
            source_sha256="b" * 64,
        ),),
        symbols=(symbol,),
    )


def test_resource_request_has_one_runtime_and_cache_identity() -> None:
    live = _live_input()
    first = _request("A.x")
    second = _request("B.y")
    activation = ActivationPlan(
        profile_id="identity-foundation",
        feature_modes=(),
        pass_feature_ids=(),
        certification_feature_ids=(),
    )

    assert first.runtime_payload() == first.identity_payload()
    assert first.identity_payload() != second.identity_payload()
    assert material_resource_environment_cache_key(
        live,
        plan=ResourceLoadPlan(live.snapshot.state_ref, (first,)),
        compiler=ProofStateCompiler(),
        activation_plan=activation,
    ) != material_resource_environment_cache_key(
        live,
        plan=ResourceLoadPlan(live.snapshot.state_ref, (second,)),
        compiler=ProofStateCompiler(),
        activation_plan=activation,
    )


def test_resource_cache_identity_changes_with_easycrypt_runtime() -> None:
    live = _live_input()
    first_runtime = EasyCryptRuntimeIdentity("build", "a" * 64)
    second_runtime = EasyCryptRuntimeIdentity("build", "b" * 64)
    first_live = replace(
        live,
        environment=replace(live.environment, easycrypt_runtime=first_runtime),
    )
    second_live = replace(
        live,
        environment=replace(live.environment, easycrypt_runtime=second_runtime),
    )
    request = _request("A.x")
    activation = ActivationPlan(
        profile_id="identity-foundation",
        feature_modes=(),
        pass_feature_ids=(),
        certification_feature_ids=(),
    )

    assert material_resource_environment_cache_key(
        first_live,
        plan=ResourceLoadPlan(first_live.snapshot.state_ref, (request,)),
        compiler=ProofStateCompiler(),
        activation_plan=activation,
    ) != material_resource_environment_cache_key(
        second_live,
        plan=ResourceLoadPlan(second_live.snapshot.state_ref, (request,)),
        compiler=ProofStateCompiler(),
        activation_plan=activation,
    )
