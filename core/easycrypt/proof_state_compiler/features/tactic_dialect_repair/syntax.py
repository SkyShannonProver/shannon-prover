"""Bounded work gate; EasyCrypt remains the tactic-grammar authority."""


def is_candidate_eager_while(tactic: str) -> bool:
    value = str(tactic or "").strip()
    return bool(
        0 < len(value.encode("utf-8")) <= 16_384
        and value.startswith("eager while")
        and value.endswith(".")
        and not any(token in value for token in ("\n", "\r", "(*", "*)", '"'))
    )
