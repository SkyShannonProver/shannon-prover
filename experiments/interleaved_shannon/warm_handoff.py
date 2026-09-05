"""Compatibility entry for the ChaChaPoly reference protocol."""

import sys

from experiments.interleaved_shannon._compat import bind_reference_project

bind_reference_project()

from workflow.interleaved import warm_handoff as _implementation

sys.modules[__name__] = _implementation
