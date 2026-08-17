"""Shared P3 diagnostic rendering over authoritative typed evidence."""

from .application import structured_application_diagnostic
from .argument_alignment import (
    application_arguments_misaligned,
    structured_application_argument_alignment_diagnostic,
)

__all__ = [
    "application_arguments_misaligned",
    "structured_application_diagnostic",
    "structured_application_argument_alignment_diagnostic",
]
