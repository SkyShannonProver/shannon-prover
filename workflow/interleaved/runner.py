#!/usr/bin/env python3
"""Run one configured outer/inner Shannon product instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from workflow.interleaved.agent_config import (
    agent_profile_sha256,
    PROFILE_PATH,
    AgentProfile,
    load_agent_profiles,
    provider_identity_projection,
    provider_identity_sha256,
    resolve_agent_config,
)
from workflow.interleaved.jobs import (
    INNER_PROVIDER_ENV,
    INNER_PROVIDER_IDENTITY_ENV,
    MAX_PARALLEL,
    cancel_jobs_in_run,
    continuation_resume_options,
    private_job_records,
    public_job_summary,
)
from workflow.interleaved.inner_runner import (
    prepare_shannon_eval_source,
)
from workflow.interleaved.warm_handoff_sentinel import (
    run_warm_handoff_sentinel,
)
from workflow.interleaved.runtime import load_runtime_settings
from workflow.interleaved.prompt import render_default_prompt
from workflow.proof_tool.easycrypt_source_resource import (
    EasyCryptSourceResource,
    SOURCE_RESOURCE_MANIFEST_ENV,
)
from workflow.proof_tool.proof_tool_launch import (
    ProviderCapabilityError,
    discover_codex_capabilities,
    outer_codex_feature_disable_args,
)
from workflow.provider.provider_sessions import provider_cli_identity
from workflow.validation.claude_required_mcp_sentinel import (
    run_claude_required_mcp_sentinel,
)


_SETTINGS = load_runtime_settings()
ROOT = _SETTINGS.root
PROJECT = _SETTINGS.project
PRODUCT = ROOT / "workflow" / "interleaved"
PROJECT_ASSETS = (
    (ROOT / PROJECT.prompt_file).parent if PROJECT.prompt_file else PRODUCT
)
TARGET_REL = PROJECT.target_file
FINAL_LEMMA = PROJECT.final_lemma
ARTIFACT_ROOT = PROJECT.artifact_root
VERIFIER = PROJECT.verifier or "workflow/interleaved/verify.py"
ANSWER_SOURCE = _SETTINGS.answer_source or ROOT / ".interleaved-no-answer-source"
DEFAULT_TIMEOUT_SECONDS = PROJECT.outer_timeout_seconds
OUTER_CLAUDE_DISABLED_TOOLS = (
    "Agent(*)",
    "Task(*)",
    "WebSearch(*)",
    "WebFetch(*)",
)
OUTER_CLAUDE_REQUIRED_OPTIONS = (
    "--disable-slash-commands",
    "--disallowedTools",
    "--effort",
    "--max-budget-usd",
    "--model",
    "--no-chrome",
    "--no-session-persistence",
    "--output-format",
    "--permission-mode",
    "--print",
    "--safe-mode",
    "--strict-mcp-config",
    "--verbose",
)
INNER_CLAUDE_REQUIRED_OPTIONS = (
    "--append-system-prompt",
    "--dangerously-skip-permissions",
    "--disallowedTools",
    "--effort",
    "--mcp-config",
    "--model",
    "--output-format",
    "--print",
    "--strict-mcp-config",
    "--verbose",
)

def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def experiment_environment(
    providers: frozenset[str],
) -> tuple[dict[str, str], list[str]]:
    """Remove injected credentials for every provider used by this run."""

    environment = os.environ.copy()
    credential_keys: list[str] = []
    if "claude" in providers:
        credential_keys.append("ANTHROPIC_API_KEY")
    if "codex" in providers:
        credential_keys.extend(("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN"))
    removed = [key for key in credential_keys if environment.pop(key, None)]
    return environment, removed


def claude_auth_summary(claude: str, environment: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        [claude, "auth", "status", "--json"],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "checked": True,
        "exit_code": result.returncode,
        "logged_in": payload.get("loggedIn") is True,
        "auth_method": payload.get("authMethod"),
        "api_provider": payload.get("apiProvider"),
        "subscription_type": payload.get("subscriptionType"),
    }


def codex_auth_summary(codex: str, environment: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        [codex, "login", "status"],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    status = (result.stdout or result.stderr).strip()
    lowered = status.lower()
    auth_method = (
        "chatgpt"
        if "chatgpt" in lowered
        else "api_key"
        if "api key" in lowered or "api_key" in lowered
        else "access_token"
        if "access token" in lowered
        else "unknown"
    )
    return {
        "checked": True,
        "exit_code": result.returncode,
        "logged_in": result.returncode == 0,
        "auth_method": auth_method,
    }


def claude_capability_error(
    claude: str,
    environment: dict[str, str],
    *,
    require_outer: bool,
    require_inner: bool,
) -> str | None:
    """Return a preflight error when Claude lacks a role-critical option."""

    result = subprocess.run(
        [claude, "--help"],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    help_text = result.stdout + result.stderr
    if result.returncode != 0:
        return f"Claude capability probe failed with exit code {result.returncode}"
    required = set()
    if require_outer:
        required.update(OUTER_CLAUDE_REQUIRED_OPTIONS)
    if require_inner:
        required.update(INNER_CLAUDE_REQUIRED_OPTIONS)
    missing = [
        option for option in sorted(required)
        if option not in help_text
    ]
    if missing:
        return "installed Claude lacks required selected-role capabilities: " + ", ".join(
            missing
        )
    return None


def build_outer_command(
    profile: AgentProfile,
    executable: str,
    *,
    rendered_prompt: str,
    codex_features: set[str] | frozenset[str] = frozenset(),
) -> tuple[list[str], bool]:
    """Return one provider command and whether its prompt is written to stdin."""

    if profile.cli_provider == "claude-code":
        if (
            profile.outer_max_turns is None
            or profile.outer_max_budget_usd is None
        ):
            raise ValueError("Claude profile requires turn and budget limits")
        return [
            executable,
            "--verbose",
            "--output-format",
            "stream-json",
            "--max-turns",
            str(profile.outer_max_turns),
            "--effort",
            profile.effort,
            "--max-budget-usd",
            str(profile.outer_max_budget_usd),
            "--permission-mode",
            "bypassPermissions",
            "--disallowedTools",
            *OUTER_CLAUDE_DISABLED_TOOLS,
            "--model",
            profile.model,
            "--safe-mode",
            "--disable-slash-commands",
            "--no-chrome",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--print",
            "--",
            rendered_prompt,
        ], False
    if profile.cli_provider == "codex":
        return [
            executable,
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "--json",
            "--color",
            "never",
            "--cd",
            str(ROOT),
            "--sandbox",
            "danger-full-access",
            "--model",
            profile.model,
            "--strict-config",
            "--config",
            'approval_policy="never"',
            "--config",
            f'model_reasoning_effort={json.dumps(profile.effort)}',
            "--config",
            'web_search="disabled"',
            *outer_codex_feature_disable_args(codex_features),
            "-",
        ], True
    raise ValueError(
        f"unsupported outer provider profile: {profile.cli_provider}"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provider_runtime_identity(
    *,
    profile: AgentProfile,
    executable: str,
    version: str,
) -> dict[str, str]:
    resolved = Path(executable).resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"provider executable is not a file: {executable}")
    first_version_line = next(
        (line.strip() for line in version.splitlines() if line.strip()),
        "",
    )
    if not first_version_line:
        raise ValueError("provider executable returned an empty version")
    return {
        "agent_backend": profile.backend,
        "model": profile.model,
        "binary": executable,
        "resolved_path": str(resolved),
        "binary_sha256": sha256(resolved),
        "version": first_version_line,
    }


def source_bundle_preflight(*, run_dir: Path) -> dict[str, Any]:
    """Prepare and validate the exact platform-neutral Shannon input shape."""

    prepared = prepare_shannon_eval_source(
        target_path=ROOT / TARGET_REL,
        lemma=FINAL_LEMMA,
        output_root=run_dir / "source_preflight",
    )
    manifest_path = run_dir / "source_preflight" / "eval_source" / "source_manifest.json"
    manifest = prepared.manifest
    expected_files = set(PROJECT.expected_task_files) or {
        path.name for path in (ROOT / TARGET_REL).parent.iterdir()
        if path.suffix in {".ec", ".eca"}
    }
    actual_files = {
        str(item.get("path") or "")
        for item in manifest.get("stripped_files", [])
        if isinstance(item, dict)
    }
    if (
        manifest.get("kind") != "eval_source_prep"
        or manifest.get("source_contract") != "proof_stripped_project"
        or manifest.get("strip_proofs") is not True
        or manifest.get("target_lemma") != FINAL_LEMMA
        or actual_files != expected_files
        or not prepared.isolated_file.is_file()
        or ANSWER_SOURCE.exists()
    ):
        raise RuntimeError("platform-neutral Shannon source preflight failed")
    source_resource = EasyCryptSourceResource.from_environment(
        project_root=ROOT,
        source_file=prepared.isolated_file.relative_to(ROOT),
        target_lemma=FINAL_LEMMA,
        include_dir=PROJECT.include_dirs[0],
        environ={
            SOURCE_RESOURCE_MANIFEST_ENV: str(manifest_path.relative_to(ROOT)),
        },
    )
    if source_resource is None:
        raise RuntimeError("manager-owned source resource was not enabled")
    source_read = source_resource.read({
        "path": prepared.isolated_file.relative_to(ROOT).as_posix(),
        "start_line": 1,
        "end_line": 1,
    }, call_id="interleaved-source-preflight")
    if source_read.is_error:
        raise RuntimeError(
            f"manager-owned source resource preflight failed: {source_read.text}"
        )
    source_search = source_resource.search({
        "query": PROJECT.source_probe_symbol or FINAL_LEMMA,
        "scope": "task",
        "max_results": 5,
    }, call_id="interleaved-search-preflight")
    if (
        source_search.is_error
        or f"{Path(TARGET_REL).name}:" not in source_search.text
    ):
        raise RuntimeError(
            "manager-owned source search preflight failed: "
            f"{source_search.text}"
        )
    declaration = source_resource.resolve_declaration({
        "symbol": PROJECT.source_probe_symbol or FINAL_LEMMA,
    }, call_id="interleaved-resolve-preflight")
    if declaration.is_error or "EasyCrypt-native declaration resolved" not in (
        declaration.text
    ):
        raise RuntimeError(
            "EasyCrypt-native declaration preflight failed: "
            f"{declaration.text}"
        )
    return {
        "passed": True,
        "source_contract": "proof_stripped_project",
        "target_lemma": FINAL_LEMMA,
        "stripped_files": sorted(actual_files),
        "proofs_replaced_total": manifest.get("proofs_replaced_total"),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": sha256(manifest_path),
        "answer_source_visible": False,
        "source_navigation": {
            "passed": True,
            "tools": [
                "search_easycrypt_source",
                "read_easycrypt_source",
                "resolve_easycrypt_declaration",
            ],
            "native_resolution_symbol": PROJECT.source_probe_symbol or FINAL_LEMMA,
            "target_path": source_resource.target_path,
            "target_sha256": source_resource.target_sha256,
        },
        "warm_handoff_sentinel": run_warm_handoff_sentinel(run_dir=run_dir),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def preserve_partial_candidate(*, target: Path, run_dir: Path) -> dict[str, str]:
    """Save the current candidate when a run does not verify successfully."""

    snapshot = run_dir / "partial_candidate.ec"
    shutil.copy2(target, snapshot)
    return {
        "path": str(snapshot.relative_to(ROOT)),
        "sha256": sha256(snapshot),
    }


def fixed_inner_config_mismatches(
    jobs: list[dict[str, Any]],
    *,
    inner_profile: AgentProfile,
    expected_inner_profile_sha256: str,
    expected_identity_sha256: str,
) -> list[str]:
    """Return jobs that drift from the single runner-selected inner profile."""

    return [
        str(job.get("job_id") or "unknown")
        for job in jobs
        if job.get("inner_provider") != inner_profile.key
        or job.get("inner_model") != inner_profile.model
        or job.get("inner_effort") != inner_profile.effort
        or job.get("inner_profile_sha256") != expected_inner_profile_sha256
        or job.get("expected_provider_identity_sha256")
        != expected_identity_sha256
        or (
            job.get("actual_provider_identity_sha256")
            and job.get("actual_provider_identity_sha256")
            != job.get("expected_provider_identity_sha256")
        )
        or (
            job.get("status") in {"verified", "incomplete", "merged"}
            and (
                not job.get("invocation_receipt_sha256")
                or not job.get("actual_provider_identity_sha256")
                or not job.get("eval_source_manifest_sha256")
            )
        )
    ]


def is_premature_agent_stop(
    *,
    final_passed: bool,
    timed_out: bool,
    interrupted: bool,
    exit_code: int | None,
    elapsed_seconds: float,
    timeout_seconds: int,
) -> bool:
    return (
        not final_passed
        and not timed_out
        and not interrupted
        and exit_code == 0
        and elapsed_seconds + 60 < timeout_seconds
    )


def require_official_start() -> str:
    status = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if status.returncode != 0:
        raise SystemExit("could not inspect Git status: " + status.stderr.strip())
    if status.stdout:
        raise SystemExit("official runs require a clean worktree:\n" + status.stdout)
    if _SETTINGS.answer_source is not None:
        branch = run(["git", "symbolic-ref", "-q", "HEAD"])
        if branch.returncode == 0:
            raise SystemExit(
                "answer-confined reference runs require a detached worktree; "
                "use the adapter's workspace preparation command"
            )
        if ANSWER_SOURCE.exists():
            raise SystemExit(f"answer-bearing EasyCrypt source is visible: {ANSWER_SOURCE}")

        forbidden_roots = ("eval", "agent_view_runs", "docs", "tests")
        visible = [name for name in forbidden_roots if (ROOT / name).exists()]
        if visible:
            raise SystemExit(
                f"answer-bearing or unnecessary roots remain visible: {visible}"
            )

    commit = run(["git", "rev-parse", "HEAD"])
    if commit.returncode != 0:
        raise SystemExit("could not resolve HEAD: " + commit.stderr.strip())
    return commit.stdout.strip()


def resolve_continuation(
    raw: str | None,
) -> tuple[
    Path | None,
    dict[str, Any] | None,
    dict[str, str] | None,
]:
    if raw is None:
        return None, None, None
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise SystemExit("--continuation-of must be a safe repository-relative path")
    resolved = (ROOT / relative).resolve()
    allowed = (ROOT / ARTIFACT_ROOT).resolve()
    if not resolved.is_relative_to(allowed) or not resolved.is_dir():
        raise SystemExit("--continuation-of is not an existing interleaved run directory")
    manifest = resolved / "manifest.json"
    events = resolved / "outer_agent_events.jsonl"
    if not manifest.is_file() or not events.is_file():
        raise SystemExit("--continuation-of lacks the prior manifest or outer event stream")
    try:
        prior_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"--continuation-of manifest is unreadable: {exc}") from exc
    if not isinstance(prior_manifest, dict):
        raise SystemExit("--continuation-of manifest must be a JSON object")
    if prior_manifest.get("schema_version") != 4:
        raise SystemExit(
            "--continuation-of requires a current schema-v4 run manifest"
        )
    selection = prior_manifest.get("agent_selection")
    if not isinstance(selection, dict):
        raise SystemExit("--continuation-of manifest lacks agent_selection")
    providers = {
        "outer_provider": str(selection.get("outer_provider") or ""),
        "inner_provider": str(selection.get("inner_provider") or ""),
    }
    if any(not value for value in providers.values()):
        raise SystemExit("--continuation-of manifest lacks provider selection")
    unsupported = sorted(set(providers.values()) - {"claude", "codex"})
    if unsupported:
        raise SystemExit(
            "--continuation-of manifest has unsupported provider selection: "
            + ", ".join(unsupported)
        )
    prior_active_elapsed = float(
        prior_manifest.get(
            "cumulative_active_elapsed_seconds",
            prior_manifest.get("elapsed_seconds", 0),
        )
        or 0
    )
    return relative, {
        "run_directory": relative.as_posix(),
        "manifest_sha256": sha256(manifest),
        "outer_events_sha256": sha256(events),
        "inherited_agent_selection": providers,
        "prior_active_elapsed_seconds": prior_active_elapsed,
    }, providers


def resolve_continuation_candidate(
    raw: str | None,
    continuation_rel: Path | None,
) -> tuple[Path | None, dict[str, Any] | None]:
    if raw is None:
        return None, None
    if continuation_rel is None:
        raise SystemExit("--continuation-candidate requires --continuation-of")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise SystemExit("--continuation-candidate must be repository-relative")
    resolved = (ROOT / relative).resolve()
    prior = (ROOT / continuation_rel).resolve()
    if not resolved.is_relative_to(prior) or not resolved.is_file():
        raise SystemExit(
            "--continuation-candidate must be an existing file inside the "
            "disclosed continuation directory"
        )
    return relative, {
        "path": relative.as_posix(),
        "sha256": sha256(resolved),
    }


def select_agent_providers(
    *,
    defaults: dict[str, str],
    requested: dict[str, str | None],
    inherited: dict[str, str] | None,
    allow_change: bool,
) -> dict[str, str]:
    if allow_change and inherited is None:
        raise ValueError("--allow-provider-change requires --continuation-of")
    selected: dict[str, str] = {}
    for role in ("outer_provider", "inner_provider"):
        prior = inherited.get(role) if inherited is not None else None
        value = requested.get(role) or prior or defaults[role]
        if prior is not None and value != prior and not allow_change:
            raise ValueError(
                f"continuation {role} changed from {prior} to {value}; "
                "pass --allow-provider-change to make that confound explicit"
            )
        selected[role] = value
    return selected


def invoke_verifier(mode: str, output: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            str(ROOT / VERIFIER),
            f"--{mode}",
            "--output",
            output.relative_to(ROOT).as_posix(),
        ]
    )


def terminate_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    for sig, delay in ((signal.SIGINT, 10), (signal.SIGTERM, 10), (signal.SIGKILL, 0)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        if delay:
            try:
                process.wait(timeout=delay)
                return
            except subprocess.TimeoutExpired:
                pass


def main() -> int:
    profiles, defaults = load_agent_profiles()
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--outer-provider",
        choices=tuple(profiles),
        help=(
            "select the outer-agent profile; a continuation inherits its prior "
            "selection when omitted"
        ),
    )
    parser.add_argument(
        "--inner-provider",
        choices=tuple(profiles),
        help=(
            "select the Shannon proof-node profile; a continuation inherits its "
            "prior selection when omitted"
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "external runner watchdog/observation cutoff; this does not change "
            "the project contract's model-facing task budget"
        ),
    )
    parser.add_argument("--continuation-of")
    parser.add_argument("--continuation-candidate")
    parser.add_argument(
        "--allow-provider-change",
        action="store_true",
        help="explicitly permit a continuation to change its prior provider arm",
    )
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    commit = require_official_start()
    continuation_rel, continuation, inherited_providers = resolve_continuation(
        args.continuation_of
    )
    try:
        selected_providers = select_agent_providers(
            defaults=defaults,
            requested={
                "outer_provider": args.outer_provider,
                "inner_provider": args.inner_provider,
            },
            inherited=inherited_providers,
            allow_change=args.allow_provider_change,
        )
    except ValueError as exc:
        parser.error(str(exc))
    agent_config = resolve_agent_config(
        outer_provider=selected_providers["outer_provider"],
        inner_provider=selected_providers["inner_provider"],
    )
    outer_profile = agent_config.outer
    inner_profile = agent_config.inner
    continuation_candidate_rel, continuation_candidate = (
        resolve_continuation_candidate(
            args.continuation_candidate,
            continuation_rel,
        )
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.preflight_only:
        kind = "preflight"
    else:
        kind = "continuation" if continuation is not None else "official"
    run_rel = Path(ARTIFACT_ROOT) / f"{kind}_{stamp}"
    run_dir = ROOT / run_rel
    run_dir.mkdir(parents=True, exist_ok=False)

    preflight_path = run_dir / "preflight_verification.json"
    preflight = invoke_verifier("preflight", preflight_path)
    if preflight.returncode != 0:
        print(preflight.stdout, file=sys.stderr)
        print(preflight.stderr, file=sys.stderr)
        raise SystemExit("preflight verification failed")

    outer_environment, removed_credential_keys = experiment_environment(
        agent_config.required_provider_keys
    )
    provider_runtime: dict[str, dict[str, Any]] = {}
    for provider in sorted(agent_config.required_provider_keys):
        selected = profiles[provider]
        executable = shutil.which(selected.binary_name)
        runtime: dict[str, Any] = {
            "executable": executable,
            "version": "unavailable",
            "auth": {"checked": False},
            "codex_capabilities": None,
            "codex_features": frozenset(),
            "capability_error": "",
            "provider_identity": None,
        }
        if executable:
            version = subprocess.run(
                [executable, "--version"],
                cwd=ROOT,
                env=outer_environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            runtime["version"] = (version.stdout or version.stderr).strip()
            if version.returncode != 0:
                runtime["capability_error"] = (
                    f"{selected.binary_name} --version failed with exit "
                    f"{version.returncode}"
                )
            else:
                try:
                    runtime["provider_identity"] = provider_runtime_identity(
                        profile=selected,
                        executable=executable,
                        version=runtime["version"],
                    )
                except (OSError, ValueError) as exc:
                    runtime["capability_error"] = str(exc)
            if provider == "claude":
                runtime["auth"] = claude_auth_summary(
                    executable,
                    outer_environment,
                )
                claude_error = claude_capability_error(
                    executable,
                    outer_environment,
                    require_outer=provider == outer_profile.key,
                    require_inner=provider == inner_profile.key,
                )
                if claude_error:
                    runtime["capability_error"] = "; ".join(
                        item
                        for item in (
                            str(runtime["capability_error"] or ""),
                            claude_error,
                        )
                        if item
                    )
            else:
                runtime["auth"] = codex_auth_summary(
                    executable,
                    outer_environment,
                )
                try:
                    discovered = discover_codex_capabilities(
                        executable,
                        probe_resume=provider == inner_profile.key,
                    )
                    if provider == outer_profile.key:
                        discovered.require_outer_construction_agent()
                    if provider == inner_profile.key:
                        discovered.require_managed_proof_node()
                    runtime["codex_features"] = discovered.features
                    runtime["codex_capabilities"] = discovered.to_dict()
                except ProviderCapabilityError as exc:
                    runtime["capability_error"] = str(exc)
        provider_runtime[provider] = runtime

    outer_runtime = provider_runtime[outer_profile.key]

    shannon_source_preflight = source_bundle_preflight(run_dir=run_dir)

    prompt_template = (
        ROOT / PROJECT.prompt_file if PROJECT.prompt_file else PRODUCT / "prompt.py"
    )
    prompt_text = (
        prompt_template.read_text(encoding="utf-8")
        if PROJECT.prompt_file
        else render_default_prompt(PROJECT)
    )
    if continuation_rel is None:
        continuation_context = ""
    else:
        resume_options = continuation_resume_options(
            ROOT / continuation_rel,
            source_text=(ROOT / TARGET_REL).read_text(encoding="utf-8"),
        )
        if resume_options:
            rendered_options = "\n".join(
                "- `--lemma {lemma} --resume-job {job_id}`: {tactic_count} "
                "manager-accepted tactics, checkpoint `{checkpoint_id}`".format(
                    **item
                )
                for item in resume_options
            )
            resume_instruction = f"""
