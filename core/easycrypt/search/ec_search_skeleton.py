"""ec_search_skeleton: wrap EasyCrypt's native `search` AST query.

Unlike our `-search` (regex grep on source files), EC's native `search`
matches at the AST/operator level:

    search take size.            → lemmas mentioning BOTH `take` and `size`
    search (_ \\in take _ _).     → lemmas matching the term skeleton

Use this when:
  - You want lemmas relating two or more operators (operator-AND).
  - You want lemmas whose statement matches a specific term shape.

Don't use for:
  - Finding a specific named lemma (use `-where`).
  - Finding modules / theory declarations (use `-where`).
  - Regex on source text (use `-search`).
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


_ANCHOR_NAME = '__ec_skeleton_anchor_zXyQ__'


def _build_probe(context_file: Path, query: str) -> Path:
    """Build a probe file: truncated context + bracket the search output
    with anchor `print` calls so we can isolate it from compile noise."""
    src = context_file.read_text(encoding='utf-8', errors='replace')
    probe_path = Path(f'/tmp/ec_skeleton_probe_{os.getpid()}_'
                      f'{abs(hash(query))}.ec')
    body = src + '\n'
    body += f'print {_ANCHOR_NAME}.\n'
    body += f'search {query}.\n'
    body += f'print {_ANCHOR_NAME}.\n'
    probe_path.write_text(body, encoding='utf-8')
    return probe_path


def _strip_emacs_prefix(text: str) -> str:
    """Strip emacs-mode line prefix ('| ', '+ ', etc.) from each line."""
    out_lines = []
    for ln in text.splitlines():
        # emacs mode prefixes most lines with '| ' or '+ '
        if ln.startswith('| ') or ln.startswith('+ '):
            out_lines.append(ln[2:])
        elif ln in ('|', '+'):
            out_lines.append('')
        else:
            out_lines.append(ln)
    return '\n'.join(out_lines)


def _parse_lemmas(block: str) -> list[dict]:
    """Parse a block of EC search output into structured lemma entries.

    Output is a sequence of `lemma NAME [...]: body.` entries separated
    by line-starts of `lemma`/`axiom`/`(* alias *)`. Indentation marks
    body continuation.
    """
    block = _strip_emacs_prefix(block)
    # Drop EC prompt lines like `[543|check]>` that get embedded
    block = re.sub(r'^\[\d+\|[^\]]+\]>.*$', '', block, flags=re.MULTILINE)

    # Split on entry-start lines: lines that begin (no leading space) with
    # `lemma`, `local lemma`, `axiom`, or a `(* X *)` alias comment.
    start_re = re.compile(
        r'^(?:\(\*\s*[\w\.]+\s*\*\)\s*\n)?(?:local\s+)?(?:lemma|axiom)\s+\w+',
        re.MULTILINE,
    )
    starts = [m.start() for m in start_re.finditer(block)]
    if not starts:
        return []
    starts.append(len(block))

    parsed = []
    for i in range(len(starts) - 1):
        ent = block[starts[i]:starts[i+1]].strip()
        m = re.search(r'\b(?:local\s+)?(?:lemma|axiom)\s+(\w+)\b', ent)
        if m and ent:
            parsed.append({'name': m.group(1), 'body': ent})
    return parsed


def search_skeleton(query: str,
                    context_file: Path,
                    include_dirs: list[Path],
                    timeout: int = 60,
                    max_results: int = 30) -> str:
    """Run EC native `search QUERY.` against the loaded context.

    Returns a formatted string with the matching lemmas.
    """
    if not query or not query.strip():
        return ("[SKELETON-ERROR] empty query. Pass operator names "
                "(e.g. `take size`) or a term skeleton in parens "
                "(e.g. `(_ \\in take _ _)`).\n")
    if context_file is None or not context_file.exists():
        return f"[SKELETON-ERROR] no context file\n"

    probe = _build_probe(context_file, query)
    args = ['easycrypt', 'cli', '-emacs']
    for d in include_dirs:
        args.extend(['-I', str(d)])
    # Build env with opam switch (same trick as ec_where)
    import os as _os
    env = dict(_os.environ)
    try:
        from core.easycrypt.ec_env import get_ec_env  # type: ignore
        env.update(get_ec_env())
    except Exception:
        pass
    try:
        with probe.open('rb') as fh:
            r = subprocess.run(args, stdin=fh, capture_output=True,
                               text=True, timeout=timeout, env=env)
        out = r.stdout
        err = r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        try:
            probe.unlink()
        except OSError:
            pass
        return f"[SKELETON-ERROR] EC failed: {e}\n"
    finally:
        try:
            probe.unlink()
        except OSError:
            pass

    # Find the anchor pair: "no such object in any category" appears at each
    # anchor. The output between the two anchor occurrences is the search
    # result.
    nso_re = re.compile(r'^\s*\|?\s*no such object in any category\s*$',
                        re.MULTILINE)
    nso_matches = list(nso_re.finditer(out))
    if len(nso_matches) < 2:
        return (f"[SKELETON-ERROR] could not locate anchors in EC output. "
                f"Query may have a parse error. Got {len(nso_matches)} anchors.\n"
                f"Last 200 chars: ...{out[-200:]}")

    # Take the LAST two anchors (most recent search) for the bracket
    anchor_start = nso_matches[-2].end()
    anchor_end = nso_matches[-1].start()
    block = out[anchor_start:anchor_end]

    parsed = _parse_lemmas(block)
    if not parsed:
        # Surface EC-specific errors from stderr if any
        ec_diag = ''
        for line in (err or '').splitlines():
            line = line.strip()
            if not line or line.startswith('[NOTE]'):
                continue
            for sig in ('unknown operator', 'more than one operator',
                        'parse error', 'unknown symbol',
                        'invalid mixfix', 'cannot find'):
                if sig in line:
                    ec_diag += f'  EC: {line.strip(chr(13))}\n'
                    break
        if ec_diag:
            return (f"[SKELETON-EC-ERROR] `search {query}` failed in EC:\n"
                    f"{ec_diag}"
                    f"Hint: if 'more than one operator' — operator is "
                    f"overloaded; disambiguate with type annotation "
                    f"`(x:T) ^ (y:U)` or qualified name "
                    f"`Module.( ^ )`. If 'unknown operator' — name not "
                    f"in scope of the loaded context.\n")
        return (f"[SKELETON-NO-MATCH] `search {query}` returned no lemmas in "
                f"the loaded context.\n"
                f"Hint: arguments must be operator names (e.g. `take`, `size`) "
                f"or term skeletons in parens (e.g. `(_ \\in take _ _)`). "
                f"Lemma names like `take_nth` won't match — `search` indexes "
                f"by what's INSIDE lemma statements, not lemma names.\n")

    lines = [f"[SKELETON-HITS] `search {query}` -> {len(parsed)} lemma(s)"]
    if len(parsed) > 25:
        # A bare common operator (e.g. `(+^)`) matches the whole theory; tell the agent how to
        # focus instead of wading the dump (live PIR playground: `search (+^)` -> 91 lemmas).
        lines.append(
            "  (broad result — to get the applicable lemma on top, search a TERM SKELETON of "
            "the sub-term you are rewriting, e.g. `(big _ _ (_ :: _))` or `(_ ++ _)`, not the "
            "bare operator)"
        )
    if len(parsed) > max_results:
        lines.append(f"  (showing first {max_results}; pass --max for more)")
        parsed = parsed[:max_results]
    lines.append('')
    for p in parsed:
        lines.append(p['body'])
        lines.append('')
    return '\n'.join(lines) + '\n'


def main():
    """CLI: ec_search_skeleton.py 'QUERY' -f context.ec -I dir1 -I dir2"""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('query')
    ap.add_argument('-f', '--file', dest='context', required=True)
    ap.add_argument('-I', dest='includes', action='append', default=[])
    ap.add_argument('--max', type=int, default=30, dest='max_results')
    args = ap.parse_args()
    print(search_skeleton(args.query, Path(args.context),
                          [Path(d) for d in args.includes],
                          max_results=args.max_results))


if __name__ == '__main__':
    main()
