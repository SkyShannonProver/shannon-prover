"""Run proof-view replay over a batch of lemma specs.

This is validation infrastructure only: it repeatedly invokes
``workflow.validation.proof_view_replay replay`` and writes one aggregate
summary.  Keeping it outside the prover/compiler path lets us run broad
calibration sweeps without baking project-specific logic into ProofIR.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ReplaySpec:
    project: str
    file: str
    lemma: str

    @property
    def label(self) -> str:
        return f"{self.project}:{self.lemma}" if self.project else self.lemma


_DEFAULT_EXAMPLES_ROOT = Path(
    os.environ.get(
        "EASYCRYPT_PUBLIC_EXAMPLES",
        "/private/tmp/easycrypt-public-examples/examples",
    )
)

_PRESET_ITEMS: dict[str, list[tuple[str, str, str]]] = {
    "chachapoly-hard": [
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step1"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step2_2"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step2_3"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "equ_cc"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step3"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step4_1"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "equiv_step4"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step4_bad2"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step4_bad1_lbad1"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step4_lbad1_sum"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step4_badi"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "step4_bad1"),
        ("ChaChaPoly", "ChaChaPoly/chacha_poly.ec", "pr_CCP_OCCP"),
    ],
    "mee-hard": [
        ("MEE-CBC", "MEE-CBC/RCPA_CMA.ec", "CTXT_security"),
        ("MEE-CBC", "MEE-CBC/RCPA_CMA.ec", "PTXT_security"),
        ("MEE-CBC", "MEE-CBC/CBC.eca", "Bound_by_PRP_PRF"),
        ("MEE-CBC", "MEE-CBC/MAC_then_Pad_then_CBC.eca", "CBC_security"),
        ("MEE-CBC", "MEE-CBC/CBC.eca", "CBC_upto"),
        ("MEE-CBC", "MEE-CBC/FunctionalSpec.ec", "mee_encrypt_correct"),
        ("MEE-CBC", "MEE-CBC/CBC.eca", "DQ_Sample_Compute_eq"),
        ("MEE-CBC", "MEE-CBC/CBC.eca", "Bound_by_Birthday"),
        ("MEE-CBC", "MEE-CBC/MAC_then_Pad_then_CBC.eca", "local_conclusion"),
        ("MEE-CBC", "MEE-CBC/FunctionalSpec.ec", "mee_decrypt_correct"),
    ],
}
_PRESET_ITEMS["crypto-hard"] = [
    *_PRESET_ITEMS["chachapoly-hard"],
    *_PRESET_ITEMS["mee-hard"],
]


def parse_spec_item(raw: str) -> ReplaySpec:
    """Parse ``PROJECT|FILE|LEMMA`` command-line specs."""
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != 3 or not all(parts):
        raise argparse.ArgumentTypeError(
            "spec must have the form PROJECT|FILE|LEMMA"
        )
    return ReplaySpec(project=parts[0], file=parts[1], lemma=parts[2])


def specs_for_preset(
    name: str,
    examples_root: Path = _DEFAULT_EXAMPLES_ROOT,
) -> list[ReplaySpec]:
    if name not in _PRESET_ITEMS:
        raise ValueError(f"unknown preset: {name}")
    return [
        ReplaySpec(project=project, file=str(examples_root / rel_file), lemma=lemma)
        for project, rel_file, lemma in _PRESET_ITEMS[name]
    ]


def read_spec_file(path: Path) -> list[ReplaySpec]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("spec file must contain a JSON list")
    specs: list[ReplaySpec] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"spec[{idx}] must be an object")
        project = str(item.get("project") or "").strip()
        file = str(item.get("file") or "").strip()
        lemma = str(item.get("lemma") or "").strip()
        if not file or not lemma:
            raise ValueError(f"spec[{idx}] must include file and lemma")
        specs.append(ReplaySpec(project=project, file=file, lemma=lemma))
    return specs


def run_batch(
    specs: Iterable[ReplaySpec],
    *,
    out_dir: Path,
    max_steps: int,
    timeout: int,
    mode: str,
    clean: bool,
    fail_on_missing: bool,
    fail_on_lint: bool,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for spec in specs:
        lemma_dir = out_dir / _safe_name(spec.label)
        cmd = [
            sys.executable,
            "-m",
            "workflow.validation.proof_view_replay",
            "replay",
            "--file",
            spec.file,
            "--lemma",
            spec.lemma,
            "--max-steps",
            str(max_steps),
            "--out-dir",
            str(lemma_dir),
            "--timeout",
            str(timeout),
            "--mode",
            mode,
        ]
        if clean:
            cmd.append("--clean")
        if fail_on_missing:
            cmd.append("--fail-on-missing")
        if fail_on_lint:
            cmd.append("--fail-on-lint")

        print(f"[batch] {spec.label}", flush=True)
        proc = subprocess.run(cmd, text=True, capture_output=True)
        report_path = lemma_dir / "report.json"
        report = _read_report(report_path)
        summary = _summary(report)
        row = {
            "project": spec.project,
            "file": spec.file,
            "lemma": spec.lemma,
            "returncode": proc.returncode,
            "accepted_steps": summary.get("accepted_steps"),
            "missing_view_alignments": summary.get("missing_view_alignments"),
            "missing_by_bucket": summary.get("missing_by_bucket") or {},
            "steps_by_bucket": summary.get("steps_by_bucket") or {},
            "missing_bucket_only": summary.get("missing_bucket_only"),
            "missing_absent": summary.get("missing_absent"),
            "missing_examples": (summary.get("missing_examples") or [])[:5],
            "text_lint_errors": summary.get("lint_errors"),
            "report": str(report_path),
        }
        rows.append(row)
        _print_row(row, proc)
    (out_dir / "aggregate.json").write_text(json.dumps(rows, indent=2))
    (out_dir / "suite_summary.json").write_text(
        json.dumps(summarize_rows(rows), indent=2)
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        action="append",
        type=parse_spec_item,
        default=[],
        help="Replay spec as PROJECT|FILE|LEMMA. May be repeated.",
    )
    parser.add_argument(
        "--spec-file",
        type=Path,
        help="JSON list of objects with project/file/lemma fields.",
    )
    parser.add_argument(
        "--preset",
        action="append",
        choices=sorted(_PRESET_ITEMS),
        default=[],
        help="Named replay suite. May be repeated.",
    )
    parser.add_argument(
        "--examples-root",
        type=Path,
        default=_DEFAULT_EXAMPLES_ROOT,
        help="Root for preset example paths.",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--mode", choices=["batch", "subprocess"], default="batch")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--fail-on-missing", action="store_true")
    parser.add_argument("--fail-on-lint", action="store_true")
    args = parser.parse_args(argv)

    specs = list(args.spec)
    if args.spec_file:
        specs.extend(read_spec_file(args.spec_file))
    for preset in args.preset:
        specs.extend(specs_for_preset(preset, args.examples_root))
    if not specs:
        parser.error("provide at least one --spec, --spec-file, or --preset")

    rows = run_batch(
        specs,
        out_dir=args.out_dir,
        max_steps=args.max_steps,
        timeout=args.timeout,
        mode=args.mode,
        clean=args.clean,
        fail_on_missing=args.fail_on_missing,
        fail_on_lint=args.fail_on_lint,
    )
    has_failed_child = any(int(row.get("returncode") or 0) != 0 for row in rows)
    has_missing = any(int(row.get("missing_view_alignments") or 0) for row in rows)
    has_lint = any(int(row.get("text_lint_errors") or 0) for row in rows)
    if has_failed_child or (args.fail_on_missing and has_missing) or (
        args.fail_on_lint and has_lint
    ):
        return 1
    return 0


def _read_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    if isinstance(summary, dict):
        return summary
    return report


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_bucket = _merge_bucket_counts(
        row.get("missing_by_bucket") for row in rows
    )
    steps_by_bucket = _merge_bucket_counts(row.get("steps_by_bucket") for row in rows)
    top_missing = sorted(
        [
            {
                "project": row.get("project"),
                "lemma": row.get("lemma"),
                "missing": int(row.get("missing_view_alignments") or 0),
                "accepted": int(row.get("accepted_steps") or 0),
                "missing_by_bucket": row.get("missing_by_bucket") or {},
                "report": row.get("report"),
            }
            for row in rows
        ],
        key=lambda item: (int(item["missing"]), int(item["accepted"])),
        reverse=True,
    )
    return {
        "lemma_count": len(rows),
        "accepted_steps": sum(int(row.get("accepted_steps") or 0) for row in rows),
        "missing_view_alignments": sum(
            int(row.get("missing_view_alignments") or 0) for row in rows
        ),
        "text_lint_errors": sum(int(row.get("text_lint_errors") or 0) for row in rows),
        "missing_bucket_only": sum(
            int(row.get("missing_bucket_only") or 0) for row in rows
        ),
        "missing_absent": sum(int(row.get("missing_absent") or 0) for row in rows),
        "steps_by_bucket": steps_by_bucket,
        "missing_by_bucket": missing_by_bucket,
        "top_missing": top_missing[:12],
    }


def _merge_bucket_counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        for bucket, count in value.items():
            try:
                n = int(count)
            except (TypeError, ValueError):
                continue
            counts[str(bucket)] = counts.get(str(bucket), 0) + n
    return {bucket: counts[bucket] for bucket in sorted(counts) if counts[bucket]}


def _print_row(row: dict[str, Any], proc: subprocess.CompletedProcess[str]) -> None:
    buckets = _format_bucket_counts(row.get("missing_by_bucket") or {})
    summary = (
        f"  accepted={row.get('accepted_steps')} "
        f"missing={row.get('missing_view_alignments')} "
        f"buckets={buckets or '-'} "
        f"lint={row.get('text_lint_errors')} "
        f"rc={row.get('returncode')}"
    )
    print(summary, flush=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").splitlines()[-5:]
        for line in tail:
            print(f"  ! {line}", flush=True)


def _safe_name(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label)


def _format_bucket_counts(counts: dict[str, Any]) -> str:
    parts: list[str] = []
    for bucket in sorted(counts):
        try:
            count = int(counts[bucket])
        except (TypeError, ValueError):
            continue
        if count:
            parts.append(f"{bucket}:{count}")
    return ",".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
