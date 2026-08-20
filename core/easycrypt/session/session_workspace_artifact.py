"""Event-bound storage contract for one ProverWorkspaceView occurrence.

The artifact carrier is neutral manager/session infrastructure.  It does not
know whether its payload came from the minimal L1/v2 envelope or a historical
diagnostic projector.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.easycrypt.session.session_artifact_io import (
    BoundJsonArtifactRead,
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session.session_events import record_authoritative_artifact_event
from core.easycrypt.session.session_prover_workspace_schema import (
    prover_workspace_event_payload_fields,
    require_prover_workspace_view,
    validate_prover_workspace_event_binding,
)


def write_prover_workspace_view_artifact(
    session_dir: str | Path,
    view: dict[str, Any],
) -> dict[str, Any]:
    path = Path(session_dir)
    data = dict(view)
    require_prover_workspace_view(data, label="workspace artifact")
    text = json.dumps(data, indent=2)
    canonical = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        path,
        subdir="prover_workspace_views",
        filename=f"prover_workspace_view_{digest[:16]}.json",
        text=text + "\n",
    )
    return prover_workspace_event_payload_fields(
        data,
        artifact=str(artifact),
        view_hash=digest,
    )


def record_prover_workspace_view(
    session_or_dir: Any,
    view: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    return record_authoritative_artifact_event(
        session_or_dir,
        "prover.workspace_view.produced",
        lambda: write_prover_workspace_view_artifact(session_dir, view),
        source=source,
    )


def read_bound_prover_workspace_event(
    session_dir: str | Path,
    event: dict[str, Any],
) -> BoundJsonArtifactRead:
    def _validate(
        data: dict[str, Any],
        payload: dict[str, Any],
        artifact_hash: str,
    ) -> tuple[list[str], list[str]]:
        validation = validate_prover_workspace_event_binding(
            data,
            payload,
            artifact_hash=artifact_hash,
        )
        return list(validation.errors), list(validation.warnings)

    return read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type="prover.workspace_view.produced",
        subdir="prover_workspace_views",
        validate_binding=_validate,
    )
