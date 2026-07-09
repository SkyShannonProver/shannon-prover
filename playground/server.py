"""Shannon Prover playground — FastAPI + WebSocket backend.

A thin shell that puts a human where the agent sits: each WS message carries one
JSON intent, which is forwarded to the SAME `ProofNodeManager.handle_agent_message`
call the agent uses; the reply carries the rendered followup (what the agent reads)
plus the structured workspace view (the 'audit view').

Run locally (from the repo root, in a normal terminal — NOT under an OS sandbox, so
EasyCrypt/why3 can start):

    eval "$(opam env --switch=easycrypt)"
    uv run --with fastapi --with "uvicorn[standard]" \
        uvicorn playground.server:app --host 127.0.0.1 --port 8000

then open http://127.0.0.1:8000
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from playground.node_boot import (
    bootstrap_node,
    dispose,
    drive,
    ensure_supported_surface_profile,
    render_instructions,
    render_followup,
    surface_turn_of,
    workspace_view_of,
)
from playground.targets import proof_declarations as _proof_declarations

DEFAULT_INCLUDE = os.environ.get("SHANNON_INCLUDE_DIR", "easycrypt-src/theories")
MAX_SESSIONS = int(os.environ.get("PLAYGROUND_MAX_SESSIONS", "4"))

app = FastAPI(title="Shannon Prover Playground")


@app.middleware("http")
async def _no_store(request, call_next):
    # Dev playground: never let the browser cache the UI, so an edit + refresh
    # always shows the latest (no more stale-JS confusion).
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# --- Results explorer: static bundle browser over agent_view_runs/ -----------
# Same shell as the playground, different surface: the playground is live
# (server-backed EC); the results browser is read-only over bundles on disk.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_FILE = "eval/examples/ChaChaPoly/chacha_poly.ec"
DEFAULT_TARGET_LEMMA = "step4_1"
TARGET_ROOT = os.environ.get("PLAYGROUND_TARGET_ROOT", "eval/examples")
PRIVATE_TARGET_DIRS = {
    part.strip()
    for part in os.environ.get("PLAYGROUND_PRIVATE_TARGET_DIRS", "CMAC").split(",")
    if part.strip()
}
BUNDLE_BROWSER = REPO_ROOT / "bundle_browser"
AGENT_VIEW_RUNS = REPO_ROOT / "agent_view_runs"
if AGENT_VIEW_RUNS.is_dir():
    app.mount("/agent_view_runs", StaticFiles(directory=str(AGENT_VIEW_RUNS)), name="runs")


@app.get("/results")
def results_redirect() -> RedirectResponse:
    return RedirectResponse("/results/")


@app.get("/results/")
def results_index() -> HTMLResponse:
    return HTMLResponse((BUNDLE_BROWSER / "index.html").read_text(encoding="utf-8"))


def _worktree_runs() -> dict[str, Path]:
    """tag -> agent_view_runs/ Path for every OTHER git worktree (not the primary
    served one) that has bundles. New runs land in whichever worktree the eval ran
    in; scanning them all means every bundle is browsable here without copying or
    committing it first. Re-discovered each call (cheap) so a freshly-added worktree
    appears live. Tag = worktree dir name (used in the /runs_ext/<tag>/ artifact URL).
    """
    import subprocess

    out: dict[str, Path] = {}
    try:
        res = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return out
    for line in res.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        wt = Path(line[len("worktree "):].strip())
        if wt.resolve() == REPO_ROOT.resolve():
            continue  # primary — already served at /agent_view_runs/
        avr = wt / "agent_view_runs"
        if avr.is_dir():
            out.setdefault(wt.name, avr)  # first wins on rare basename collision
    return out


@app.get("/runs_ext/{tag}/{path:path}")
def runs_ext(tag: str, path: str):
    """Serve a bundle artifact from a non-primary worktree's agent_view_runs/, with
    a path-traversal guard (the resolved file must stay inside that worktree's runs)."""
    base = _worktree_runs().get(tag)
    if base is None:
        return JSONResponse({"error": "unknown runs tag"}, status_code=404)
    full = (base / path).resolve()
    base_r = base.resolve()
    if base_r != full and base_r not in full.parents:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not full.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(full))


