"""Bound only candidate PHL transitivity spellings before native parsing."""


def is_candidate_phl_transitivity(tactic: str) -> bool:
    value = str(tactic or "").strip()
    return bool(
        0 < len(value.encode("utf-8")) <= 16_384
        and value.endswith(".")
        and (
            value.startswith("transitivity ")
            or value.startswith("transitivity{")
        )
        and not any(token in value for token in ("\n", "\r", "(*", "*)", '"'))
    )
