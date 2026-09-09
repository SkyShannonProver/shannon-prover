#!/usr/bin/env python3
"""Assemble the same public website for local preview and GitHub Pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from build_manifest import build, write_timeline_scripts
from proof_library import package_library


ROOT = Path(__file__).resolve().parents[1]


def assemble(source: Path, destination: Path, *, local_preview: bool = False,
             case_studies: Path | None = None) -> dict:
    source = source.resolve()
    destination = destination.resolve()
    if (source / "RELEASING.md").exists() and not local_preview:
        raise ValueError("Build from the public export, not the private checkout.")
    if case_studies is not None and not local_preview:
        raise ValueError("Unreviewed proof libraries require --local-preview.")
    if case_studies is None:
        case_studies = source / "bundle_browser/case_studies"
        catalog = json.loads((case_studies / "catalog.json").read_text(encoding="utf-8"))
        if catalog.get("publication_status") != "reviewed" or catalog.get("local_review_only"):
            raise ValueError("Default case studies must be explicitly reviewed for publication.")
    if destination == source or destination in source.parents:
        raise ValueError("Output must not replace the source or its parent.")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Choose a new or empty output directory.")

    data = build(str(source), public_only=True)
    if not data["bundles"]:
        raise ValueError("No public benchmark bundles found.")
    copies = [
        (source / "website/index.html", Path("index.html")),
        (source / "bundle_browser/index.html", Path("results/index.html")),
        (source / "bundle_browser/proof_browser.js", Path("results/proof_browser.js")),
        (source / "bundle_browser/proof_browser.css", Path("results/proof_browser.css")),
    ]
    runs = source / "agent_view_runs"
    for record in data["bundles"]:
        relative = Path(record["dir"])
        bundle = runs / relative
        if relative.is_absolute() or ".." in relative.parts or bundle.is_symlink():
            raise ValueError(f"Invalid bundle path: {relative}")
        timeline = bundle / "timeline_report.json"
        if not timeline.is_file():
            raise ValueError(f"Missing benchmark timeline: {relative}")
        json.loads(timeline.read_text(encoding="utf-8"))
        for path in sorted(bundle.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Symlinks are not public site inputs: {path}")
            if path.is_file():
                copies.append((path, Path("agent_view_runs") / path.relative_to(runs)))

    for path, _ in copies:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or invalid site input: {path}")
    cases = package_library(case_studies, destination / "results/case_studies")
    for path, relative in copies:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    manifest = json.dumps(data, ensure_ascii=True, indent=2) + "\n"
    (destination / "results/manifest.json").write_text(manifest, encoding="utf-8")
    (destination / "results/manifest.js").write_text(
        "window.SHANNON_MANIFEST = " + manifest.rstrip() + ";\n",
        encoding="utf-8",
    )
    # Generate sidecars in the output only; captured source bundles are immutable.
    timelines = write_timeline_scripts(str(destination), data)
    if timelines != data["count"]:
        raise ValueError("Not all benchmark timelines could be packaged.")
    (destination / ".nojekyll").touch()
    return {"site": str(destination), "bundles": data["count"], "timelines": timelines,
            "case_studies": cases, "local_preview": local_preview}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new or empty site directory")
    parser.add_argument("--local-preview", action="store_true",
                        help="explicit local-only build from the private checkout; never deploy this output")
    parser.add_argument("--case-studies", type=Path,
                        help="override the reviewed catalog for local preview only; requires --local-preview")
    args = parser.parse_args()
    try:
        result = assemble(ROOT, args.out, local_preview=args.local_preview,
                          case_studies=args.case_studies)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Site build failed: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
