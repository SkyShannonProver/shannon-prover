"""Feature-neutral technical bounds for internal presentation values."""


# This is a defensive in-memory/schema ceiling, not an agent delivery budget.
# Feature-specific delivery policies own the much smaller Markdown budget.
MAX_INTERNAL_PRESENTATION_BYTES = 16_384