@app.get("/results/manifest.json")
def results_manifest() -> JSONResponse:
    # Built live so new runs appear without re-running build_manifest.py. Scans the
    # primary served worktree FIRST, then every other worktree (their bundles fetch
    # artifacts via /runs_ext/<tag>/). The local view keeps private/CMAC bundles (the
    # browser badges them with a lock); a hosted static deploy uses
    # `build_manifest.py --public` instead.
    from bundle_browser.build_manifest import build_multi

    roots: list = [("", str(REPO_ROOT))]
    for tag, avr in sorted(_worktree_runs().items()):
        roots.append((f"/runs_ext/{tag}/", str(avr.parent)))
    return JSONResponse(build_multi(roots, public_only=False))


_active = 0


# Site layout: / is the main page (intro + paper phases + MCP tool + install
# instructions) with two click-throughs — /playground (the live prover UI,
# formerly served at /) and /results/ (benchmark browser). Documents are served
# inline (not a redirect to a cacheable /static URL) so a fresh load always
# gets the latest UI.
@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "static" / "home.html").read_text(encoding="utf-8"))


@app.get("/start")
def start_page() -> RedirectResponse:
    # The get-started content merged into the main page (owner decision); keep
    # the old URL working.
    return RedirectResponse("/#install")


@app.get("/playground")
def playground_page() -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8"))


def _safe_target_root() -> Path:
    root = Path(TARGET_ROOT)
    if not root.is_absolute():
        root = REPO_ROOT / root
    root = root.resolve()
    repo = REPO_ROOT.resolve()
    if root != repo and repo not in root.parents:
        raise ValueError("PLAYGROUND_TARGET_ROOT must stay inside the repository")
    return root


@app.get("/api/targets")
def playground_targets() -> JSONResponse:
    try:
        root = _safe_target_root()
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    files: list[dict[str, object]] = []
    for path in sorted([*root.rglob("*.ec"), *root.rglob("*.eca")]):
        if any(part in PRIVATE_TARGET_DIRS for part in path.relative_to(root).parts):
            continue
        lemmas = _proof_declarations(path)
        if not lemmas:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        files.append(
            {
                "path": rel,
                "label": path.relative_to(root).as_posix(),
                "lemmas": lemmas,
            }
        )

    return JSONResponse(
        {
            "root": root.relative_to(REPO_ROOT).as_posix(),
            "default_file": DEFAULT_TARGET_FILE,
            "default_lemma": DEFAULT_TARGET_LEMMA,
            "files": files,
        }
    )


