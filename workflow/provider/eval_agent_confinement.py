"""Fail-closed filesystem confinement for evaluation prover agents.

The manager and EasyCrypt backend continue to run in the ordinary project
workspace.  Only the untrusted prover-agent subprocess is placed in a
Bubblewrap mount namespace.  Inside that namespace the project path is rebuilt
from a small allow-list: runtime code, EasyCrypt library sources, the prepared
proof-stripped source bundle, and the current node's advertised memory/private
transport directory.  The original repository, sibling worktrees, stale
sessions, prior agent transcripts, and other experiment artifacts are absent.

This module carries no proof-state authority.  It consumes the durable source
preparation manifest only to construct an OS visibility boundary before an
agent process starts.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from core.easycrypt.eval_source_prep import PROOF_STRIPPED_PROJECT_CONTRACT


EVAL_CONFINEMENT_MANIFEST_ENV = "SHANNON_EVAL_CONFINEMENT_MANIFEST"
EVAL_CONFINEMENT_REQUIRED_ENV = "SHANNON_EVAL_CONFINEMENT_REQUIRED"
CONFINEMENT_KIND = "eval_agent_filesystem_confinement"
CONFINEMENT_SCHEMA_VERSION = 2

# Start Bubblewrap from an empty mount namespace and expose only the host paths
# required by the provider CLI and its dynamically linked runtime.  In
# particular, never use ``--ro-bind / /``: a read-only host root is still a
# proof-exposure boundary failure.
_SYSTEM_READ_PATHS = (
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/etc/alternatives",
    "/etc/ca-certificates",
    "/etc/ssl",
    "/etc/pki",
    "/etc/resolv.conf",
    "/etc/hosts",
    "/etc/host.conf",
    "/etc/gai.conf",
    "/etc/nsswitch.conf",
    "/etc/passwd",
    "/etc/group",
    "/etc/localtime",
)
_SYSTEM_LAYOUT_SYMLINKS = frozenset({"/bin", "/sbin", "/lib", "/lib64"})

_PROJECT_READ_DIRS = (
    "core",
    "workflow",
    "knowledge",
)
_PROJECT_READ_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "pyproject.toml",
    ".python-version",
)
_PROJECT_MASKED_DIRS = (
    # Runtime Python modules live below workflow/, but archived proof-agent
    # transcripts and accepted tactic spines must never cross an eval boundary.
    "workflow/runs",
)


class EvalAgentConfinementError(RuntimeError):
    """Requested evaluation confinement cannot be established safely."""


def _enabled(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_from_project(value: object, project_root: Path) -> Path:
    path = Path(str(value or "").strip())
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _repository_mount_root(project_root: Path) -> Path:
    """Return the shared repository root that must disappear in the sandbox.

    Evaluation worktrees live below ``<repo>/.worktrees/<lane>``.  Masking only
    the lane would leave ``<repo>/eval`` and every sibling lane readable by an
    absolute search, which is the exact leak this boundary is meant to close.
    """

    for parent in (project_root, *project_root.parents):
        if parent.name == ".worktrees":
            return parent.parent.resolve()
    # Detached scheduler lanes may live under /tmp rather than beneath the
    # repository's .worktrees directory.  Resolve their shared Git common dir
    # so the negative probe still names the main checkout and sibling lanes.
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            check=False,
        )
        common_dir = Path(completed.stdout.strip()).resolve()
        if completed.returncode == 0 and common_dir.name == ".git":
            return common_dir.parent
    except (OSError, subprocess.TimeoutExpired):
        pass
    return project_root.resolve()


def _safe_json_object(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalAgentConfinementError(
            f"cannot read evaluation source manifest {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise EvalAgentConfinementError(
            f"evaluation source manifest must be a JSON object: {path}"
        )
    return raw


def _sample_files(root: Path, *, suffix: str, limit: int = 4) -> list[Path]:
    """Return a bounded set of existing host files without reading contents."""

    if limit <= 0 or not root.is_dir():
        return []
    found: list[Path] = []
    try:
        for directory, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                if suffix and not name.endswith(suffix):
                    continue
                found.append((Path(directory) / name).resolve())
                if len(found) >= limit:
                    return found
    except OSError:
        return found
    return found


@dataclass(frozen=True)
class EvalAgentConfinement:
    """Validated inputs for one agent process mount namespace."""

    manifest_path: Path
    project_root: Path
    repository_mount_root: Path
    isolated_root: Path
    isolated_file: Path
    original_file: Path
    node_memory_dir: Path
    private_dir: Path
    include_dirs: tuple[Path, ...]
    target_lemma: str
    bubblewrap: Path

    @property
    def state_root(self) -> Path:
        return self.private_dir / "agent_state"

    @property
    def claude_projects_host_dir(self) -> Path:
        return self.state_root / "claude_home" / "projects"

    @classmethod
    def from_environment(
        cls,
        *,
        project_root: Path,
        source_file: str | Path,
        target_lemma: str,
        node_memory_dir: Path,
        private_dir: Path,
        include_dir: str | Path = "",
        environ: Mapping[str, str] | None = None,
    ) -> "EvalAgentConfinement | None":
        env = os.environ if environ is None else environ
        raw_manifest = str(env.get(EVAL_CONFINEMENT_MANIFEST_ENV) or "").strip()
        required = _enabled(env.get(EVAL_CONFINEMENT_REQUIRED_ENV))
        if not raw_manifest:
            if required:
                raise EvalAgentConfinementError(
                    "evaluation confinement is required but no source manifest "
                    f"was supplied in {EVAL_CONFINEMENT_MANIFEST_ENV}"
                )
            return None

        root = Path(project_root).resolve()
        manifest_path = _resolve_from_project(raw_manifest, root)
        manifest = _safe_json_object(manifest_path)
        if manifest.get("source_contract") != PROOF_STRIPPED_PROJECT_CONTRACT:
            raise EvalAgentConfinementError(
                "evaluation confinement requires a proof-stripped-project "
                f"manifest, got {manifest.get('source_contract')!r}"
            )
        if manifest.get("strip_proofs") is not True:
            raise EvalAgentConfinementError(
                "evaluation confinement source manifest is not proof stripped"
            )
        if str(manifest.get("target_lemma") or "") != str(target_lemma):
            raise EvalAgentConfinementError(
                "evaluation confinement target lemma does not match source "
                f"manifest: {target_lemma!r} != "
                f"{manifest.get('target_lemma')!r}"
            )

        isolated_root = _resolve_from_project(manifest.get("isolated_root"), root)
        isolated_file = _resolve_from_project(manifest.get("isolated_file"), root)
        original_file = _resolve_from_project(manifest.get("original_file"), root)
        actual_source = _resolve_from_project(source_file, root)
        if actual_source != isolated_file:
            raise EvalAgentConfinementError(
                "agent target is not the source file named by the evaluation "
                f"manifest: {actual_source} != {isolated_file}"
            )
        for label, path in (
            ("source manifest", manifest_path),
            ("isolated source root", isolated_root),
            ("isolated source file", isolated_file),
            ("original source file", original_file),
            ("node memory", Path(node_memory_dir).resolve()),
            ("runtime private directory", Path(private_dir).resolve()),
        ):
            if not _is_relative_to(path, root):
                raise EvalAgentConfinementError(
                    f"{label} escapes the current project root: {path}"
                )
        if not isolated_root.is_dir() or not isolated_file.is_file():
            raise EvalAgentConfinementError(
                "proof-stripped source root/file is missing at agent startup"
            )
        if not original_file.is_file() or original_file == isolated_file:
            raise EvalAgentConfinementError(
                "evaluation confinement requires a distinct existing original "
                "source path for the negative visibility probe"
            )
        if not _is_relative_to(isolated_file, isolated_root):
            raise EvalAgentConfinementError(
                f"isolated source file escapes isolated root: {isolated_file}"
            )

        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise EvalAgentConfinementError(
                "evaluation confinement requested but bubblewrap is unavailable"
            )
        for raw in _SYSTEM_READ_PATHS:
            system_path = Path(raw)
            if system_path.is_dir() and _is_relative_to(
                root, system_path.resolve()
            ):
                raise EvalAgentConfinementError(
                    "evaluation project is below a system path that must be "
                    f"mounted into the agent namespace: {system_path}"
                )

        include_dirs: list[Path] = []
        if str(include_dir or "").strip():
            include = _resolve_from_project(include_dir, root)
            if not include.is_dir():
                raise EvalAgentConfinementError(
                    f"evaluation include directory is missing: {include}"
                )
            allowed_include_roots = (
                isolated_root,
                root / "easycrypt-src",
            )
            if _is_relative_to(include, root) and not any(
                _is_relative_to(include, allowed_root)
                for allowed_root in allowed_include_roots
            ):
                raise EvalAgentConfinementError(
                    "evaluation include directory is outside the stripped "
                    f"source and EasyCrypt library roots: {include}"
                )
            # Project-local safe include directories are admitted explicitly.
            # System includes are already covered by the runtime allow-list.
            if _is_relative_to(include, root):
                include_dirs.append(include)

        return cls(
            manifest_path=manifest_path,
            project_root=root,
            repository_mount_root=_repository_mount_root(root),
            isolated_root=isolated_root,
            isolated_file=isolated_file,
            original_file=original_file,
            node_memory_dir=Path(node_memory_dir).resolve(),
            private_dir=Path(private_dir).resolve(),
            include_dirs=tuple(include_dirs),
            target_lemma=str(target_lemma),
            bubblewrap=Path(bwrap).resolve(),
        )

    def prepare(self) -> None:
        """Create only run-local writable state used inside the namespace."""

        self.node_memory_dir.mkdir(parents=True, exist_ok=True)
        self.private_dir.mkdir(parents=True, exist_ok=True)
        codex_home = self.state_root / "codex_home"
        claude_home = self.state_root / "claude_home"
        for path in (
            codex_home / "packages",
            codex_home / "sessions",
            claude_home / "projects",
            claude_home / "file-history",
            claude_home / "shell-snapshots",
        ):
            path.mkdir(parents=True, exist_ok=True)
        for path in (
            codex_home / "auth.json",
            claude_home / ".credentials.json",
            claude_home / "settings.json",
            claude_home / "settings.local.json",
        ):
            path.touch(exist_ok=True)

        # Codex opens its installation identity read/write while starting the
        # in-process app server, and may refresh its model cache.  Seed those
        # non-secret files into the run-local writable home instead of placing
        # read-only host mounts over them.  Authentication remains a read-only
        # host overlay below and is never copied into evaluation artifacts.
        host_codex = Path.home() / ".codex"
        for name in ("installation_id", "models_cache.json"):
            source = host_codex / name
            destination = codex_home / name
            if destination.exists():
                continue
            try:
                shutil.copyfile(source, destination)
            except OSError:
                destination.touch(exist_ok=True)

        # Claude keeps non-secret onboarding state outside ~/.claude.  Preserve
        # enough client state for a non-interactive launch while dropping the
        # project registry that names prior workspaces.
        host_state = Path.home() / ".claude.json"
        local_state = self.state_root / "claude_state.json"
        if not local_state.exists():
            state: dict[str, object] = {}
            try:
                candidate = json.loads(host_state.read_text(encoding="utf-8"))
                if isinstance(candidate, dict):
                    state = dict(candidate)
            except (OSError, json.JSONDecodeError):
                pass
            state["projects"] = {}
            state["githubRepoPaths"] = {}
            local_state.write_text(
                json.dumps(state, sort_keys=True) + "\n", encoding="utf-8"
            )

    def audit_record(
        self,
        probe_results: Mapping[str, object],
    ) -> dict[str, object]:
        required = (
            "original_repository_visible",
            "sibling_worktrees_visible",
            "prior_agent_transcripts_visible",
            "host_tmp_visible",
        )
        if probe_results.get("probe_status") != "passed" or any(
            probe_results.get(key) is not False for key in required
        ):
            raise EvalAgentConfinementError(
                "refusing to record evaluation confinement without a passing "
                "negative visibility probe"
            )
        return {
            "schema_version": CONFINEMENT_SCHEMA_VERSION,
            "kind": CONFINEMENT_KIND,
            "mode": "bubblewrap_selective_mounts",
            "target_lemma": self.target_lemma,
            "source_manifest": str(self.manifest_path),
            "isolated_root": str(self.isolated_root),
            "isolated_file": str(self.isolated_file),
            "project_root": str(self.project_root),
            "repository_mount_root": str(self.repository_mount_root),
            "node_memory_dir": str(self.node_memory_dir),
            "private_dir": str(self.private_dir),
            "probe_status": "passed",
            "original_repository_visible": probe_results[
                "original_repository_visible"
            ],
            "sibling_worktrees_visible": probe_results[
                "sibling_worktrees_visible"
            ],
            "prior_agent_transcripts_visible": probe_results[
                "prior_agent_transcripts_visible"
            ],
            "host_tmp_visible": probe_results["host_tmp_visible"],
            "probe_path_counts": {
                str(key): len(value) if isinstance(value, list) else 0
                for key, value in dict(
                    probe_results.get("probe_paths") or {}
                ).items()
            },
        }

    def write_audit_record(self, probe_results: Mapping[str, object]) -> Path:
        self.prepare()
        path = self.private_dir / "eval_agent_confinement.json"
        path.write_text(
            json.dumps(
                self.audit_record(probe_results), indent=2, sort_keys=True
            ) + "\n",
            encoding="utf-8",
        )
        return path

    def wrap_command(
        self,
        command: Sequence[str],
        *,
        agent_backend: str,
    ) -> list[str]:
        """Return a Bubblewrap argv for one provider CLI invocation."""

        if not command:
            raise EvalAgentConfinementError("cannot confine an empty command")
        self.prepare()
        executable_text = str(command[0])
        executable_candidate = (
            executable_text
            if Path(executable_text).is_absolute()
            else str(shutil.which(executable_text) or "")
        )
        executable = Path(executable_candidate).resolve()
        if not executable_candidate or not executable.is_file():
            raise EvalAgentConfinementError(
                f"cannot resolve confined executable: {executable_text!r}"
            )

        args = [
            str(self.bubblewrap),
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--share-net",  # provider API and manager's loopback MCP bridge
        ]
        made_dirs: set[Path] = {Path("/")}
        mounted_destinations: list[Path] = []
        bound_destinations: list[Path] = []

        def covered(path: Path) -> bool:
            return any(
                path == destination or _is_relative_to(path, destination)
                for destination in mounted_destinations
            )

        def host_content_visible(path: Path) -> bool:
            return any(
                path == destination or _is_relative_to(path, destination)
                for destination in bound_destinations
            )

        def ensure_parent(path: Path) -> None:
            parents: list[Path] = []
            cursor = path.parent
            while cursor != Path("/"):
                if covered(cursor):
                    break
                parents.append(cursor)
                cursor = cursor.parent
            for parent in reversed(parents):
                if parent not in made_dirs and not covered(parent):
                    args.extend(["--dir", str(parent)])
                    made_dirs.add(parent)

        def bind_path(source: Path, destination: Path, *, writable: bool) -> None:
            source = source.resolve()
            destination = destination.absolute()
            ensure_parent(destination)
            args.extend([
                "--bind" if writable else "--ro-bind",
                str(source),
                str(destination),
            ])
            if source.is_dir():
                mounted_destinations.append(destination)
                bound_destinations.append(destination)

        def ro_bind(path: Path) -> None:
            bind_path(path, path, writable=False)

        def rw_bind(path: Path) -> None:
            bind_path(path, path, writable=True)

        def tmpfs(path: Path) -> None:
            path = path.absolute()
            ensure_parent(path)
            args.extend(["--tmpfs", str(path)])
            mounted_destinations.append(path)

        # Bubblewrap constructs a fresh root.  Admit only ordinary runtime
        # paths, never the host root, home, /tmp, /var, /mnt, or another data
        # volume wholesale.  Preserve merged-/usr symlinks where applicable.
        for raw in _SYSTEM_READ_PATHS:
            path = Path(raw)
            if raw in _SYSTEM_LAYOUT_SYMLINKS and path.is_symlink():
                ensure_parent(path)
                args.extend(["--symlink", os.readlink(path), str(path)])
            elif path.exists():
                ro_bind(path)
        args.extend(["--proc", "/proc", "--dev", "/dev"])
        tmpfs(Path("/tmp"))
        tmpfs(Path("/var/tmp"))

        # Recreate the current lane, but only with code and non-eval library
        # sources needed by the MCP shim or legitimate proof lookup.
        for relative in _PROJECT_READ_DIRS:
            path = self.project_root / relative
            if path.is_dir():
                ro_bind(path)
        for relative in _PROJECT_READ_FILES:
            path = self.project_root / relative
            if path.is_file():
                ro_bind(path)
        for relative in _PROJECT_MASKED_DIRS:
            path = self.project_root / relative
            if path.is_dir():
                tmpfs(path)

        # The private MCP transport is launched with ``sys.executable``.  In
        # worktree evaluations that interpreter commonly lives in a shared
        # repository-local virtualenv, which disappeared with the repository
        # mask above.  Re-expose only that dependency environment read-only;
        # never re-expose a prefix that contains the project itself.
        runtime_prefix = Path(sys.prefix).resolve()
        if not host_content_visible(runtime_prefix):
            if _is_relative_to(self.project_root, runtime_prefix):
                raise EvalAgentConfinementError(
                    "refusing to expose a Python runtime prefix that contains "
                    f"the evaluation project: {runtime_prefix}"
                )
            if not (runtime_prefix / "pyvenv.cfg").is_file():
                raise EvalAgentConfinementError(
                    "masked Python runtime prefix is not a validated virtualenv: "
                    f"{runtime_prefix}"
                )
            ro_bind(runtime_prefix)

        # A virtualenv may use an absolute symlink into a separately installed
        # base interpreter (notably uv-managed Python). Mounting only the
        # virtualenv then exposes the symlink but not the standard library, and
        # resolving ``sys.executable`` to one file is insufficient. Admit the
        # validated base-interpreter prefix when system mounts do not already
        # cover it. This is runtime-only dependency exposure: a prefix that
        # contains the evaluation project remains forbidden.
        base_runtime_prefix = Path(sys.base_prefix).resolve()
        python_executable = Path(sys.executable).resolve()
        if (
            base_runtime_prefix != runtime_prefix
            and not host_content_visible(base_runtime_prefix)
        ):
            if _is_relative_to(self.project_root, base_runtime_prefix):
                raise EvalAgentConfinementError(
                    "refusing to expose a Python base runtime prefix that "
                    f"contains the evaluation project: {base_runtime_prefix}"
                )
            if not (
                _is_relative_to(python_executable, base_runtime_prefix)
                and (base_runtime_prefix / "lib").is_dir()
            ):
                raise EvalAgentConfinementError(
                    "masked Python base runtime prefix is not a validated "
                    f"interpreter installation: {base_runtime_prefix}"
                )
            ro_bind(base_runtime_prefix)

        # Provider CLIs may be installed as a user-local standalone binary.
        # Rewrite argv[0] to the resolved target and expose that one file only;
        # its dynamic runtime is supplied by the system mounts above.
        if not host_content_visible(executable):
            ro_bind(executable)

        ro_bind(self.isolated_root)
        for include in self.include_dirs:
            if include != self.isolated_root and not _is_relative_to(
                include, self.isolated_root
            ):
                ro_bind(include)
        rw_bind(self.node_memory_dir)
        rw_bind(self.private_dir)

        home = Path.home().resolve()
        backend = str(agent_backend or "").strip().lower()
        if backend == "codex":
            codex_home = (self.state_root / "codex_home").resolve()
            bind_path(codex_home, home / ".codex", writable=True)
            host_codex = home / ".codex"
            for name in ("auth.json",):
                source = host_codex / name
                if source.is_file():
                    bind_path(
                        source, home / ".codex" / name, writable=False
                    )
            packages = host_codex / "packages" / "standalone"
            if packages.is_dir():
                bind_path(
                    packages,
                    home / ".codex" / "packages" / "standalone",
                    writable=False,
                )
            if _is_relative_to(executable, host_codex):
                bind_path(executable, executable, writable=False)
        elif backend == "claude":
            claude_home = (self.state_root / "claude_home").resolve()
            bind_path(claude_home, home / ".claude", writable=True)
            host_claude = home / ".claude"
            for name in (".credentials.json", "settings.json", "settings.local.json"):
                source = host_claude / name
                if source.is_file():
                    bind_path(
                        source, home / ".claude" / name, writable=False
                    )
            bind_path(
                (self.state_root / "claude_state.json").resolve(),
                home / ".claude.json",
                writable=True,
            )
            if _is_relative_to(executable, host_claude):
                bind_path(executable, executable, writable=False)
        else:
            raise EvalAgentConfinementError(
                f"unsupported confined agent backend: {agent_backend!r}"
            )

        args.extend([
            "--chdir",
            str(self.project_root),
            "--",
            str(executable),
            *(str(item) for item in command[1:]),
        ])
        return args

    def _negative_probe_paths(
        self,
        *,
        agent_backend: str,
    ) -> dict[str, list[str]]:
        original_paths = [self.original_file]
        git_config = self.repository_mount_root / ".git" / "config"
        if git_config.exists():
            original_paths.append(git_config)
        original_paths.extend(
            _sample_files(
                self.repository_mount_root / "easycrypt-src" / "examples",
                suffix=".ec",
                limit=4,
            )
        )

        sibling_paths: list[Path] = []
        worktrees = self.repository_mount_root / ".worktrees"
        if worktrees.is_dir():
            try:
                for child in sorted(worktrees.iterdir()):
                    resolved = child.resolve()
                    if _is_relative_to(self.project_root, resolved):
                        continue
                    sibling_paths.append(resolved)
                    if len(sibling_paths) >= 4:
                        break
            except OSError:
                pass

        home = Path.home().resolve()
        backend = str(agent_backend or "").strip().lower()
        transcript_root = (
            home / ".claude" / "projects"
            if backend == "claude"
            else home / ".codex" / "sessions"
        )
        transcript_paths = _sample_files(transcript_root, suffix=".jsonl")
        transcript_paths.extend(
            _sample_files(
                self.project_root / "workflow" / "runs",
                suffix=".md",
                limit=max(0, 4 - len(transcript_paths)),
            )
        )

        tmp_paths: list[Path] = []
        host_tmp = Path("/tmp")
        if host_tmp.is_dir():
            try:
                for child in sorted(host_tmp.iterdir()):
                    resolved = child.resolve()
                    if _is_relative_to(self.project_root, resolved):
                        continue
                    tmp_paths.append(resolved)
                    if len(tmp_paths) >= 4:
                        break
            except OSError:
                pass

        return {
            "original_repository_visible": [
                str(path) for path in original_paths if path.exists()
            ],
            "sibling_worktrees_visible": [str(path) for path in sibling_paths],
            "prior_agent_transcripts_visible": [
                str(path) for path in transcript_paths
            ],
            "host_tmp_visible": [str(path) for path in tmp_paths],
        }

    def probe(
        self,
        *,
        agent_backend: str,
        timeout: float = 15.0,
    ) -> dict[str, object]:
        """Prove allowed readability and forbidden host-path invisibility."""

        probe_paths = self._negative_probe_paths(agent_backend=agent_backend)
        specification = {
            "allowed": [
                str(self.isolated_file),
                str(self.node_memory_dir),
                str(self.private_dir),
            ],
            "forbidden": probe_paths,
        }
        probe_code = """
