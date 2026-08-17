"""P2 output: shared structured proof-domain IR.

Feature packages contribute ordinary ``ProofResource`` values.  This module
must not grow one field or dataclass per experiment feature.

Python dataclass structure is not EasyCrypt semantic typing. Until a value is
derived from the planned native semantic adapter, parsed application slots and
judgments are lexical candidate sketches and require exact native preflight
before they can support an agent-visible action.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts.failure import (
    AttemptedOperationIR,
)
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NativeSemanticObservation,
    NativeSemanticPlanningReport,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
)


@dataclass(frozen=True)
class TypedTermIR:
    """Feature-neutral typed EasyCrypt term lowered from native AST."""

    kind: str
    text: str
    type_text: str
    children: tuple["TypedTermIR", ...]
    child_roles: tuple[str, ...]
    properties: FrozenJsonObject

    def __post_init__(self) -> None:
        if not self.kind or not self.text:
            raise ValueError("typed term requires kind and exact text")
        if self.child_roles and len(self.child_roles) != len(self.children):
            raise ValueError("typed term child roles disagree with children")


@dataclass(frozen=True)
class FormulaRelation:
    """One exact top-level binary relation in a parsed proposition."""

    operator: str
    left: str
    right: str

    def __post_init__(self) -> None:
        if self.operator not in {"=", "<=", ">=", "<", ">", "<=>"}:
            raise ValueError(f"unsupported formula relation {self.operator!r}")
        if not self.left or not self.right:
            raise ValueError("formula relation requires both operands")


@dataclass(frozen=True)
class GoalIR:
    status: str
    kind: str
    formula: str = ""
    bound_relation: str = ""
    bound_value: str = ""
    precondition: str = ""
    postcondition: str = ""
    relation: FormulaRelation | None = None
    formula_ir: TypedTermIR | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"known", "unknown"}:
            raise ValueError(f"unsupported goal IR status {self.status!r}")
        if self.status == "unknown" and self.kind != "unknown":
            raise ValueError("unknown goal IR must use kind='unknown'")
        if self.status == "known" and not self.evidence_refs:
            raise ValueError("known goal IR requires evidence")
        if self.status == "known" and self.formula_ir is None:
            raise ValueError("known goal IR requires native typed formula")
        if self.formula and not self.evidence_refs:
            raise ValueError("exact goal formula requires evidence")


@dataclass(frozen=True)
class ProgramStatement:
    side: str
    position: int
    kind: str
    text: str
    procedure: str = ""
    structural_path: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if self.side not in {"single", "left", "right"}:
            raise ValueError(f"unsupported program side {self.side!r}")
        if self.position <= 0 or not self.text:
            raise ValueError("program statement requires positive position and text")
        if self.kind not in {"call", "if", "while", "sample", "assign", "other"}:
            raise ValueError(f"unsupported statement kind {self.kind!r}")
        if self.kind == "call" and not self.procedure:
            raise ValueError("call statement requires procedure identity")
        if not self.structural_path:
            raise ValueError("program statement requires native structural path")
        if not self.evidence_refs:
            raise ValueError("program statement requires evidence")


@dataclass(frozen=True)
class ProofJudgment:
    """One normalized proposition attached to a loaded proof resource.

    ``kind`` is proof-domain vocabulary such as ``lossless``, ``hoare``,
    ``equiv``, or ``probability``. ``procedure`` is populated only when the
    proposition is specifically about a procedure.
    """

    kind: str
    text: str
    subject: str = ""
    procedure: str = ""
    relation: FormulaRelation | None = None
    formula_ir: TypedTermIR | None = None

    def __post_init__(self) -> None:
        if not self.kind or not self.text:
            raise ValueError("proof judgment requires kind and text")
        if self.kind == "lossless" and not self.procedure:
            raise ValueError("lossless judgment requires procedure identity")


@dataclass(frozen=True)
class ProofFact:
    """One named proof fact parsed without a liveness claim."""

    fact_id: str
    name: str
    judgment: ProofJudgment
    origin: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.fact_id or not self.name:
            raise ValueError("proof fact requires identity and name")
        if self.origin not in {"current_context", "source_declaration"}:
            raise ValueError(f"unsupported proof fact origin {self.origin!r}")
        if not self.evidence_refs:
            raise ValueError("proof fact requires evidence")


_ARGUMENT_SLOT_KINDS = {
    "module",
    "term",
    "formula",
    "type",
    "memory",
    "proof",
    "implicit",
}
_ARGUMENT_BINDING_MODES = {"required", "deferred_obligation"}


@dataclass(frozen=True)
class ArgumentSlot:
    """One ordered structural input slot for a loaded proof resource.

    ``binding_mode`` separates mechanically required application inputs from
    proof obligations that may soundly remain as ``_`` and become residual
    EasyCrypt goals. This is application vocabulary, not tactic rendering.
    """

    slot_id: str
    name: str
    kind: str
    binding_mode: str
    expected: str
    explicit: bool
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.slot_id or not self.name or not self.expected:
            raise ValueError("argument slot requires identity, name, and expectation")
        if self.kind not in _ARGUMENT_SLOT_KINDS:
            raise ValueError(f"unsupported argument slot kind {self.kind!r}")
        if self.binding_mode not in _ARGUMENT_BINDING_MODES:
            raise ValueError(
                f"unsupported argument binding mode {self.binding_mode!r}"
            )
        if self.binding_mode == "deferred_obligation" and self.kind != "proof":
            raise ValueError("only proof slots may be deferred obligations")
        if not self.evidence_refs:
            raise ValueError("argument slot requires evidence")


@dataclass(frozen=True)
class ApplicationSignature:
    """Ordered application-interface sketch for one loaded resource.

    The current frontend may build this from printed declaration text. That is
    candidate-planning evidence, not native proof-term elaboration.
    """

    resource_id: str
    slots: tuple[ArgumentSlot, ...]
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("application signature requires resource identity")
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("application signature has duplicate slot IDs")
        if not self.evidence_refs:
            raise ValueError("application signature requires evidence")


@dataclass(frozen=True)
class ProofResource:
    """One loaded declaration represented in shared proof-domain terms."""

    resource_id: str
    symbol: str
    resource_kind: str
    declaration: str
    application_signature: ApplicationSignature
    premises: tuple[ProofJudgment, ...]
    conclusion: ProofJudgment
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.resource_id or not self.symbol or not self.resource_kind:
            raise ValueError("proof resource requires identity, symbol, and kind")
        if not self.declaration:
            raise ValueError("proof resource requires its loaded declaration")
        if not self.evidence_refs:
            raise ValueError("proof resource requires evidence")
        if self.application_signature.resource_id != self.resource_id:
            raise ValueError("proof resource and application signature identities differ")


@dataclass(frozen=True)
class ModuleSpellingInventory:
    """Bounded lexical spellings; EasyCrypt still owns all module semantics."""

    terms: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    complete: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if self.terms != tuple(sorted(set(self.terms))):
            raise ValueError("module spelling inventory is not canonical")
        if self.complete == bool(self.reason):
            raise ValueError("module spelling inventory completeness is invalid")
        if self.complete and not self.evidence_refs:
            raise ValueError("complete module spelling inventory lacks evidence")
        if not self.complete and self.terms:
            raise ValueError("incomplete module spelling inventory was truncated")


@dataclass(frozen=True)
class ProofIR:
    """Shared structure only: no liveness claim and no proposed tactic."""

    state_ref: StateRef
    provenance: ProvenanceRef
    goal: GoalIR
    statements: tuple[ProgramStatement, ...] = ()
    facts: tuple[ProofFact, ...] = ()
    resources: tuple[ProofResource, ...] = ()
    module_spelling_inventory: ModuleSpellingInventory | None = None
    attempted_operation: AttemptedOperationIR | None = None
    native_semantic_observations: tuple[NativeSemanticObservation, ...] = ()
    native_semantic_planning_report: NativeSemanticPlanningReport | None = None

    def __post_init__(self) -> None:
        if (
            self.attempted_operation is not None
            and self.attempted_operation.state_ref != self.state_ref
        ):
            raise ValueError("attempted operation belongs to another StateRef")
        if any(
            item.state_ref != self.state_ref
            for item in self.native_semantic_observations
        ):
            raise ValueError("native semantic observation belongs to another StateRef")
        if (
            self.native_semantic_planning_report is not None
            and self.native_semantic_planning_report.state_ref != self.state_ref
        ):
            raise ValueError("native semantic planning report belongs to another StateRef")
