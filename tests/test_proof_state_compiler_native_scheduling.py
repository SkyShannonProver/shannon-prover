"""Generic P3 native-dependency scheduling, authority, and activation tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.native_semantics import NativeCompanionIdentity
from core.easycrypt.session_projection import active_goal_hash_from_raw
from core.easycrypt.proof_state_compiler.contracts import (
    EvidenceRef,
    INTRINSIC,
    NativeProofTermElaborationQuery,
    NativePlanningBudget,
    NativeSemanticExecutionUnit,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    StateRef,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)
from workflow.proof_state_compiler.activation import AUDIT, OFF
from workflow.proof_state_compiler.assembly import assemble_feature_set
from workflow.proof_state_compiler.service import (
    CompilerServiceSkipped,
    ProofStateCompilerService,
)
from workflow.proof_state_compiler.input_gateway import (
    live_compiler_input,
    native_semantic_observations,
)
from tests.proof_state_compiler_test_support import (
    native_state,
    native_state_manager_result,
)


RUNTIME = EasyCryptRuntimeIdentity(
    build_id="native-scheduling-test",
    binary_sha256="a" * 64,
)
COMPANION = NativeCompanionIdentity(
    protocol_version=2,
    easycrypt_toolchain_build_id=RUNTIME.build_id,
    easycrypt_library_sha256="b" * 64,
    companion_binary_sha256="c" * 64,
    why3_config_sha256="d" * 64,
)
FEATURE_ID = "synthetic_native_semantic_consumer"


def _accepted_descriptor() -> dict[str, Any]:
    return {
        "resolved_head": {
            "kind": "global",
            "identity": "Core.trueI",
            "type_arguments": [],
        },
        "input_mode": "implicit",
        "input_arguments": [],
        "explicit_hole_count": 0,
        "implicit_argument_count": 0,
        "arguments": [],
        "can_concretize": True,
        "residual_proof_premises": [],
        "result": {"kind": "true", "text": "true", "type": "bool"},
        "result_convertible_to_current_goal": True,
    }


def _accepted_module_proof_descriptor() -> dict[str, Any]:
    premise = {
        "kind": "bounded_hoare_function",
        "text": "islossless Top.D2(O).O.f",
        "type": "bool",
        "procedure": "Top.D2(O).O./f",
        "comparison": "=",
        "lossless": True,
    }
    result = {
        "kind": "bounded_hoare_function",
        "text": "islossless Top.Adv_MAC_to_F(A, Top.D2(O).O).guess",
        "type": "bool",
        "procedure": "Top.Adv_MAC_to_F(A, Top.D2(O).O)./guess",
        "comparison": "=",
        "lossless": True,
    }
    return {
        "resolved_head": {
            "kind": "global",
            "identity": "Top.Alossless_F",
            "type_arguments": [],
        },
        "input_mode": "implicit",
        "input_arguments": [
            {
                "position": 1,
                "syntax_kind": "module",
                "explicit_hole": False,
                "source_spelling": "",
            },
            {
                "position": 2,
                "syntax_kind": "hole",
                "explicit_hole": True,
                "source_spelling": "",
            },
        ],
        "explicit_hole_count": 1,
        "implicit_argument_count": 0,
        "arguments": [
            {
                "position": 1,
                "actual": {
                    "kind": "module",
                    "hole": False,
                    "identity": "Top.D2(O).O",
                },
                "expected": {
                    "kind": "module",
                    "name": "O",
                    "type": "NativeDescriptorOracle",
                },
            },
            {
                "position": 2,
                "actual": {
                    "kind": "proof",
                    "hole": True,
                    "formula": premise,
                },
                "expected": {"kind": "proof", "name": "", "formula": premise},
            },
        ],
        "can_concretize": True,
        "residual_proof_premises": [
            {"argument_position": 2, "formula": premise},
        ],
        "result": result,
        "result_convertible_to_current_goal": True,
    }


def _request_native_fact(proof_ir, coordinate, invocation, budget):
    del coordinate, invocation, budget
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id="synthetic.trueI",
        producer_id=FEATURE_ID,
        query=NativeProofTermElaborationQuery(
            operation="apply",
            application_term="trueI",
        ),
        evidence_refs=(EvidenceRef(
            evidence_id="synthetic.native.request",
            source_kind="projected_goal",
            source_ref=proof_ir.provenance.artifact_ref,
            source_sha256=proof_ir.provenance.source_sha256,
        ),),
    )
    return NativeSemanticRequestProduction.ready(FEATURE_ID, (request,))


def _request_two_native_facts(proof_ir, coordinate, invocation, budget):
    first = _request_native_fact(
        proof_ir, coordinate, invocation, budget
    ).requests[0]
    requests = (
        first,
        NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id="synthetic.trueI.with-hole",
            producer_id=FEATURE_ID,
            query=NativeProofTermElaborationQuery(
                operation="apply",
                application_term="trueI _",
            ),
            evidence_refs=first.evidence_refs,
        ),
    )
    return NativeSemanticRequestProduction.ready(FEATURE_ID, requests)


def _same_unit_request(*, producer_id: str, request_id: str):
    def produce(proof_ir, coordinate, invocation, budget):
        base = _request_native_fact(
            proof_ir, coordinate, invocation, budget
        ).requests[0]
        request = NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=request_id,
            producer_id=producer_id,
            query=base.query,
            evidence_refs=base.evidence_refs,
        )
        return NativeSemanticRequestProduction.ready(
            producer_id, (request,)
        )

    return produce


def _many_requests(
    *,
    producer_id: str,
    count: int,
    coalesce: bool = False,
):
    def produce(proof_ir, coordinate, invocation, budget):
        del coordinate, invocation, budget
        evidence = (EvidenceRef(
            evidence_id=f"{producer_id}.native.request",
            source_kind="projected_goal",
            source_ref=proof_ir.provenance.artifact_ref,
            source_sha256=proof_ir.provenance.source_sha256,
        ),)
        requests = tuple(
            NativeSemanticRequest(
                state_ref=proof_ir.state_ref,
                request_id=f"{producer_id}:{index}",
                producer_id=producer_id,
                query=NativeProofTermElaborationQuery(
                    operation="apply",
                    application_term=(
                        f"{producer_id}.trueI"
                        if coalesce
                        else f"{producer_id}.trueI " + "_ " * index
                    ).strip(),
                ),
                evidence_refs=evidence,
            )
            for index in range(count)
        )
        return NativeSemanticRequestProduction.ready(
            producer_id,
            requests,
            considered_candidate_count=count,
        )

    return produce


def _feature(
    request_producer=_request_native_fact,
    *,
    feature_id: str = FEATURE_ID,
) -> FeatureDefinition:
    return FeatureDefinition(
        spec=FeatureSpec(
            feature_id=feature_id,
            gate=ExperimentGate(
                status="candidate",
                evidence_ledger_ids=("SYNTHETIC",),
                experiment_id="native-scheduling-sentinel",
            ),
            correctness_contract="synthetic scheduling sentinel only",
            provenance_contract="current native.semantic.batch.produced event",
            native_semantic_dependencies=("NativeProofTermDescriptor",),
            shannon_delta_contract="one synthetic exact native request",
            lexical_prefilter_contract="none",
            required_ir_capabilities=(
                "NativeSemanticObservation",
                "NativeProofTermDescriptor",
            ),
            certification_policy="no-visible-action",
            strategy_contracts=(StrategyContract(
                strategy_class=INTRINSIC,
                rationale="the sentinel emits no agent-visible proof choice",
            ),),
        ),
        native_semantic_request_producers=(request_producer,),
    )


class _Runtime:
    def __init__(
        self,
        source: Path,
        *,
        accepted_descriptor: dict[str, Any] | None = None,
    ) -> None:
        self.source = source
        self.accepted_descriptor = accepted_descriptor
        self.state_version = 0
        self.session_id = "native-scheduling-session"
        self.goal_lines = [
            "Current goal",
            "------------------------------------------------------------------------",
            "true",
        ]
        self.goal_identity = active_goal_hash_from_raw("\n".join(self.goal_lines))
        self.prefix_identity = "d" * 64
        self.input_calls = 0
        self.native_calls = 0

    def committed_history(self) -> list[str]:
        return []

    def read_compiler_input_v2(self, *, timeout: int = 30) -> dict[str, Any]:
        del timeout
        self.input_calls += 1
        source_sha256 = hashlib.sha256(self.source.read_bytes()).hexdigest()
        return {
            "snapshot": {
                "schema_version": 5,
                "kind": "proof_state_compiler_input",
                "ok": True,
                "snapshot_id": f"native-snapshot-{self.input_calls}",
                "target": {
                    "source_file": str(self.source),
                    "source_sha256": source_sha256,
                    "lemma": "native_scheduling_sentinel",
                },
                "transition": {"kind": "inspected"},
                "easycrypt_runtime": RUNTIME.to_payload(),
                "state": {
                    "session_id": self.session_id,
                    "state_version": self.state_version,
                    "goal_identity": self.goal_identity,
                    "goal_identity_required": True,
                    "committed_prefix_identity": self.prefix_identity,
                    "goal_lines": self.goal_lines,
                    "goal_count": 1,
                    "goal_count_known": True,
                    "closed": False,
                },
            },
            "authority": {
                "event_type": "compiler.input.produced",
                "event_id": f"compiler-input-{self.input_calls}",
                "event_sequence": self.input_calls,
                "artifact_ref": "compiler_inputs/current.json",
                "artifact_sha256": "e" * 64,
            },
        }

    def project_native_state(
        self,
        *,
        request_id: str,
        max_nodes: int = 4096,
        max_depth: int = 128,
        timeout: int = 30,
    ) -> dict[str, Any]:
        del max_nodes, max_depth, timeout
        state_ref = StateRef(
            session_id=self.session_id,
            state_version=self.state_version,
            goal_identity=self.goal_identity,
            goal_identity_required=True,
            committed_prefix_identity=self.prefix_identity,
        )
        result = native_state_manager_result(
            native_state(state_ref),
            RUNTIME,
            event_id=f"native-state-{self.input_calls}",
            event_sequence=40 + self.input_calls,
            goal_before="\n".join(self.goal_lines),
        )
        result["result"]["request"]["request_id"] = request_id
        return result

    def execute_native_semantic_batch(
        self,
        *,
        batch_id: str,
        requests: tuple[dict[str, object], ...],
        timeout: int = 30,
    ) -> dict[str, Any]:
        del timeout
        self.native_calls += 1
        members = [{
            **dict(request),
            **(
                {
                    "status": "accepted",
                    "result_formula": self.accepted_descriptor["result"]["text"],
                    "descriptor": self.accepted_descriptor,
                    "structured_error": {},
                }
                if self.accepted_descriptor is not None
                else {
                    "status": "rejected",
                    "result_formula": "",
                    "descriptor": {},
                    "structured_error": {
                        "code": "not_functional",
                        "message": "synthetic structured rejection",
                    },
                }
            ),
            "elapsed_ms": 3,
        } for request in requests]
        result = {
            "schema_version": 17,
            "kind": "easycrypt_native_semantic_batch_result",
            "ok": True,
            "query_id": f"native-query-{self.native_calls}",
            "request": {
                "batch_id": batch_id,
                "members": [dict(item) for item in requests],
            },
            "state": {
                "session_id": self.session_id,
                "state_version": self.state_version,
                "goal_identity": self.goal_identity,
                "goal_identity_required": True,
                "committed_prefix_identity": self.prefix_identity,
            },
            "inputs": {
                "context_sha256": "f" * 64,
                "history_sha256": "0" * 64,
            },
            "easycrypt_runtime": RUNTIME.to_payload(),
            "native_companion": COMPANION.identity_payload(),
            "result": {
                "goal_before": "\n".join(self.goal_lines),
                "members": members,
                "cache_state": "warm",
                "build_elapsed_ms": 0,
                "execution_elapsed_ms": 3,
                "elapsed_ms": 3,
            },
            "session_files_unchanged": True,
        }
        return {
            "result": result,
            "authority": {
                "event_type": "native.semantic.batch.produced",
                "event_id": f"native-event-{self.native_calls}",
                "event_sequence": 100 + self.native_calls,
                "artifact_ref": (
                    f"native_semantic_batches/{self.native_calls}.json"
                ),
                "artifact_sha256": "1" * 64,
            },
            "history_unchanged": True,
            "state_version_before": self.state_version,
            "state_version_after": self.state_version,
        }

    def certify_exact_tactic(self, tactic: str, *, timeout: int = 30):
        raise AssertionError((tactic, timeout))


def _service(
    source: Path,
    mode: str,
    *,
    accepted_descriptor: dict[str, Any] | None = None,
) -> tuple[ProofStateCompilerService, _Runtime]:
    runtime = _Runtime(source, accepted_descriptor=accepted_descriptor)
    assembly = assemble_feature_set(
        profile_id=f"native-{mode}",
        features=(_feature(),),
        modes={FEATURE_ID: mode},
    )
    return ProofStateCompilerService.create(
        runtime=runtime,
        assembly=assembly,
    ), runtime


def test_active_feature_runs_one_native_dependency_cycle(tmp_path: Path) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    service, runtime = _service(source, AUDIT)

    raw_input = runtime.read_compiler_input_v2()
    unresolved = live_compiler_input(
        raw_input,
        runtime.project_native_state(request_id="direct-native-state"),
        native_state_request_id="direct-native-state",
    )
    with pytest.raises(
        ValueError,
        match="unresolved native semantic dependencies",
    ):
        service.compiler.compile(
            unresolved.snapshot,
            unresolved.environment,
        )

    result = service.compile_current_state()

    assert runtime.native_calls == 1
    assert len(result.bundle.proof_ir.native_semantic_observations) == 1
    observation = result.bundle.proof_ir.native_semantic_observations[0]
    assert observation.status == "rejected"
    assert observation.provenance.authority == "native.semantic.batch.produced"
    assert result.telemetry["native_semantics"]["planned_request_count"] == 1
    assert result.telemetry["native_semantics"]["rejected"] == 1
    assert result.telemetry["exact_observation_cache"]["stored"] is False
    timings = result.telemetry["timings_ms"]
    assert timings["compiler_input_transport"] >= 0
    assert timings["native_state_projection"] >= 0
    assert timings["native_state_lowering"] >= 0
    assert (
        timings["manager_state_snapshot"]
        + timings["compiler_input_transport"]
        + timings["native_state_projection"]
        + timings["native_state_lowering"]
        <= timings["input_initial"]
    )

    # Native authority is deliberately not hidden behind whole-result reuse.
    service.compile_current_state()
    assert runtime.native_calls == 2


def test_one_native_batch_carries_the_whole_ordered_plan(tmp_path: Path) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    runtime = _Runtime(source)
    assembly = assemble_feature_set(
        profile_id="native-batch-audit",
        features=(_feature(_request_two_native_facts),),
        modes={FEATURE_ID: AUDIT},
    )
    service = ProofStateCompilerService.create(
        runtime=runtime,
        assembly=assembly,
    )

    result = service.compile_current_state()

    observations = result.bundle.proof_ir.native_semantic_observations
    assert runtime.native_calls == 1
    assert [item.request_id for item in observations] == [
        "synthetic.trueI",
        "synthetic.trueI.with-hole",
    ]
    assert [item.batch_index for item in observations] == [0, 1]
    assert len({item.batch_id for item in observations}) == 1
    assert len({item.provenance.source_event_id for item in observations}) == 1
    assert result.telemetry["native_semantics"]["planned_request_count"] == 2
    assert result.telemetry["native_semantics"]["batch_count"] == 1


def test_identical_native_units_execute_once_and_fan_out_to_each_producer(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    first_id = "synthetic_native_consumer_a"
    second_id = "synthetic_native_consumer_b"
    runtime = _Runtime(source)
    assembly = assemble_feature_set(
        profile_id="native-coalescing-audit",
        features=(
            _feature(
                _same_unit_request(
                    producer_id=first_id,
                    request_id="consumer-a.trueI",
                ),
                feature_id=first_id,
            ),
            _feature(
                _same_unit_request(
                    producer_id=second_id,
                    request_id="consumer-b.trueI",
                ),
                feature_id=second_id,
            ),
        ),
        modes={first_id: AUDIT, second_id: AUDIT},
    )
    service = ProofStateCompilerService.create(
        runtime=runtime,
        assembly=assembly,
    )

    result = service.compile_current_state()

    observations = result.bundle.proof_ir.native_semantic_observations
    assert runtime.native_calls == 1
    assert [item.request_id for item in observations] == [
        "consumer-a.trueI",
        "consumer-b.trueI",
    ]
    assert [item.producer_id for item in observations] == [first_id, second_id]
    assert [item.feature_id for item in observations] == [first_id, second_id]
    assert [item.batch_index for item in observations] == [0, 0]
    assert [item.batch_size for item in observations] == [1, 1]
    assert len({item.request_identity_sha256 for item in observations}) == 2
    assert len({item.provenance.source_event_id for item in observations}) == 1
    telemetry = result.telemetry["native_semantics"]
    assert telemetry["planned_request_count"] == 2
    assert telemetry["observation_count"] == 2
    assert telemetry["batch_count"] == 1
    assert telemetry["batches"][0]["execution_unit_count"] == 1
    assert telemetry["batches"][0]["consumer_request_count"] == 2
    assert [
        item["feature_id"] for item in telemetry["observations"]
    ] == [first_id, second_id]


def test_more_than_eight_consumers_fit_when_they_coalesce_to_one_native_unit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    feature_id = "synthetic_nine_consumer_fanout"
    runtime = _Runtime(source)
    assembly = assemble_feature_set(
        profile_id="native-nine-consumer-fanout-audit",
        features=(_feature(
            _many_requests(
                producer_id=feature_id,
                count=9,
                coalesce=True,
            ),
            feature_id=feature_id,
        ),),
        modes={feature_id: AUDIT},
    )

    result = ProofStateCompilerService.create(
        runtime=runtime, assembly=assembly
    ).compile_current_state()

    assert runtime.native_calls == 1
    assert len(result.bundle.proof_ir.native_semantic_observations) == 9
    native = result.telemetry["native_semantics"]
    assert native["planned_request_count"] == 9
    assert native["batches"][0]["execution_unit_count"] == 1
    assert native["batches"][0]["consumer_request_count"] == 9


def test_shared_native_execution_cap_cannot_be_expanded_locally() -> None:
    with pytest.raises(ValueError, match="execution limit exceeds"):
        NativePlanningBudget(max_execution_units=9)


def test_over_budget_feature_typed_abstains_without_hiding_independent_work(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    over_id = "synthetic_over_budget"
    fit_id = "synthetic_within_budget"
    runtime = _Runtime(source)
    assembly = assemble_feature_set(
        profile_id="native-feature-isolation-audit",
        features=(
            _feature(
                _many_requests(producer_id=over_id, count=9),
                feature_id=over_id,
            ),
            _feature(
                _many_requests(producer_id=fit_id, count=1),
                feature_id=fit_id,
            ),
        ),
        modes={over_id: AUDIT, fit_id: AUDIT},
    )

    result = ProofStateCompilerService.create(
        runtime=runtime, assembly=assembly
    ).compile_current_state()

    assert runtime.native_calls == 1
    observations = result.bundle.proof_ir.native_semantic_observations
    assert [item.producer_id for item in observations] == [fit_id]
    decisions = result.telemetry["native_semantics"]["planning"]["decisions"]
    over = [item for item in decisions if item["feature_id"] == over_id]
    assert over
    assert {item["disposition"] for item in over} == {"abstained"}
    assert {item["reason"] for item in over} == {
        "feature_complete_request_population_exceeds_native_budget"
    }


def test_collective_budget_conflict_abstains_independently_of_feature_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    first_id = "synthetic_collective_a"
    second_id = "synthetic_collective_b"
    definitions = (
        _feature(
            _many_requests(producer_id=first_id, count=5),
            feature_id=first_id,
        ),
        _feature(
            _many_requests(producer_id=second_id, count=5),
            feature_id=second_id,
        ),
    )
    observed = []
    for index, features in enumerate((definitions, tuple(reversed(definitions)))):
        runtime = _Runtime(source)
        assembly = assemble_feature_set(
            profile_id=f"native-collective-conflict-{index}",
            features=features,
            modes={first_id: AUDIT, second_id: AUDIT},
        )
        result = ProofStateCompilerService.create(
            runtime=runtime, assembly=assembly
        ).compile_current_state()
        assert runtime.native_calls == 0
        decisions = result.telemetry["native_semantics"]["planning"]["decisions"]
        observed.append(sorted(
            (item["feature_id"], item["disposition"], item["reason"])
            for item in decisions
        ))
    assert observed[0] == observed[1]
    assert {
        (feature_id, disposition, reason)
        for feature_id, disposition, reason in observed[0]
    } == {
        (first_id, "abstained", "shared_native_budget_conflict"),
        (second_id, "abstained", "shared_native_budget_conflict"),
    }


def test_off_feature_executes_no_native_producer(tmp_path: Path) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text("lemma native_scheduling_sentinel : true.\n", encoding="utf-8")
    service, runtime = _service(source, OFF)

    result = service.compile_current_state()

    assert runtime.native_calls == 0
    assert isinstance(result, CompilerServiceSkipped)
    assert result.execution_plan.configured_feature_ids == ()
    assert result.telemetry["timings_ms"]["native_semantic_execution"] == 0


def test_feature_producer_cannot_invent_native_evaluation_prefix(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text(
        "lemma native_scheduling_sentinel : true.\n",
        encoding="utf-8",
    )

    def invent_prefix(proof_ir, coordinate, invocation, budget):
        base = _request_native_fact(
            proof_ir, coordinate, invocation, budget
        ).requests[0]
        return NativeSemanticRequestProduction.ready(
            FEATURE_ID,
            (NativeSemanticRequest(
                state_ref=base.state_ref,
                request_id=base.request_id,
                producer_id=base.producer_id,
                query=base.query,
                evidence_refs=base.evidence_refs,
                evaluation_prefix=("symmetry.",),
            ),),
        )

    runtime = _Runtime(source)
    service = ProofStateCompilerService.create(
        runtime=runtime,
        assembly=assemble_feature_set(
            profile_id="native-prefix-authority-audit",
            features=(_feature(invent_prefix),),
            modes={FEATURE_ID: AUDIT},
        ),
    )

    with pytest.raises(
        ValueError,
        match="feature producer cannot choose a native evaluation prefix",
    ):
        service.compile_current_state()
    assert runtime.native_calls == 0


def test_accepted_native_descriptor_reaches_shared_proof_ir(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text(
        "lemma native_scheduling_sentinel : true.\n",
        encoding="utf-8",
    )
    service, _ = _service(
        source,
        AUDIT,
        accepted_descriptor=_accepted_descriptor(),
    )

    result = service.compile_current_state()

    observation = result.bundle.proof_ir.native_semantic_observations[0]
    assert observation.status == "accepted"
    assert observation.descriptor is not None
    assert observation.descriptor.to_payload() == _accepted_descriptor()
    record = result.telemetry["native_semantics"]["observations"][0]
    assert record["descriptor_present"] is True
    assert record["resolved_head"]["identity"] == "Core.trueI"


def test_module_and_proof_descriptor_survives_gateway_round_trip(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text(
        "lemma native_scheduling_sentinel : true.\n",
        encoding="utf-8",
    )
    descriptor = _accepted_module_proof_descriptor()
    service, _ = _service(
        source,
        AUDIT,
        accepted_descriptor=descriptor,
    )

    observation = (
        service.compile_current_state()
        .bundle.proof_ir.native_semantic_observations[0]
    )

    assert observation.descriptor is not None
    assert observation.descriptor.to_payload() == descriptor
    assert tuple(
        argument.kind for argument in observation.descriptor.arguments
    ) == ("module", "proof")
    assert observation.descriptor.arguments[0].resolved_identity == (
        "Top.D2(O).O"
    )
    assert observation.descriptor.residual_proof_premises[0].formula.procedure == (
        "Top.D2(O).O./f"
    )


def test_native_state_join_rejects_goal_body_identity_drift(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text(
        "lemma native_scheduling_sentinel : true.\n",
        encoding="utf-8",
    )
    service, runtime = _service(source, OFF)
    raw_input = runtime.read_compiler_input_v2()
    native_result = runtime.project_native_state(request_id="native-drift")
    native_result["result"]["result"]["goal_before"] = (
        "Current goal\n----------------------------------------\nfalse"
    )

    with pytest.raises(ValueError, match="goal text disagrees"):
        live_compiler_input(
            raw_input,
            native_result,
            native_state_request_id="native-drift",
        )


def test_native_semantic_join_rejects_goal_body_identity_drift(
    tmp_path: Path,
) -> None:
    source = tmp_path / "native_scheduling.ec"
    source.write_text(
        "lemma native_scheduling_sentinel : true.\n",
        encoding="utf-8",
    )
    runtime = _Runtime(source)
    state_ref = StateRef(
        session_id=runtime.session_id,
        state_version=runtime.state_version,
        goal_identity=runtime.goal_identity,
        goal_identity_required=True,
        committed_prefix_identity=runtime.prefix_identity,
    )
    request = NativeSemanticRequest(
        state_ref=state_ref,
        request_id="native-semantic-drift",
        producer_id=FEATURE_ID,
        query=NativeProofTermElaborationQuery(
            operation="apply",
            application_term="trueI",
        ),
        evidence_refs=(EvidenceRef(
            evidence_id="native-semantic-drift",
            source_kind="projected_goal",
            source_ref="compiler_inputs/current.json",
            source_sha256="e" * 64,
        ),),
    )
    batch_id = "native-semantic-drift-batch"
    unit = NativeSemanticExecutionUnit(
        unit_id=request.semantic_unit_sha256,
        state_ref=state_ref,
        query=request.query,
        requests=(request,),
    )
    manager_result = runtime.execute_native_semantic_batch(
        batch_id=batch_id,
        requests=(unit.runtime_payload(),),
    )
    manager_result["result"]["result"]["goal_before"] = (
        "Current goal\n----------------------------------------\nfalse"
    )

    with pytest.raises(ValueError, match="batch goal disagrees"):
        native_semantic_observations(
            manager_result,
            execution_units=(unit,),
            expected_batch_id=batch_id,
            expected_runtime=RUNTIME,
        )