The scheduler validated these manager-owned checkpoints from the disclosed
prior run against the current lemma declarations and prefix environment:

{rendered_options}

For a matching still-promising lemma, submit that exact `--resume-job` before
starting a fresh handoff. The scheduler copies and revalidates the capsule in
this run and records the prior run directory in the invocation receipt.
"""
            assert continuation is not None
            continuation["resume_checkpoints"] = resume_options
        else:
            resume_instruction = ""
        candidate_instruction = ""
        if continuation_candidate_rel is not None:
            candidate_instruction = f"""
The disclosed partial-proof snapshot is
`{continuation_candidate_rel.as_posix()}`. Before writing another speculative
variant at its first stuck lemma, and when no validated managed checkpoint is
listed below, create the strategy note and invoke warm handoff with
`--candidate-source {continuation_candidate_rel.as_posix()}`.
This preserves the accepted prefix while giving the inner agent the exact
residual state. Do not cold-start that lemma unless handoff preparation fails;
if it fails, journal only the wrapper-reported reason, do not inspect raw
preparation or session artifacts, and then continue.
"""
        prior_outer = (
            inherited_providers["outer_provider"]
            if inherited_providers is not None
            else outer_profile.key
        )
        ownership_instruction = (
            "Treat it as your own checkpoint."
            if prior_outer == outer_profile.key
            else (
                f"It was produced by the prior `{prior_outer}` outer agent; "
                f"this run explicitly hands it to `{outer_profile.key}`, so "
                "preserve that cross-provider provenance as an experiment "
                "confound."
            )
        )
        continuation_context = f"""## Continuation checkpoint

