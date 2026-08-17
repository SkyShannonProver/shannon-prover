"""Bounded manager-session memory for compiler presentation lifetimes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeliveryLifetimeLedger:
    """Remember presentation identities, never compiler or proof-state facts."""

    max_entries: int = 512
    _presented: dict[str, None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_entries <= 0:
            raise ValueError("delivery lifetime ledger must be bounded")

    def snapshot(self) -> frozenset[str]:
        return frozenset(self._presented)

    def record(self, presentation_ids: tuple[str, ...]) -> None:
        for presentation_id in presentation_ids:
            if not presentation_id:
                raise ValueError("cannot record an empty presentation ID")
            self._presented.pop(presentation_id, None)
            self._presented[presentation_id] = None
        while len(self._presented) > self.max_entries:
            oldest = next(iter(self._presented))
            del self._presented[oldest]

    def projected_size(self, presentation_ids: tuple[str, ...]) -> int:
        if any(not presentation_id for presentation_id in presentation_ids):
            raise ValueError("cannot project an empty presentation ID")
        return min(
            self.max_entries,
            len(set(self._presented) | set(presentation_ids)),
        )

    @property
    def size(self) -> int:
        return len(self._presented)
