"""Typed historical fixtures used only by deterministic validation harnesses.

These values are not runtime fallbacks. Live compiler service calls obtain the
same structure from ``native.state.produced``; archived one-step validators
need an explicit typed equivalent of their ledger-pinned historical state.
"""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    NativeProofStateSnapshot,
    ProvenanceRef,
    StateRef,
    freeze_json_object,
)


def archived_m05_native_state(state_ref: StateRef) -> NativeProofStateSnapshot:
    truth = _node("true", "true")
    bound = _node("operator_application", "1%r", type_text="real")
    calls = [
        _call("D2(O).O.init", 1),
        _call("Adv_MAC_to_F(A, D2(O).O).guess", 2),
    ]
    projection = {
        "complete": True,
        "truncation_reasons": [],
        "node_count": 8,
        "open_goal_count": 1,
        "focused_goal": {
            "judgment_kind": "bounded_hoare_statement",
            "formula": _node(
                "bounded_hoare_statement",
                "phoare[statement : true ==> true] = 1%r",
                children=[truth, truth, bound],
                child_roles=["precondition", "postcondition", "bound"],
                comparison="=",
                memory="&m",
            ),
            "programs": [{
                "side": "single",
                "role": "body",
                "memory": "&m",
                "statement": {
                    "kind": "statement",
                    "complete": True,
                    "structural_path": ["single"],
                    "text": " ".join(item["text"] for item in calls),
                    "instructions": calls,
                },
            }],
            "procedures": [],
        },
        "local_declarations": [],
    }
    return NativeProofStateSnapshot(
        state_ref=state_ref,
        request_id="archived-m05-native-fixture",
        projection=freeze_json_object(projection),
        runtime_identity_sha256="c" * 64,
        companion_identity_sha256="d" * 64,
        provenance=ProvenanceRef(
            producer="validation.archived_m05_native_fixture",
            authority="native.state.produced",
            source_sha256="e" * 64,
            artifact_ref="fixtures/native_state/m05_post_proc.json",
            source_event_id="archived-m05-native-state",
            source_event_sequence=1,
            authoritative=True,
        ),
        elapsed_ms=0,
    )


def _node(
    kind: str,
    text: str,
    *,
    type_text: str = "bool",
    children: list[dict] | None = None,
    child_roles: list[str] | None = None,
    **properties: object,
) -> dict:
    value = {
        "kind": kind,
        "complete": True,
        "text": text,
        "type": type_text,
        "children": list(children or []),
        **properties,
    }
    if child_roles:
        value["child_roles"] = child_roles
    return value


def _call(procedure: str, position: int) -> dict:
    return {
        "kind": "call",
        "complete": True,
        "structural_path": ["single", str(position)],
        "top_level_position": position,
        "text": f"_ <@ {procedure}()",
        "target": None,
        "procedure": procedure,
        "arguments": [],
    }
