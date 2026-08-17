"""Single owner of the current proof/program coordinate."""

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import ProofCoordinate
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofIR


def analyze_coordinate(proof_ir: ProofIR) -> ProofCoordinate:
    sides = {}
    for side in ("single", "left", "right"):
        statements = tuple(sorted(
            (item for item in proof_ir.statements if item.side == side),
            key=lambda item: item.position,
        ))
        if not statements:
            continue
        # Straight-line assignments before the first program operation are
        # setup, not an operation frontier. Sampling remains an operation.
        forward = next(
            (item for item in statements if item.kind != "assign"),
            None,
        )
        if forward is None:
            continue
        sides[side] = (forward, statements[-1])
    if not sides or (proof_ir.goal.kind == "equiv" and set(sides) != {
        "left", "right"
    }):
        return ProofCoordinate(
            status="unknown",
            forward_frontier=None,
            tactic_active_boundary=None,
        )
    if set(sides) == {"left", "right"}:
        left_forward, left_active = sides["left"]
        right_forward, right_active = sides["right"]
        if (
            (left_forward.position, left_forward.kind)
            != (right_forward.position, right_forward.kind)
            or (left_active.position, left_active.kind)
            != (right_active.position, right_active.kind)
        ):
            return ProofCoordinate(
                status="unknown",
                forward_frontier=None,
                tactic_active_boundary=None,
            )
        forward, active = left_forward, left_active
        evidence = tuple(dict.fromkeys(
            left_forward.evidence_refs
            + right_forward.evidence_refs
            + left_active.evidence_refs
            + right_active.evidence_refs
        ))
    else:
        forward, active = next(iter(sides.values()))
        evidence = tuple(dict.fromkeys(
            forward.evidence_refs + active.evidence_refs
        ))
    return ProofCoordinate(
        status="known",
        forward_frontier=forward,
        tactic_active_boundary=active,
        evidence_refs=evidence,
    )
