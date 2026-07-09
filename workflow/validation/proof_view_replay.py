"""Replay human EasyCrypt proofs against the prover-facing ProofContextView.

This is a calibration tool, not an LLM prover.  It answers a narrow question:
after replaying a human proof prefix, does the current ProofContextView provide
enough clean information to make the next human tactic unsurprising?

Typical use:

  python3 -m workflow.validation.proof_view_replay scan /tmp/easycrypt-public-examples/examples --min-lines 20
  python3 -m workflow.validation.proof_view_replay replay \
    --file /tmp/easycrypt-public-examples/examples/ChaChaPoly/chacha_poly.ec \
    --lemma step1 --max-steps 12

The replay command creates a temporary session and applies the human tactics
one by one.  Before each tactic it records a compact view summary and a rough
"alignment" judgment between the next human tactic and the surfaced actions.

Use ``--mode batch`` for normal calibration.  It keeps one Python session
runtime alive and lets ``Session.append_block`` use the EasyCrypt daemon fast
path, avoiding the old two-subprocess-per-step harness.  Batch mode skips the
stateful post-commit hook phases by default because the next pre-step
ProofContextView rebuilds ProofIR directly; pass ``--full-hooks`` when you want
to reproduce the complete ``session_cli -next`` display pipeline.
``--mode subprocess`` is kept as a compatibility fallback.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SESSION_CLI = _PROJECT_ROOT / "core" / "easycrypt" / "session_cli.py"
_DEFAULT_INCLUDES = [
    _PROJECT_ROOT / "easycrypt-src" / "theories",
    _PROJECT_ROOT / "easycrypt-src" / "theories" / "crypto",
    _PROJECT_ROOT / "easycrypt-src" / "theories" / "datatypes",
    _PROJECT_ROOT / "easycrypt-src" / "theories" / "distributions",
]


try:
    from workflow.validation.prover_view_text_lint import (  # type: ignore
        lint_prover_facing_payload,
    )
except Exception:
    lint_prover_facing_payload = None  # type: ignore


@dataclass
class ProofSpan:
    file: Path
    name: str
    decl_line: int
    proof_line: int
    qed_line: int
    body: list[str]

    @property
    def body_lines(self) -> int:
        return len(self.body)


def _read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def iter_proof_spans(root: Path) -> Iterable[ProofSpan]:
    decl_re = re.compile(
        r"^\s*(?:local\s+)?(?:lemma|equiv|phoare|hoare)\s+"
        r"([A-Za-z_][A-Za-z0-9_']*)\b"
    )
    proof_re = re.compile(r"^\s*proof\.\s*$")
    qed_re = re.compile(r"^\s*qed\.\s*$")

    files = [root] if root.is_file() else sorted(root.rglob("*"))
    for path in files:
        if path.suffix not in {".ec", ".eca"}:
            continue
        lines = _read(path)
        last_decl: tuple[str, int] | None = None
        for idx, line in enumerate(lines):
            m = decl_re.match(line)
            if m:
                last_decl = (m.group(1), idx + 1)
                continue
            if not (last_decl and proof_re.match(line)):
                continue
            depth = 1
            j = idx + 1
            while j < len(lines):
                if proof_re.match(lines[j]):
                    depth += 1
                if qed_re.match(lines[j]):
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j < len(lines):
                yield ProofSpan(
                    file=path,
                    name=last_decl[0],
                    decl_line=last_decl[1],
                    proof_line=idx + 1,
                    qed_line=j + 1,
                    body=lines[idx + 1:j],
                )
            last_decl = None


def _split_human_tactics(body: list[str]) -> list[str]:
    tactics = _split_human_tactics_by_proof_lines(body)
    if tactics:
        return tactics
    text = "\n".join(line for line in body if line.strip())
    try:
        sys.path.insert(0, str(_PROJECT_ROOT / "core" / "easycrypt"))
        from daemon_backend import _split_tactics  # type: ignore
        tactics = _split_tactics(text)
    except Exception:
        tactics = _fallback_split_tactics(text)
    return [t.strip() for t in tactics if t.strip()]


def _split_human_tactics_by_proof_lines(body: list[str]) -> list[str]:
    """Split like a human-written proof, preserving EasyCrypt bullets.

    The daemon splitter is correct for raw EC command streams, but for
    calibration we want source-line granularity: a bullet claim
    ``+ have ... .`` and the next bullet ``+ by ... .`` are distinct human
    moves even when later tooling could compact them into one command.
    """
    tactics: list[str] = []
    buf: list[str] = []
    in_comment = 0
    for raw in body:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("(*") and stripped.endswith("*)"):
            continue
        # Strip simple inline comments; calibration examples use comments as
        # annotations, not as tactic syntax.
        line = re.sub(r"\(\*.*?\*\)", "", line).rstrip()
        if not line.strip():
            continue
        buf.append(line)
        for m in re.finditer(r"\(\*|\*\)", line):
            if m.group(0) == "(*":
                in_comment += 1
            elif in_comment:
                in_comment -= 1
        if in_comment == 0 and re.search(r"\.\s*$", line):
            tactics.append("\n".join(buf).strip())
            buf = []
    if buf:
        tactics.append("\n".join(buf).strip())
    return tactics


def _fallback_split_tactics(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    in_comment = 0
    for ch in text:
        buf.append(ch)
        tail = "".join(buf[-2:])
        if tail == "(*":
            in_comment += 1
        elif tail == "*)" and in_comment:
            in_comment -= 1
        elif ch == "." and not in_comment:
            out.append("".join(buf).strip())
            buf = []
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def _display_tactic(tactic: str, limit: int = 160) -> str:
    compact = " ".join(tactic.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _tactic_head(tactic: str) -> str:
    text = tactic.strip()
    text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.S).strip()
    text = re.sub(r"^[+\-*]\s*", "", text)
    text = re.sub(r"^(by\s+)+", "", text)
    if text.startswith("have"):
        return "have"
    if text.startswith("rewrite"):
        return "rewrite"
    m = re.match(r"([A-Za-z_][A-Za-z0-9_']*|/=?[A-Za-z_][A-Za-z0-9_']*)", text)
    return m.group(1) if m else text[:20]


_BUCKETS = (
    "pr_bridge",
    "pr_arithmetic",
    "procedure_control",
    "invariant",
    "call_handle",
    "hoare_prob",
    "ambient_logic",
    "close",
    "other",
)


def _normalized_tactic(tactic: str) -> str:
    text = tactic.strip()
    text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.S).strip()
    text = re.sub(r"^[+\-*]\s*", "", text)
    text = re.sub(r"^(by\s+)+", "", text)
    return " ".join(text.split())


def _tactic_bucket(tactic: str, layer: str | None = None) -> str:
    """Classify the next human tactic by the compiler frontend it needs.

    This is validation bookkeeping, not prover logic.  It lets replay reports
    answer whether missing guidance concentrates in Pr bridge planning,
    program/control-flow frontend, invariant skeletons, or closing residue.
    """
    text = _normalized_tactic(tactic)
    low = text.lower()
    head = _tactic_head(tactic)
    low_head = head.lower()

    if low_head in {"auto", "smt", "done", "trivial", "sim", "progress"}:
        return "close"
    if re.match(r"(auto|smt|done|trivial|sim|progress)\b", low):
        return "close"

    if re.match(r"(call|ecall)\s*\(_\s*:", low):
        return "invariant"
    if low_head == "while":
        return "invariant"
    if low_head in {"seq", "conseq"} and ":" in text:
        return "invariant"

    if low_head in {
        "proc",
        "inline",
        "wp",
        "sp",
        "seq",
        "if",
        "case",
        "swap",
        "rnd",
        "rcondt",
        "rcondf",
        "unroll",
        "splitwhile",
        "skip",
    }:
        return "procedure_control"

    if low_head in {"call", "ecall"}:
        return "call_handle"

    if low_head in {"byphoare", "phoare", "hoare"}:
        return "hoare_prob"

    if re.search(r"\b(ler_|realorder|lez_|ltr_|ler|mu\b|bound|birthday)\b", low):
        return "pr_arithmetic"
    if low_head == "apply" and (layer == "pr" or "pr[" in low):
        return "pr_arithmetic"
    if low_head == "exact" and re.search(r"\bpr_[a-z0-9_']*", low):
        return "pr_bridge"
    if low_head == "transitivity" and layer == "pr":
        return "pr_bridge"
    if low_head == "transitivity":
        return "procedure_control"
    if low_head in {
        "move",
        "exlim",
        "elim",
        "pose",
        "exists",
        "split",
        "do",
        "suff",
        "have",
    }:
        return "ambient_logic"

    if (
        low_head in {"have", "rewrite", "congr", "byequiv", "transitivity"}
        or "pr[" in low
        or re.search(r"\bpr_[a-z0-9_']*", low)
    ):
        if layer == "pr" or "pr[" in low or "pr_" in low:
            return "pr_bridge"
        return "other"

    return "other"


def _view_signal_buckets(text_blob: str) -> list[str]:
    low = text_blob.lower()
    buckets: list[str] = []
    if re.search(r"pr_|pr path|pr_path|checkpoint|bridge|signature_lookup", low):
        buckets.append("pr_bridge")
    if re.search(
        r"pr arithmetic|inequality|union-bound|bound lemma|ler_|realorder",
        low,
    ):
        buckets.append("pr_arithmetic")
    if re.search(
        r"program_|control-flow|procedure|inline|wp|seq|swap|rcond|rnd|splitwhile",
        low,
    ):
        buckets.append("procedure_control")
    if re.search(r"invariant|obligation|skeleton|call \(_:", low):
        buckets.append("invariant")
    if re.search(r"call site|call-site|call handle|named equiv|call [a-z0-9_.']+", low):
        buckets.append("call_handle")
    if re.search(r"phoare|hoare|byphoare", low):
        buckets.append("hoare_prob")
    if re.search(r"ambient logic|pure logic|exists|split|pose|case analysis", low):
        buckets.append("ambient_logic")
    if re.search(r"suggest-close|close|smt|auto|sim", low):
        buckets.append("close")
    return [bucket for bucket in _BUCKETS if bucket in set(buckets)]


def _view_actions(view: dict) -> list[dict]:
    actions: list[dict] = []
    for key in ("safe_next_actions", "actions"):
        value = view.get(key)
        if isinstance(value, list):
            actions.extend(item for item in value if isinstance(item, dict))
    guidance = view.get("guidance")
    recs = guidance.get("recommendations") if isinstance(guidance, dict) else None
    if isinstance(recs, list):
        actions.extend(item for item in recs if isinstance(item, dict))
    proof_ir = view.get("proof_ir")
    menu = proof_ir.get("candidate_menu") if isinstance(proof_ir, dict) else None
    if isinstance(menu, list):
        actions.extend(item for item in menu if isinstance(item, dict))
    return actions


def _align_next_tactic(view: dict, tactic: str) -> dict:
    head = _tactic_head(tactic)
    actions = _view_actions(view)
    rendered = [
        str(a.get("action") or a.get("tactic") or a.get("command") or "")
        for a in actions
    ]
    text_blob = "\n".join(rendered + [json.dumps(view.get("proof_ir", {}))])
    exact = any(_display_tactic(tactic).rstrip(".") in item for item in rendered)
    head_seen = any(item.strip().startswith(head) for item in rendered)
    bridge_seen = bool(re.search(
        r"pr_|PR_CHECKPOINT|pr_path|bridge|checkpoint|signature_lookup",
        text_blob,
        re.I,
    ))
    proof_ir = view.get("proof_ir") if isinstance(view.get("proof_ir"), dict) else {}
    layer = proof_ir.get("current_layer") or (
        proof_ir.get("current", {}).get("abstraction_layer")
        if isinstance(proof_ir.get("current"), dict)
        else None
    )
    target_bucket = _tactic_bucket(tactic, str(layer) if layer else None)
    signal_buckets = _view_signal_buckets(text_blob)
    target_signal_seen = target_bucket in signal_buckets
    if exact:
        verdict = "exact"
        support_level = "exact"
    elif head_seen:
        verdict = "head"
        support_level = "head"
    elif head in {"have", "rewrite"} and bridge_seen:
        verdict = "bridge_oriented"
        support_level = "compiler_signal"
    else:
        verdict = "missing"
        support_level = "bucket_only" if target_signal_seen else "absent"
    return {
        "next_tactic": _display_tactic(tactic),
        "next_head": head,
        "target_bucket": target_bucket,
        "verdict": verdict,
        "support_level": support_level,
        "view_signal_buckets": signal_buckets,
        "target_signal_seen": target_signal_seen,
        "missing_detail": (
            ""
            if verdict != "missing"
            else (
                f"{target_bucket} signal is present, but no matching tactic form/head was surfaced"
                if target_signal_seen
                else f"no matching tactic form/head or {target_bucket} signal surfaced"
            )
        ),
        "layer": layer,
        "top_actions": rendered[:8],
    }


def _bucket_counts(steps: list[dict], *, verdict: str | None = None) -> dict[str, int]:
    counts = {bucket: 0 for bucket in _BUCKETS}
    for step in steps:
        if verdict is not None and step.get("verdict") != verdict:
            continue
        bucket = str(step.get("target_bucket") or "other")
        if bucket not in counts:
            bucket = "other"
        counts[bucket] += 1
    return {bucket: count for bucket, count in counts.items() if count}


def _missing_examples(steps: list[dict], limit: int = 12) -> list[dict]:
    examples: list[dict] = []
    for step in steps:
        if step.get("verdict") != "missing":
            continue
        examples.append({
            "index": step.get("index"),
            "bucket": step.get("target_bucket"),
            "support_level": step.get("support_level"),
            "head": step.get("next_head"),
            "layer": step.get("layer"),
            "next_tactic": step.get("next_tactic"),
            "detail": step.get("missing_detail"),
        })
        if len(examples) >= limit:
            break
    return examples


def _alignment_summary(steps: list[dict]) -> dict:
    missing_steps = [s for s in steps if s.get("verdict") == "missing"]
    return {
        "missing_view_alignments": len(missing_steps),
        "steps_by_bucket": _bucket_counts(steps),
        "missing_by_bucket": _bucket_counts(steps, verdict="missing"),
        "missing_bucket_only": sum(
            1 for s in missing_steps if s.get("support_level") == "bucket_only"
        ),
        "missing_absent": sum(
            1 for s in missing_steps if s.get("support_level") == "absent"
        ),
        "missing_examples": _missing_examples(steps),
    }


def _run_cli(args: list[str], *, env: dict, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SESSION_CLI), *args],
        cwd=str(_PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ec_env() -> dict:
    try:
        from core.easycrypt.ec_env import get_ec_env
        env = get_ec_env()
    except Exception:
        env = os.environ.copy()
    env["SHANNON_LEGACY_DISPLAY"] = "off"
    return env


def _include_args(file: Path, extra: list[Path]) -> list[str]:
    dirs: list[Path] = []
    dirs.extend(p for p in _DEFAULT_INCLUDES if p.exists())
    dirs.append(file.parent)
    # Include the examples root for sibling imports, but do not recursively
    # add every example subdirectory; that made public-checkout calibration
    # unnecessarily slow and noisy.
    for parent in [file.parent, *file.parent.parents]:
        if parent.name == "examples":
            dirs.append(parent)
            break
    dirs.extend(extra)
    seen: set[str] = set()
    args: list[str] = []
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key in seen:
            continue
        seen.add(key)
        args.extend(["-I", key])
    return args


def scan(args: argparse.Namespace) -> int:
    rows = [
        span for root in args.roots
        for span in iter_proof_spans(Path(root))
        if span.body_lines >= args.min_lines
    ]
    rows.sort(key=lambda s: (s.body_lines, str(s.file), s.name), reverse=True)
    for span in rows[: args.limit]:
        print("\t".join(map(str, [
            span.body_lines,
            len(_split_human_tactics(span.body)),
            span.file,
            span.name,
            span.decl_line,
            span.proof_line,
            span.qed_line,
        ])))
    return 0


def replay(args: argparse.Namespace) -> int:
    file = Path(args.file).resolve()
    spans = [s for s in iter_proof_spans(file) if s.name == args.lemma]
    if not spans:
        raise SystemExit(f"lemma not found: {args.lemma} in {file}")
    span = spans[0]
    tactics = _split_human_tactics(span.body)
    if args.max_steps:
        tactics = tactics[: args.max_steps]
    out_dir = Path(args.out_dir).resolve()
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    session_dir = out_dir / f".ec_session_{file.stem}_{args.lemma}"
    tactic_dir = out_dir / "tactics"
    tactic_dir.mkdir(exist_ok=True)
    includes = _include_args(file, [Path(p) for p in args.include])

    if args.mode == "batch":
        return _replay_batch(
            args=args,
            file=file,
            span=span,
            tactics=tactics,
            out_dir=out_dir,
            session_dir=session_dir,
            tactic_dir=tactic_dir,
            includes=includes,
        )

    return _replay_subprocess(
        args=args,
        file=file,
        span=span,
        tactics=tactics,
        out_dir=out_dir,
        session_dir=session_dir,
        tactic_dir=tactic_dir,
        includes=includes,
    )


def _replay_subprocess(
    *,
    args: argparse.Namespace,
    file: Path,
    span: ProofSpan,
    tactics: list[str],
    out_dir: Path,
    session_dir: Path,
    tactic_dir: Path,
    includes: list[str],
) -> int:
    env = _ec_env()

    start = _run_cli(
        ["-d", str(session_dir), "-start", "-f", str(file), "-lemma", args.lemma, *includes],
        env=env,
        timeout=args.timeout,
    )
    if start.returncode != 0:
        (out_dir / "start.stderr.txt").write_text(start.stderr, encoding="utf-8")
        (out_dir / "start.stdout.txt").write_text(start.stdout, encoding="utf-8")
        raise SystemExit(f"session start failed: {start.stderr[:300]}")

    steps: list[dict] = []
    for idx, tactic in enumerate(tactics):
        view_proc = _run_cli(
            ["-d", str(session_dir), "-agent-view"],
            env=env,
            timeout=args.timeout,
        )
        try:
            view = json.loads(view_proc.stdout)
        except Exception:
            view = {"parse_error": view_proc.stdout[-1000:], "stderr": view_proc.stderr}
        alignment = _align_next_tactic(view, tactic)
        tactic_path = tactic_dir / f"{idx:03d}.ec"
        tactic_path.write_text(tactic + "\n", encoding="utf-8")
        next_proc = _run_cli(
            ["-d", str(session_dir), "-next", "--from-file", str(tactic_path)],
            env=env,
            timeout=args.timeout,
        )
        accepted = next_proc.returncode == 0
        steps.append({
            "index": idx,
            **alignment,
            "accepted": accepted,
            "stdout_tail": next_proc.stdout[-1200:],
            "stderr_tail": next_proc.stderr[-1200:],
        })
        print(
            f"{idx:03d} {alignment['verdict']:<15} "
            f"{alignment.get('layer') or '?':<22} "
            f"{_display_tactic(tactic, 110)}",
            flush=True,
        )
        if not accepted:
            break

    report = {
        "file": str(file),
        "lemma": args.lemma,
        "proof_lines": span.body_lines,
        "steps_requested": len(tactics),
        "steps": steps,
        "summary": {
            "accepted_steps": sum(1 for s in steps if s.get("accepted")),
            **_alignment_summary(steps),
        },
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    missing = sum(1 for s in steps if s["verdict"] == "missing")
    print(f"\nreport: {out_dir / 'report.json'}", flush=True)
    print(f"missing-view-alignments: {missing}/{len(steps)}", flush=True)
    return 1 if missing and args.fail_on_missing else 0


def _replay_batch(
    *,
    args: argparse.Namespace,
    file: Path,
    span: ProofSpan,
    tactics: list[str],
    out_dir: Path,
    session_dir: Path,
    tactic_dir: Path,
    includes: list[str],
) -> int:
    _ensure_easycrypt_import_path()
    try:
        from core.easycrypt.lemma_extract import extract_lemma
        from core.easycrypt.session_agent_view import (
            build_proof_context_view,
            record_proof_context_view,
        )
        from core.easycrypt.session_api import open_session
        from core.easycrypt.session_events import event_payload, read_events
    except Exception:
        from lemma_extract import extract_lemma  # type: ignore
        from session_agent_view import build_proof_context_view, record_proof_context_view  # type: ignore
        from session_api import open_session  # type: ignore
        from session_events import event_payload, read_events  # type: ignore

    session = open_session(session_dir, include_dirs=_include_values(includes))
    if not args.full_hooks:
        try:
            session.commit_phases = []
        except Exception:
            pass
    _start_extracted_lemma_session(
        session=session,
        file=file,
        lemma=args.lemma,
        includes=_include_values(includes),
        extract_lemma=extract_lemma,
    )

    steps: list[dict] = []
    started = time.perf_counter()
    for idx, tactic in enumerate(tactics):
        view_start = time.perf_counter()
        view = build_proof_context_view(
            session_dir,
            live_tool_name="proof-view-replay",
            max_recommendations=8,
            max_stale_recommendations=4,
        )
        view_record: dict = {}
        try:
            view_record = record_proof_context_view(
                session,
                view,
                source="proof_view_replay.pre_step",
            )
        except Exception:
            pass
        view_ms = int((time.perf_counter() - view_start) * 1000)
        alignment = _align_next_tactic(view, tactic)
        lint_issues = _lint_view(view)

        tactic_path = tactic_dir / f"{idx:03d}.ec"
        tactic_path.write_text(tactic + "\n", encoding="utf-8")
        apply_start = time.perf_counter()
        delta = session.append_block(tactic)
        apply_ms = int((time.perf_counter() - apply_start) * 1000)
        transition = _latest_tactic_result(read_events(session_dir), event_payload)
        status = str(transition.get("status") or "")
        accepted = status == "ok" and transition.get("history_committed") is not False
        steps.append({
            "index": idx,
            **alignment,
            "accepted": accepted,
            "status": status,
            "daemon_used": bool(transition.get("daemon_used")),
            "view_artifact": str(view_record.get("artifact") or ""),
            "view_hash": str(view_record.get("view_hash") or ""),
            "view_ms": view_ms,
            "apply_ms": apply_ms,
            "lint_error_count": sum(
                1 for item in lint_issues if item.get("severity") == "error"
            ),
            "lint_warning_count": sum(
                1 for item in lint_issues if item.get("severity") == "warning"
            ),
            "lint_issues": lint_issues[:12],
            "stdout_tail": str(delta)[-1200:],
            "stderr_tail": "",
        })
        print(
            f"{idx:03d} {alignment['verdict']:<15} "
            f"{alignment.get('layer') or '?':<22} "
            f"status={status or '?':<20} "
            f"daemon={str(bool(transition.get('daemon_used'))):<5} "
            f"view={view_ms:>4}ms apply={apply_ms:>5}ms "
            f"lint={steps[-1]['lint_error_count']}/{steps[-1]['lint_warning_count']} "
            f"{_display_tactic(tactic, 90)}",
            flush=True,
        )
        if not accepted:
            break

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    report = {
        "mode": "batch",
        "file": str(file),
        "lemma": args.lemma,
        "proof_lines": span.body_lines,
        "steps_requested": len(tactics),
        "elapsed_ms": elapsed_ms,
        "commit_phases": "full" if args.full_hooks else "disabled_for_fast_replay",
        "steps": steps,
        "summary": {
            "accepted_steps": sum(1 for s in steps if s.get("accepted")),
            "daemon_steps": sum(1 for s in steps if s.get("daemon_used")),
            **_alignment_summary(steps),
            "lint_errors": sum(int(s.get("lint_error_count") or 0) for s in steps),
            "lint_warnings": sum(
                int(s.get("lint_warning_count") or 0) for s in steps
            ),
            "mean_view_ms": _mean_int([int(s.get("view_ms") or 0) for s in steps]),
            "mean_apply_ms": _mean_int([int(s.get("apply_ms") or 0) for s in steps]),
        },
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    missing = int(report["summary"]["missing_view_alignments"])
    lint_errors = int(report["summary"]["lint_errors"])
    print(f"\nreport: {out_dir / 'report.json'}", flush=True)
    print(f"missing-view-alignments: {missing}/{len(steps)}", flush=True)
    print(f"text-lint-errors: {lint_errors}", flush=True)
    if missing and args.fail_on_missing:
        return 1
    if lint_errors and args.fail_on_lint:
        return 1
    return 0


def _ensure_easycrypt_import_path() -> None:
    ec_dir = _PROJECT_ROOT / "core" / "easycrypt"
    for path in (str(_PROJECT_ROOT), str(ec_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _include_values(include_args: list[str]) -> list[str]:
    out: list[str] = []
    idx = 0
    while idx < len(include_args):
        item = include_args[idx]
        if item == "-I" and idx + 1 < len(include_args):
            out.append(include_args[idx + 1])
            idx += 2
            continue
        idx += 1
    return out


def _start_extracted_lemma_session(
    *,
    session,
    file: Path,
    lemma: str,
    includes: list[str],
    extract_lemma,
    daemon_backend_cls=None,
) -> None:
    briefing = session.start()
    session.emit_event("session.started", {
        "file": str(file.resolve()),
        "lemma": lemma,
        "include_dirs": list(includes),
        "discarded_tactic_count": briefing.get("discarded_tactic_count", 0),
        "pre_restart_checkpoint_path": briefing.get(
            "pre_restart_checkpoint_path",
        ),
        "restart_count": 1,
    })
    extracted = extract_lemma(file, lemma, open_proof=True)
    safe_lemma_fname = re.sub(r"[^a-zA-Z0-9_-]", "_", lemma)
    extracted_path = session.dir / f"extracted_{safe_lemma_fname}.ec"
    extracted_path.write_text(extracted, encoding="utf-8")
    meta = {
        "file": str(file.resolve()),
        "lemma": lemma,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "restart_count": 1,
    }
    (session.dir / "session_meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )

    daemon_error = ""
    try:
        if daemon_backend_cls is None:
            try:
                from core.easycrypt.daemon_backend import DaemonBackend
            except Exception:
                from daemon_backend import DaemonBackend  # type: ignore
            daemon_backend_cls = DaemonBackend
        dbe = daemon_backend_cls(session.dir, includes)
        if dbe._sync_to(file, lemma, []):
            raw = dbe.get_goal_raw() or ""
            if raw.strip():
                session._daemon_backend = dbe
                session._write_curr_compressed(raw)
                session.prev.write_bytes(session.curr.read_bytes())
                session.emit_event("session.daemon_context_opened", {
                    "file": str(file.resolve()),
                    "lemma": lemma,
                    "include_dirs": list(includes),
                    "extracted_artifact": str(extracted_path.resolve()),
                    "mode": "daemon_open_session",
                })
                return
            daemon_error = "daemon returned an empty initial goal"
        else:
            daemon_error = str(getattr(dbe, "last_error", "") or "sync failed")
    except Exception as exc:
        daemon_error = str(exc)

    session.emit_event("session.daemon_context_open_failed", {
        "file": str(file.resolve()),
        "lemma": lemma,
        "include_dirs": list(includes),
        "extracted_artifact": str(extracted_path.resolve()),
        "error": daemon_error,
        "fallback": "subprocess_extracted_context",
    })
    session.load_context(extracted_path)
    session._run_ec(session.history, session.curr)
    session._compress_curr_inplace()
    session.prev.write_bytes(session.curr.read_bytes())


def _latest_tactic_result(events: list[dict], event_payload) -> dict:
    for event in reversed(events):
        if event.get("type") != "tactic.result":
            continue
        payload = event_payload(event)
        if isinstance(payload, dict):
            return payload
    return {}


def _lint_view(view: dict) -> list[dict]:
    if lint_prover_facing_payload is None:
        return []
    try:
        return [
            issue.to_dict()
            for issue in lint_prover_facing_payload(view, view_type="agent_view")
        ]
    except Exception as exc:
        return [{
            "severity": "warning",
            "code": "text_lint_failed",
            "message": str(exc),
            "path": "$",
        }]


def _mean_int(values: list[int]) -> int:
    clean = [value for value in values if value >= 0]
    return int(sum(clean) / len(clean)) if clean else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("roots", nargs="+")
    p_scan.add_argument("--min-lines", type=int, default=20)
    p_scan.add_argument("--limit", type=int, default=50)
    p_scan.set_defaults(func=scan)

    p_replay = sub.add_parser("replay")
    p_replay.add_argument("--file", required=True)
    p_replay.add_argument("--lemma", required=True)
    p_replay.add_argument("--max-steps", type=int, default=0)
    p_replay.add_argument("--timeout", type=int, default=120)
    p_replay.add_argument("--include", action="append", default=[])
    p_replay.add_argument("--out-dir", default="artifacts/proof_view_replay")
    p_replay.add_argument("--clean", action="store_true")
    p_replay.add_argument("--fail-on-missing", action="store_true")
    p_replay.add_argument("--fail-on-lint", action="store_true")
    p_replay.add_argument(
        "--full-hooks",
        action="store_true",
        help=(
            "In batch mode, keep stateful post-commit hook phases enabled. "
            "Default batch replay disables them for speed and relies on the "
            "next pre-step ProofContextView/ProofIR rebuild."
        ),
    )
    p_replay.add_argument(
        "--mode",
        choices=("batch", "subprocess"),
        default="batch",
        help=(
            "batch keeps one Python Session runtime alive and uses the EC "
            "daemon fast path; subprocess preserves the older CLI-per-step "
            "harness"
        ),
    )
    p_replay.set_defaults(func=replay)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
