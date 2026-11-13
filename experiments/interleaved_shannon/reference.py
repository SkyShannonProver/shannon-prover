"""The ChaChaPoly reference project binding used by this adapter's entry points."""

from __future__ import annotations

import os

from workflow.interleaved.project import PROJECT_ENV
from workflow.interleaved.runtime import ANSWER_SOURCE_ENV, ProjectContext


REFERENCE_PROJECT = "experiments/interleaved_shannon/project.json"
REFERENCE_ANSWER_SOURCE = "easycrypt-src/examples/ChaChaPoly/chacha_poly.ec"


def reference_context() -> ProjectContext:
    """Return the ChaChaPoly reference binding.

    A binding already in the environment wins, as it does for a child that
    the runner started with the reference project.
    """

    return ProjectContext.from_environment({
        PROJECT_ENV: REFERENCE_PROJECT,
        ANSWER_SOURCE_ENV: REFERENCE_ANSWER_SOURCE,
        **os.environ,
    })
