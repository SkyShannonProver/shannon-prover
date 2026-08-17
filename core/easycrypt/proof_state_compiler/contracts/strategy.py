"""Strategy-coupling contracts for compiler outputs.

The classification is about what an output is allowed to decide, not whether
the underlying fact is true.  A true theorem can still be route-selecting when
the compiler foregrounds it before the agent has chosen that theorem.
"""

from __future__ import annotations

from dataclasses import dataclass


INTRINSIC = "intrinsic"
COMMITMENT_RELATIVE = "commitment_relative"
ROUTE_SELECTING = "route_selecting"
STRATEGY_CLASSES = frozenset({
    INTRINSIC,
    COMMITMENT_RELATIVE,
    ROUTE_SELECTING,
})


@dataclass(frozen=True)
class StrategyContract:
    """Declare whether one candidate introduces an uncommitted proof choice.

    ``intrinsic`` facts follow from the authoritative state without relying on
    an agent-selected route.  ``commitment_relative`` facts are mechanical only
    relative to a named prior commitment, such as an accepted invariant or an
    explicitly selected theorem.  ``route_selecting`` outputs foreground or
    choose a theorem, invariant, midpoint, witness, transform, or other route
    that the agent has not yet committed.
    """

    strategy_class: str
    rationale: str
    required_commitment: str = ""
    introduced_choice: str = ""

    def __post_init__(self) -> None:
        if self.strategy_class not in STRATEGY_CLASSES:
            raise ValueError(
                f"unsupported strategy class {self.strategy_class!r}"
            )
        if not self.rationale:
            raise ValueError("strategy contract requires a rationale")
        if self.strategy_class == INTRINSIC:
            if self.required_commitment or self.introduced_choice:
                raise ValueError(
                    "intrinsic output cannot require or introduce a proof choice"
                )
        elif self.strategy_class == COMMITMENT_RELATIVE:
            if not self.required_commitment:
                raise ValueError(
                    "commitment-relative output requires a commitment anchor"
                )
            if self.introduced_choice:
                raise ValueError(
                    "commitment-relative output cannot introduce a new choice"
                )
        else:
            if not self.introduced_choice:
                raise ValueError(
                    "route-selecting output must name the introduced choice"
                )
            if self.required_commitment:
                raise ValueError(
                    "route-selecting output cannot claim a prior commitment"
                )

    @property
    def strategy_entangled(self) -> bool:
        return self.strategy_class == ROUTE_SELECTING
