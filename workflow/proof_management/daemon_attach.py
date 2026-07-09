"""Worker-death survival: attach a respawned proof node to a still-live
EC daemon session instead of replaying the committed tactic prefix.

Problem (observed repeatedly 2026-06-11, lemma equiv_step4): when a
prover worker process dies (agent context exhaustion -> whole-worker
crash), the Layer-3 respawn boots a NEW session dir and replays the
entire committed prefix one tactic at a time, with every smt call
re-verified by EasyCrypt — ~30 minutes at 167 tactics, several times per
90-minute window. But the EC process itself never died: it lives in the
detached per-run ``ec_daemon`` (see ``core/easycrypt/daemon_backend.py``),
keyed by the DEAD node's session dir, holding the full proof state in
memory.

This module is the client half of the fix:

1. Verify the donor (dead node's) session dir matches the requested
   replay prefix and target (file, lemma), and that the daemon still
   holds a live session for it.
2. Copy the donor session dir to the new node's session dir (disk state
   — ``history.ec``, ``current.out``, projections — is the source of
   truth for views and capsules and must travel with the proof).
3. ``adopt_session`` in the daemon: rename the live EC session to the
   new node's derived session id, and rewrite ``daemon_state.json`` so
   the first post-attach commit syncs as a no-op.
4. Probe the adopted session (``get_goal``) to confirm the EC process
   actually responds.

Every step is verified; ANY failure returns a structured non-ok result
and the caller falls back to the legacy restart+replay path. The whole
feature is gated behind ``SHANNON_EC_DAEMON=1`` — with the flag off no
code path here is ever entered, preserving byte-identical legacy
behavior (hard requirement: the pipeline is mid-measurement-campaign).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket as _socket
from pathlib import Path
from typing import Any

# Single source of truth for the daemon session id lives in core; re-export the
# name this module's callers use so the formula is no longer hand-mirrored here
# (audit §2.5 / backlog #15).
from core.easycrypt.daemon_backend import (
    session_id_for_dir as daemon_session_id_for_dir,
)

__all__ = [
    "daemon_session_attach_enabled",
    "attempt_daemon_attach",
    "close_daemon_session",
    "release_daemon_session",
    "daemon_session_id_for_dir",
]


def daemon_session_attach_enabled() -> bool:
    """Master gate for daemon-backed session continuity (attach-not-replay).

    Distinct from ``EC_DAEMON_DISABLE`` (which kills the daemon
    *accelerator* inside session_cli): this flag enables the NEW
    attach/adopt lifecycle. Default OFF."""
    value = os.environ.get("SHANNON_EC_DAEMON", "").strip().lower()
    return value in ("1", "true", "yes", "on")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_history_tactics(session_dir: Path) -> list[str]:
    try:
        lines = (Path(session_dir) / "history.ec").read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip()]


def _socket_listening(socket_path: str) -> bool:
    if not socket_path or not os.path.exists(socket_path):
        return False
    try:
        probe = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        probe.settimeout(2.0)
        try:
            return probe.connect_ex(socket_path) == 0
        finally:
            probe.close()
    except Exception:
        return False


def _daemon_client(socket_path: str):
    """Late-bound ``ECDaemonClient`` import (core/easycrypt is not a
    package root for these modules; mirror daemon_backend's sys.path
    convention)."""
    import sys

    ec_dir = str(Path(__file__).resolve().parents[2] / "core" / "easycrypt")
    if ec_dir not in sys.path:
        sys.path.insert(0, ec_dir)
    from ec_daemon_client import ECDaemonClient  # type: ignore

    return ECDaemonClient(socket_path)


def _goal_hash_from_session_dir(session_dir: Path) -> str:
    """Projection-derived goal hash for a session dir.

    Mirrors ``workflow.proof_node_resume._goal_hash_from_session`` (the
    function that minted the capsule's ``current_goal_hash``) so the
    attach-time comparison is apples-to-apples."""
    try:
        from core.easycrypt.session_projection import read_proof_state_projection

        projection = read_proof_state_projection(Path(session_dir))
        value = projection.goal.active_goal_hash
        if value:
            return str(value)
    except Exception:
        pass
    try:
        current_out = (Path(session_dir) / "current.out").read_text(
            encoding="utf-8"
        )
    except OSError:
        return ""
    if not current_out:
        return ""
    return hashlib.sha256(current_out.encode("utf-8")).hexdigest()


def _fail(reason: str, **extra: Any) -> dict[str, Any]:
    result = {"ok": False, "reason": reason}
    result.update(extra)
    return result


def attempt_daemon_attach(
    *,
    project_root: Path,
    donor_session_dir: str | Path,
    target_session_dir: str | Path,
    file_path: str,
    lemma_name: str,
    replay_prefix: list[str],
    expected_goal_hash: str = "",
) -> dict[str, Any]:
    """Try to adopt the donor's live daemon EC session for the target dir.

    Returns ``{"ok": True, "replay_avoided": N, ...}`` on success — the
    target session dir is then a fully coherent continuation of the
    donor (disk state copied, daemon session renamed, daemon_state.json
    rewritten) and NO prefix replay is needed. On any verification or
    I/O failure returns ``{"ok": False, "reason": ...}`` and guarantees
    the daemon is left in a state the legacy fallback path can handle
    (a half-adopted session is closed so the fallback's ``-start``
    invalidation has nothing stale to trip over).

    Never raises.
    """
    try:
        return _attempt_daemon_attach_inner(
            project_root=Path(project_root),
            donor_session_dir=donor_session_dir,
            target_session_dir=target_session_dir,
            file_path=file_path,
            lemma_name=lemma_name,
            replay_prefix=list(replay_prefix or []),
            expected_goal_hash=str(expected_goal_hash or ""),
        )
    except Exception as exc:  # absolute backstop: attach is opportunistic
        return _fail("unexpected_error", error=f"{type(exc).__name__}: {exc}"[:600])


def _resolve_dir(session_dir: str | Path, project_root: Path) -> Path:
    path = Path(session_dir)
    return path if path.is_absolute() else project_root / path


def _attempt_daemon_attach_inner(
    *,
    project_root: Path,
    donor_session_dir: str | Path,
    target_session_dir: str | Path,
    file_path: str,
    lemma_name: str,
    replay_prefix: list[str],
    expected_goal_hash: str,
) -> dict[str, Any]:
    if not daemon_session_attach_enabled():
        return _fail("disabled")
    donor = _resolve_dir(donor_session_dir, project_root)
    target = _resolve_dir(target_session_dir, project_root)
    if donor.resolve() == target.resolve():
        return _fail("donor_is_target", donor=str(donor))
    if not donor.is_dir():
        return _fail("donor_dir_missing", donor=str(donor))

    requested = [str(t).strip() for t in replay_prefix if str(t).strip()]
    if not requested:
        # Zero-prefix bootstraps gain nothing from attach; a fresh start
        # is already cheap, and the verification below would be vacuous.
        return _fail("empty_replay_prefix", donor=str(donor))
    donor_history = _read_history_tactics(donor)
    if donor_history != requested:
        return _fail(
            "history_mismatch",
            donor=str(donor),
            donor_history_count=len(donor_history),
            requested_count=len(requested),
        )

    meta = _read_json(donor / "session_meta.json")
    meta_file = str(meta.get("file") or "")
    meta_lemma = str(meta.get("lemma") or "")
    try:
        same_file = bool(meta_file) and (
            Path(meta_file).resolve() == Path(file_path).resolve()
        )
    except OSError:
        same_file = False
    if not same_file or meta_lemma != str(lemma_name):
        return _fail(
            "session_meta_mismatch",
            donor=str(donor),
            meta_file=meta_file,
            meta_lemma=meta_lemma,
        )

    state = _read_json(donor / "daemon_state.json")
    state_count = int(state.get("committed_count") or 0)
    socket_path = str(state.get("socket_path") or "")
    state_lemma = str(state.get("lemma_name") or "")
    if state_count != len(requested) or state_lemma != str(lemma_name):
        # The daemon was not in sync with history.ec when the worker died
        # (e.g. the last commits fell back to the subprocess path, or an
        # undo invalidated the daemon session). The live EC state would
        # NOT match the prefix — replay is the only correct restore.
        return _fail(
            "daemon_state_out_of_sync",
            donor=str(donor),
            daemon_state_count=state_count,
            requested_count=len(requested),
        )
    if not _socket_listening(socket_path):
        return _fail("daemon_socket_dead", socket_path=socket_path)

    donor_sid = str(state.get("session_id") or daemon_session_id_for_dir(donor))
    target_sid = daemon_session_id_for_dir(target)
    client = _daemon_client(socket_path)
    try:
        live_sessions = client.list_sessions()
    except Exception as exc:
        return _fail("daemon_unreachable", error=str(exc)[:400])
    if donor_sid not in (live_sessions or []):
        return _fail("daemon_session_gone", donor_session_id=donor_sid)
    try:
        info = client.session_info(donor_sid)
    except Exception:
        info = {}
    if isinstance(info, dict) and info.get("exists"):
        if not info.get("ec_alive", True):
            return _fail("daemon_ec_dead", donor_session_id=donor_sid)
        daemon_count = info.get("committed_count")
        if isinstance(daemon_count, int) and daemon_count != len(requested):
            return _fail(
                "daemon_commit_count_mismatch",
                daemon_committed_count=daemon_count,
                requested_count=len(requested),
            )

    if expected_goal_hash:
        donor_goal_hash = _goal_hash_from_session_dir(donor)
        if donor_goal_hash and donor_goal_hash != expected_goal_hash:
            return _fail(
                "goal_hash_mismatch",
                expected=expected_goal_hash[:16],
                observed=donor_goal_hash[:16],
            )

    # --- Mutating phase -------------------------------------------------
    # Copy donor dir -> target dir (disk truth travels with the proof).
    try:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(donor, target)
    except OSError as exc:
        shutil.rmtree(target, ignore_errors=True)
        return _fail("copy_failed", error=str(exc)[:400])

    # Rename the live daemon session to the target's derived id.
    try:
        client.adopt_session(donor_sid, target_sid)
    except Exception as exc:
        shutil.rmtree(target, ignore_errors=True)
        return _fail("adopt_failed", error=str(exc)[:400])

    # Rewrite daemon_state.json so the first post-attach commit's
    # _sync_to() is a no-op (cached_count == history length, same id).
    try:
        new_state = dict(state)
        new_state["session_id"] = target_sid
        (target / "daemon_state.json").write_text(
            json.dumps(new_state, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        _best_effort_close(client, target_sid)
        shutil.rmtree(target, ignore_errors=True)
        return _fail("state_rewrite_failed", error=str(exc)[:400])

    # Liveness probe: the adopted EC process must actually answer.
    try:
        goal = client.get_goal(target_sid)
        raw = goal.get("raw") if isinstance(goal, dict) else None
    except Exception as exc:
        _best_effort_close(client, target_sid)
        shutil.rmtree(target, ignore_errors=True)
        return _fail("liveness_probe_failed", error=str(exc)[:400])
    if not raw:
        _best_effort_close(client, target_sid)
        shutil.rmtree(target, ignore_errors=True)
        return _fail("liveness_probe_empty")

    return {
        "ok": True,
        "replay_avoided": len(requested),
        "donor": str(donor),
        "target": str(target),
        "donor_session_id": donor_sid,
        "session_id": target_sid,
        "socket_path": socket_path,
    }


def _best_effort_close(client: Any, session_id: str) -> None:
    try:
        client.close_session(session_id)
    except Exception:
        pass


def close_daemon_session(
    session_dir: str | Path,
    project_root: Path,
) -> bool:
    """Best-effort close of the daemon session backing ``session_dir``.

    This is the lifecycle primitive used by replay/audit tools and other
    manager-owned cleanup paths. It is intentionally not gated by
    ``SHANNON_EC_DAEMON``: daemon fast-path sessions can exist even when the
    worker-death attach feature is disabled. Returns True iff a close RPC
    succeeded."""
    try:
        session_path = _resolve_dir(session_dir, Path(project_root))
        state = _read_json(session_path / "daemon_state.json")
        socket_path = str(state.get("socket_path") or "")
        if not _socket_listening(socket_path):
            return False
        sid = str(state.get("session_id") or daemon_session_id_for_dir(session_path))
        client = _daemon_client(socket_path)
        client.close_session(sid)
        try:
            (session_path / "daemon_state.json").unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return True
    except Exception:
        return False


def release_daemon_session(
    session_dir: str | Path,
    project_root: Path,
) -> bool:
    """Explicitly release a cleanly finished worker's daemon session.

    Called on CLEAN node termination (proved / give-up): a clean exit is
    final — Layer-3 only resurrects crashes — so the live EC session has
    no future attacher and should be released instead of waiting for the
    idle TTL reaper. Gated by the same SHANNON_EC_DAEMON flag as attach so
    the flag-off worker pipeline is untouched."""
    if not daemon_session_attach_enabled():
        return False
    return close_daemon_session(session_dir, project_root)