@app.get("/api/instructions")
def playground_instructions(
    file: str = DEFAULT_TARGET_FILE,
    lemma: str = DEFAULT_TARGET_LEMMA,
    profile: str = "l4_checked_action_surface",
    include_dir: str = DEFAULT_INCLUDE,
) -> JSONResponse:
    try:
        prompt = render_instructions(
            file=file,
            lemma=lemma,
            include_dir=include_dir,
            profile=profile,
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({
        "type": "instructions",
        "scope": "state_independent_agent_instructions",
        "prompt": prompt,
        "profile": profile,
        "file": file,
        "lemma": lemma,
    })


def _view_payload(
    node,
    turn_or_view,
    *,
    ok: bool = True,
    repair: str = "",
    base_view=None,
) -> dict:
    full_view = getattr(getattr(node, "manager", None), "latest_full_view", None)
    surface_turn = surface_turn_of(
        turn_or_view,
        node.profile,
        base_view=base_view,
        full_view=full_view,
    )
    followup_md = render_followup(
        node,
        turn_or_view,
        node.profile,
        base_view=base_view,
        full_view=full_view,
    )
    return {
        "type": "view",
        "ok": ok,
        "followup_md": followup_md,
        "surface_turn": surface_turn,
        "workspace_view": workspace_view_of(turn_or_view),
        "repair_prompt": repair,
    }


def _view_msg(node, turn_or_view, *, ok: bool = True, repair: str = "", base_view=None) -> str:
    return json.dumps(_view_payload(node, turn_or_view, ok=ok, repair=repair, base_view=base_view))


def _err(message: str) -> str:
    return json.dumps({"type": "error", "message": message})


def _initial_prompt_msg(node, last: dict[str, str]) -> str:
    return json.dumps({
        "type": "initial_prompt",
        "scope": "state_independent_agent_instructions",
        "prompt": getattr(node, "initial_prompt", ""),
        "profile": getattr(node, "initial_prompt_profile", getattr(node, "profile", "")),
        "file": last.get("file", ""),
        "lemma": last.get("lemma", ""),
    })


@app.websocket("/play")
async def play(ws: WebSocket) -> None:
    global _active
    await ws.accept()
    node = None
    last: dict[str, str] = {}
    last_view = None  # the current proof state (bootstrap or last turn), re-rendered on profile switch

    async def start(file: str, lemma: str, profile: str, include_dir: str) -> None:
        nonlocal node, last_view
        global _active
        if node is not None:
            await asyncio.to_thread(dispose, node)
            node = None
            _active -= 1
        if _active >= MAX_SESSIONS:
            await ws.send_text(_err(f"server at capacity ({MAX_SESSIONS} sessions)"))
            return
        try:
            node = await asyncio.to_thread(
                bootstrap_node, file, lemma, profile, include_dir=include_dir
            )
            _active += 1
            last_view = node.bootstrap
            await ws.send_text(_view_msg(node, node.bootstrap, base_view=node.bootstrap))
        except Exception as exc:  # surface bootstrap failures to the UI
            await ws.send_text(_err(f"bootstrap failed: {exc}"))

    try:
        while True:
            msg = json.loads(await ws.receive_text())
            kind = msg.get("type")

            if kind == "start":
                last = {
                    "file": msg["file"],
                    "lemma": msg["lemma"],
                    "include_dir": msg.get("include_dir", DEFAULT_INCLUDE),
                }
                await start(
                    last["file"], last["lemma"],
                    msg.get("profile", "l4_checked_action_surface"), last["include_dir"],
                )

            elif kind == "switch_profile":
                # The surface profile is a RENDER of the current proof state, not a new
                # proof. Re-render the SAME state (last_view) at the new profile — do NOT
                # restart. L1<->L4 toggles freely; the EC session / committed tactics stay.
                if node is None or last_view is None:
                    await ws.send_text(_err("start a session first"))
                    continue
                profile = msg["profile"]
                try:
                    ensure_supported_surface_profile(profile)
                except Exception:
                    await ws.send_text(_err(f"unknown profile: {profile}"))
                    continue
                node.profile = profile
                # keep the manager in sync so subsequent intents build at this profile too
                try:
                    node.manager.surface_profile = profile
                    proj = getattr(node.manager, "projection", None)
                    if proj is not None and hasattr(proj, "surface_profile"):
                        proj.surface_profile = profile
                    esc = getattr(node.manager, "escalation", None)
                    if esc is not None and hasattr(esc, "effective_profile"):
                        esc.effective_profile = profile
                except Exception:
                    pass
                await ws.send_text(_view_msg(node, last_view, base_view=last_view))

            elif kind == "intent":
                if node is None:
                    await ws.send_text(_err("start a session first"))
                    continue
                intent = str(msg.get("intent") or "")
                payload = msg.get("payload", {})
                intent_json = json.dumps(
                    {"intent": intent, "payload": payload}
                )
                try:
                    turn = await asyncio.to_thread(drive, node, intent_json)
                    payload_msg = _view_payload(
                        node,
                        turn,
                        ok=turn.ok,
                        repair=turn.repair_prompt,
                        base_view=last_view,
                    )
                    if payload_msg.get("surface_turn", {}).get("base_surface_updates"):
                        last_view = turn
                    await ws.send_text(json.dumps(payload_msg))
                except Exception as exc:
                    # One bad intent must NOT kill the session: report it and keep the
                    # node + socket alive so the human can try another step (or restart).
                    # Previously this propagated to the outer handler, which disposed the
                    # node and closed the socket -> the UI then showed "no live session".
                    await ws.send_text(_err(f"intent failed (session kept alive): {exc}"))

            elif kind == "initial_prompt":
                if node is None:
                    await ws.send_text(_err("start a session first"))
                    continue
                await ws.send_text(_initial_prompt_msg(node, last))

            else:
                await ws.send_text(_err(f"unknown message type: {kind!r}"))

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        try:
            await ws.send_text(_err(str(exc)))
        except Exception:
            pass
    finally:
        if node is not None:
            await asyncio.to_thread(dispose, node)
            _active -= 1