import json
import os
import sys

spec = json.loads(sys.argv[1])
allowed_readable = all(
    os.path.exists(path) and os.access(path, os.R_OK)
    for path in spec["allowed"]
)
result = {
    key: any(os.path.lexists(path) for path in paths)
    for key, paths in spec["forbidden"].items()
}
forbidden_visible = any(result.values())
result["allowed_paths_readable"] = allowed_readable
result["probe_status"] = (
    "passed" if allowed_readable and not forbidden_visible else "failed"
)
print(json.dumps(result, sort_keys=True))
raise SystemExit(0 if result["probe_status"] == "passed" else 23)
""".strip()
        command = self.wrap_command(
            [sys.executable, "-c", probe_code, json.dumps(specification)],
            agent_backend=agent_backend,
        )
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EvalAgentConfinementError(
                f"evaluation confinement probe failed: {exc}"
            ) from exc
        try:
            result = json.loads((completed.stdout or "").strip())
        except (json.JSONDecodeError, TypeError):
            result = {}
        if not isinstance(result, dict):
            result = {}
        if completed.returncode != 0 or result.get("probe_status") != "passed":
            detail = (completed.stderr or completed.stdout or "").strip()[:500]
            raise EvalAgentConfinementError(
                "evaluation confinement probe could not establish the selective "
                f"mount namespace (rc={completed.returncode}): {detail}"
            )
        result["probe_paths"] = probe_paths
        return result


def confinement_environment(
    *,
    manifest_path: Path,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a subprocess environment requesting mandatory confinement."""

    env = dict(os.environ if base is None else base)
    env[EVAL_CONFINEMENT_MANIFEST_ENV] = str(Path(manifest_path).resolve())
    env[EVAL_CONFINEMENT_REQUIRED_ENV] = "1"
    return env


def clear_confinement_environment(
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env.pop(EVAL_CONFINEMENT_MANIFEST_ENV, None)
    env.pop(EVAL_CONFINEMENT_REQUIRED_ENV, None)
    return env


__all__ = [
    "CONFINEMENT_KIND",
    "CONFINEMENT_SCHEMA_VERSION",
    "EVAL_CONFINEMENT_MANIFEST_ENV",
    "EVAL_CONFINEMENT_REQUIRED_ENV",
    "EvalAgentConfinement",
    "EvalAgentConfinementError",
    "clear_confinement_environment",
    "confinement_environment",
]