This is a disclosed continuation of `{continuation_rel.as_posix()}`. The
scratchpad contains work produced by the immediately preceding outer-agent run,
not a human-supplied decomposition. {ownership_instruction} Preserve the proved
prefix and read the prior journal and user-facing summaries as needed; the
backend-private artifact restriction below still applies. Assess the first
admitted or locally stuck lemma and apply the accountable switch rule before
resuming large construction-mode edits.
{candidate_instruction}
{resume_instruction}
"""
    prior_active_elapsed = float(
        (continuation or {}).get("prior_active_elapsed_seconds") or 0
    )
    watchdog_deadline = (
        datetime.now(timezone.utc).astimezone()
        + timedelta(seconds=args.timeout_seconds)
    ).isoformat(timespec="seconds")
    rendered_prompt = (
        prompt_text
        .replace("{{RUN_DIR}}", run_rel.as_posix())
        .replace("{{CONTINUATION_CONTEXT}}", continuation_context)
    )
    if "{{" in rendered_prompt or "}}" in rendered_prompt:
        raise SystemExit(
            "rendered experiment prompt contains an unresolved placeholder"
        )
    rendered_path = run_dir / "prompt.rendered.md"
    rendered_path.write_text(rendered_prompt, encoding="utf-8")

    public_provider_runtimes = {
        provider: {
            "version": runtime["version"],
            "auth": runtime["auth"],
            "provider_identity": runtime["provider_identity"],
            "codex_capabilities": runtime["codex_capabilities"],
            "capability_error": runtime["capability_error"],
        }
        for provider, runtime in provider_runtime.items()
    }
    manifest: dict[str, Any] = {
        "schema_version": 4,
        "product": "interleaved_shannon",
        "project_contract": _SETTINGS.project_path.relative_to(ROOT).as_posix(),
        "project_identity_sha256": PROJECT.identity_sha256,
        "reference_answer_confinement": _SETTINGS.answer_source is not None,
        "experiment": "interleaved_phase2_phase3_shannon",
        "experiment_family": "interleaved_phase2_phase3_shannon",
        "arm_id": f"outer_{outer_profile.key}_inner_{inner_profile.key}",
        "commit": commit,
        "started_at": now(),
        "run_directory": run_rel.as_posix(),
        "run_kind": kind,
        "continuation": continuation,
        "continuation_candidate": continuation_candidate,
        "source_preflight_passed": True,
        "provider_preflight_passed": False,
        "preflight_passed": False,
        "model_process_launched": False,
        "shannon_source_preflight": shannon_source_preflight,
        "claude_required_mcp_preflight": {
            "required": inner_profile.backend == "claude",
            "passed": None if inner_profile.backend == "claude" else True,
        },
        "agent_selection": {
            "outer_provider": outer_profile.key,
            "inner_provider": inner_profile.key,
            "continuation_provider_change_allowed": args.allow_provider_change,
        },
        "profiles": {
            provider: profiles[provider].outer_dict()
            for provider in sorted(agent_config.required_provider_keys)
        },
        "provider_runtimes": public_provider_runtimes,
        "credential_policy": {
            "removed_injected_credential_keys": removed_credential_keys,
        },
        "outer_agent": {
            "profile": outer_profile.key,
            "limits": {
                "max_turns": outer_profile.outer_max_turns,
                "max_budget_usd": outer_profile.outer_max_budget_usd,
            },
            "timeout_seconds": args.timeout_seconds,
            "deadline_at": watchdog_deadline,
            "timing_contract": "project_model_budget_external_watchdog",
            "model_visible_task_budget_seconds": DEFAULT_TIMEOUT_SECONDS,
            "watchdog_timeout_seconds": args.timeout_seconds,
            "watchdog_deadline_at": watchdog_deadline,
            "prior_active_elapsed_seconds": prior_active_elapsed,
            "installed_claude_code_version": (
                outer_runtime["version"]
                if outer_profile.key == "claude"
                else None
            ),
            "installed_codex_cli_version": (
                outer_runtime["version"]
                if outer_profile.key == "codex"
                else None
            ),
        },
        "inner_shannon_agent": {
            "profile": inner_profile.key,
            "eval_mode_required": True,
            "proof_tool_only": True,
            "source_contract": "proof_stripped_project",
            "managed_tree_mode": True,
            "outer_warm_handoff": True,
            "job_scheduler": {
                "nonblocking": True,
                "max_parallel": MAX_PARALLEL,
            },
        },
        "input_hashes": {
            "agent_profiles": sha256(PROFILE_PATH),
            "agent_config_loader": sha256(PRODUCT / "agent_config.py"),
            "prompt_template": sha256(prompt_template),
            "rendered_prompt": sha256(rendered_path),
            "target": sha256(ROOT / TARGET_REL),
            "runner": sha256(Path(__file__)),
            "shannon_job_scheduler": sha256(PRODUCT / "jobs.py"),
            "shannon_wrapper": sha256(PRODUCT / "inner_runner.py"),
            "warm_handoff": sha256(PRODUCT / "warm_handoff.py"),
            "warm_handoff_sentinel": sha256(
                PRODUCT / "warm_handoff_sentinel.py"
            ),
            "claude_required_mcp_sentinel": sha256(
                ROOT
                / "workflow"
                / "validation"
                / "claude_required_mcp_sentinel.py"
            ),
            "outer_handoff_contract": sha256(
                ROOT / "workflow" / "node" / "outer_proof_handoff.py"
            ),
            "verifier": sha256(ROOT / VERIFIER),
        },
    }
    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)

    preflight_errors: list[str] = []
    for provider in sorted(agent_config.required_provider_keys):
        selected = profiles[provider]
        runtime = provider_runtime[provider]
        if runtime["executable"] is None:
            preflight_errors.append(
                f"{selected.binary_name} CLI is not installed or not on PATH"
            )
            continue
        required_auth_method = "claude.ai" if provider == "claude" else "chatgpt"
        auth = runtime["auth"]
        if (
            not auth.get("logged_in")
            or auth.get("auth_method") != required_auth_method
        ):
            preflight_errors.append(
                f"{selected.binary_name} OAuth is not logged in via "
                f"{required_auth_method}; refusing an ambiguous auth fallback"
            )
        if runtime["provider_identity"] is None:
            preflight_errors.append(
                f"{selected.binary_name} runtime identity could not be bound"
            )
        if runtime["capability_error"]:
            preflight_errors.append(str(runtime["capability_error"]))
    if preflight_errors:
        manifest["status"] = "preflight_provider_failed"
        manifest["preflight_provider_errors"] = preflight_errors
        write_json(manifest_path, manifest)
        raise SystemExit("; ".join(preflight_errors))

    inner_launch_identity = {
        "model": inner_profile.model,
        **provider_cli_identity(inner_profile.backend),
    }
    if provider_identity_projection(inner_launch_identity) != (
        provider_identity_projection(
            provider_runtime[inner_profile.key]["provider_identity"]
        )
    ):
        manifest["status"] = "preflight_provider_failed"
        manifest["preflight_provider_errors"] = [
            "inner provider launch identity differs from runner preflight identity"
        ]
        write_json(manifest_path, manifest)
        raise SystemExit(manifest["preflight_provider_errors"][0])

    if inner_profile.backend == "claude":
        claude_mcp_preflight = run_claude_required_mcp_sentinel(
            claude_executable=str(
                provider_runtime[inner_profile.key]["executable"]
            ),
            model=inner_profile.model,
            output_path=run_dir / "claude_required_mcp_preflight.json",
            project_root=ROOT,
        )
        manifest["claude_required_mcp_preflight"] = {
            "required": True,
            **claude_mcp_preflight,
        }
        if claude_mcp_preflight.get("passed") is not True:
            error = str(
                claude_mcp_preflight.get("error")
                or "Claude required MCP startup sentinel failed"
            )
            manifest["status"] = "preflight_provider_failed"
            manifest["preflight_provider_errors"] = [error]
            write_json(manifest_path, manifest)
            raise SystemExit(error)

    manifest["provider_preflight_passed"] = True
    manifest["preflight_passed"] = True
    write_json(manifest_path, manifest)

    if args.preflight_only:
        manifest["finished_at"] = now()
        manifest["status"] = "preflight_only_passed"
        write_json(manifest_path, manifest)
        print(run_dir)
        return 0

    command, prompt_via_stdin = build_outer_command(
        outer_profile,
        str(outer_runtime["executable"]),
        rendered_prompt=rendered_prompt,
        codex_features=outer_runtime["codex_features"],
    )
    manifest["command"] = (
        command[:-1] + ["<rendered prompt>"]
        if not prompt_via_stdin
        else command
    )
    manifest["prompt_transport"] = "stdin" if prompt_via_stdin else "argument"
    manifest["model_process_launched"] = True
    write_json(manifest_path, manifest)

    events_path = run_dir / "outer_agent_events.jsonl"
    stderr_path = run_dir / "outer_agent_stderr.log"
    process: subprocess.Popen[str] | None = None
    caffeinate: subprocess.Popen[str] | None = None
    timed_out = False
    interrupted = False
    scheduler_cleanup: dict[str, Any] = {"cancelled": []}
    scheduler_cleanup_error = ""
    start = time.monotonic()
    exit_code: int | None = None

    try:
        if shutil.which("caffeinate"):
            caffeinate = subprocess.Popen(
                ["caffeinate", "-dis", "-w", str(os.getpid())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        with events_path.open("w", encoding="utf-8") as events, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            environment = outer_environment.copy()
            environment["INTERLEAVED_RUN_DIR"] = run_rel.as_posix()
            environment[INNER_PROVIDER_ENV] = inner_profile.key
            environment["INTERLEAVED_INNER_PROFILE_SHA256"] = (
                agent_profile_sha256(inner_profile)
            )
            environment[INNER_PROVIDER_IDENTITY_ENV] = json.dumps(
                provider_runtime[inner_profile.key]["provider_identity"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if continuation_rel is not None:
                environment["INTERLEAVED_CONTINUATION_OF"] = (
                    continuation_rel.as_posix()
                )
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                stdin=subprocess.PIPE if prompt_via_stdin else subprocess.DEVNULL,
                stdout=events,
                stderr=stderr,
                start_new_session=True,
            )
            if prompt_via_stdin:
                assert process.stdin is not None
                try:
                    process.stdin.write(rendered_prompt)
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            try:
                exit_code = process.wait(timeout=args.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_group(process)
                exit_code = process.returncode
            except KeyboardInterrupt:
                interrupted = True
                terminate_group(process)
                exit_code = process.returncode
    finally:
        if process is not None:
            terminate_group(process)
        try:
            scheduler_cleanup = cancel_jobs_in_run(
                run_rel=run_rel,
                run_dir=run_dir,
                dispatch_after=False,
            )
        except Exception as exc:
            scheduler_cleanup_error = f"{type(exc).__name__}: {exc}"
        if caffeinate is not None and caffeinate.poll() is None:
            caffeinate.terminate()
        elapsed = time.monotonic() - start

    final_path = run_dir / "final_verification.json"
    final = invoke_verifier("final", final_path)
    shannon_summary = public_job_summary(run_dir)
    private_jobs = private_job_records(run_dir)
    expected_inner_identity = provider_identity_sha256(
        provider_runtime[inner_profile.key]["provider_identity"]
    )
    inner_config_mismatches = fixed_inner_config_mismatches(
        private_jobs,
        inner_profile=inner_profile,
        expected_inner_profile_sha256=agent_profile_sha256(inner_profile),
        expected_identity_sha256=expected_inner_identity,
    )
    orphan_invocation_audit = run_dir / "shannon_invocations.jsonl"
    if orphan_invocation_audit.exists():
        inner_config_mismatches.append("orphan_direct_wrapper_invocation")
    final_passed = final.returncode == 0 and not inner_config_mismatches
    premature_agent_stop = is_premature_agent_stop(
        final_passed=final_passed,
        timed_out=timed_out,
        interrupted=interrupted,
        exit_code=exit_code,
        elapsed_seconds=elapsed,
        timeout_seconds=args.timeout_seconds,
    )
    partial_candidate = (
        None
        if final_passed
        else preserve_partial_candidate(target=ROOT / TARGET_REL, run_dir=run_dir)
    )
    manifest.update(
        {
            "finished_at": now(),
            "elapsed_seconds": elapsed,
            "cumulative_active_elapsed_seconds": prior_active_elapsed + elapsed,
            "outer_exit_code": exit_code,
            "timed_out": timed_out,
            "interrupted": interrupted,
            "shannon_job_cleanup": scheduler_cleanup,
            "shannon_job_cleanup_error": scheduler_cleanup_error,
            "shannon_job_summary": shannon_summary,
            "inner_config_mismatches": inner_config_mismatches,
            "final_verification_passed": final_passed,
            "premature_agent_stop": premature_agent_stop,
            "partial_candidate": partial_candidate,
            "answer_source_visible_at_finish": ANSWER_SOURCE.exists(),
            "final_git_status": run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"]
            ).stdout.splitlines(),
            "status": (
                "proved"
                if final_passed
                else "premature_agent_stop"
                if premature_agent_stop
                else "not_proved"
            ),
        }
    )
    write_json(manifest_path, manifest)

    if not final_passed:
        print(final.stdout, file=sys.stderr)
        print(final.stderr, file=sys.stderr)
        if inner_config_mismatches:
            print(
                "inner-agent configuration drift in jobs: "
                + ", ".join(inner_config_mismatches),
                file=sys.stderr,
            )
    print(run_dir)
    return 0 if final_passed else 1


if __name__ == "__main__":
    sys.exit(main())
