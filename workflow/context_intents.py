"""Re-export shim: the intent protocol vocabulary lives in core.

``context_intents`` moved to ``core/context_intents.py`` so that core-side
view code (``session_workspace_view_manager``) can consume the intent
contract without a core -> workflow import (the repo's layering invariant:
workflow imports core, never the reverse — enforced by
``tests/test_layering_contract.py``). Workflow-side callers keep importing
``workflow.context_intents``; this module is that unchanged public path.
"""
from core.context_intents import *  # noqa: F401,F403
from core.context_intents import _BASE_INTENT_SPECS  # noqa: F401
