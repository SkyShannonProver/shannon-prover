"""Bind the historical ChaChaPoly command paths to the product runtime."""

from __future__ import annotations

import os

from workflow.interleaved.project import PROJECT_ENV
from workflow.interleaved.runtime import ANSWER_SOURCE_ENV


def bind_reference_project() -> None:
    os.environ.setdefault(
        PROJECT_ENV, "experiments/interleaved_shannon/project.json"
    )
    os.environ.setdefault(
        ANSWER_SOURCE_ENV,
        "easycrypt-src/examples/ChaChaPoly/chacha_poly.ec",
    )
