"""Analyzer pipeline facade.

This package provides the stable proof-evidence pipeline boundary: analyzers
consume ProofNodeState and CheckpointIndex-shaped inputs, then produce
EvidenceBundle data for the renderer.  They do not execute tactics or mutate
sessions.
"""

from .call_site import CallSiteAnalysis, CallSiteAnalyzer
from .frame_obligation import FrameObligationAnalyzer
from .pipeline import AnalyzerPipeline
from .pure_tail import PureTailAnalyzer
from .recovery import RecoveryDiagnosisAnalyzer
from .route_health import RouteHealthAnalysis, RouteHealthAnalyzer
from .seq_cut import SeqCutAnalyzer

__all__ = [
    "AnalyzerPipeline",
    "CallSiteAnalysis",
    "CallSiteAnalyzer",
    "FrameObligationAnalyzer",
    "PureTailAnalyzer",
    "RecoveryDiagnosisAnalyzer",
    "RouteHealthAnalysis",
    "RouteHealthAnalyzer",
    "SeqCutAnalyzer",
]
