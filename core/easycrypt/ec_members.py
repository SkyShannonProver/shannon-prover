"""ec_members: list top-level members of a theory / clone instance.

Wraps EC's `print theory SCOPE.` and parses the output to surface just
the declaration NAMES (per kind), without dumping every body.

Why not just `print theory T.`: EC's raw output is enormous (6000+ lines
for a typical clone instance). Agent context overflows. We need an outline,
not a dump.

Why not source-text grep: clones inline external members under their alias,
and `print theory` is the authoritative AST view (catches `clone include`
expansions that source-grep would miss).

Output:
  [MEMBERS] SplitC2 (theory) — 28 members
    ops:      topair, ofpair
    lemmas:   topairK, sample_spec, pr_RO_split, ll_RO_split
    theories: I1, I2
    modules:  RO_Pair, MainD, ROF, RO_DOM
    types:    (none)
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


_ANCHOR_NAME = '__ec_members_anchor_zXyQ__'

# Pattern: a line that LOOKS LIKE a top-level declaration in `print theory`
# output. EC prefixes imported decls with `(* import *)`; local decls have
# the `local` modifier. Both forms get caught.
_DECL_RE = re.compile(
    r'^(?:\s*\(\*\s*import\s*\*\)\s*)?\s*(?:local\s+)?'
    r'(module(?:\s+type)?|theory|op|pred|abbrev|lemma|axiom|type)\s+'
    r'(\w+)',
    re.MULTILINE,
)


def _ec_env() -> dict:
    """Return os.environ + opam switch env."""
    env = dict(os.environ)
    try:
        from core.easycrypt.ec_env import get_ec_env  # type: ignore
        env.update(get_ec_env())
    except Exception:
        pass
    return env


def _build_probe(context_file: Path, scope: str) -> Path:
    """Build a probe file: full context + bracketed `print theory SCOPE.`."""
    src = context_file.read_text(encoding='utf-8', errors='replace')
    probe_path = Path(f'/tmp/ec_members_probe_{os.getpid()}_'
                      f'{abs(hash(scope))}.ec')
    body = src + '\n'
    # If we're in a proof context, abort first. (Best-effort; if not in
    # proof mode, EC will emit "cannot process [abort] outside a proof
    # script" warning but continue.)
    body += 'abort.\n'
    body += f'print {_ANCHOR_NAME}.\n'
    body += f'print theory {scope}.\n'
    body += f'print {_ANCHOR_NAME}.\n'
    probe_path.write_text(body, encoding='utf-8')
    return probe_path


def _parse_decls(block: str) -> dict[str, list[str]]:
    """Extract declaration names per kind from a `print theory` block.

    Returns dict like {'op': ['topair', 'ofpair'], 'lemma': [...], ...}
    """
    by_kind: dict[str, list[str]] = {}
    seen: set[tuple[str, str]] = set()
    for m in _DECL_RE.finditer(block):
        kind = m.group(1)
        # normalize 'module type' -> 'module_type'
        kind = kind.replace(' ', '_').replace('module_type', 'module type')
        name = m.group(2)
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)
        by_kind.setdefault(kind, []).append(name)
    return by_kind


def members(scope: str,
            context_file: Path | None,
            include_dirs: list[Path],
            timeout: int = 60) -> dict:
    """Return top-level members of a theory/clone scope.

    Args:
        scope: name of the theory or clone instance (e.g. `SplitC2`,
            `SplitD`, `Poly`).
        context_file: the .ec file loaded as session context.
        include_dirs: -I dirs.
        timeout: subprocess timeout.

    Returns:
        {
          'scope': str,
          'status': 'ok' | 'miss' | 'error',
          'by_kind': {'op': [...], 'lemma': [...], ...},
          'total': int,
          'note': str,
        }
    """
    if not scope or not scope.strip():
        return {'scope': scope, 'status': 'error', 'by_kind': {},
                'total': 0, 'note': 'empty scope'}
    if not re.match(r'^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)*$', scope.strip()):
        return {'scope': scope, 'status': 'error', 'by_kind': {},
                'total': 0,
                'note': f'invalid identifier: {scope!r}'}
    if context_file is None or not context_file.exists():
        return {'scope': scope, 'status': 'error', 'by_kind': {},
                'total': 0, 'note': 'no context file'}

    probe = _build_probe(context_file, scope)
    args = ['easycrypt', 'cli', '-emacs']
    for d in include_dirs:
        args.extend(['-I', str(d)])
    try:
        with probe.open('rb') as fh:
            r = subprocess.run(args, stdin=fh, capture_output=True,
                               text=True, timeout=timeout, env=_ec_env())
        out = r.stdout
    except FileNotFoundError as e:
        return {'scope': scope, 'status': 'error', 'by_kind': {},
                'total': 0, 'note': f'easycrypt not in PATH: {e}'}
    except subprocess.TimeoutExpired:
        return {'scope': scope, 'status': 'error', 'by_kind': {},
                'total': 0, 'note': f'EC timed out after {timeout}s'}
    finally:
        try:
            probe.unlink()
        except OSError:
            pass

    # Find content between the two `no such object` anchors
    nso_re = re.compile(r'^\s*\|?\s*no such object in any category\s*$',
                        re.MULTILINE)
    matches = list(nso_re.finditer(out))
    if len(matches) < 2:
        # Could be a miss (scope doesn't resolve to a theory)
        # Look for "unknown theory" or similar in output
        if 'unknown' in out.lower() or 'cannot' in out.lower():
            return {'scope': scope, 'status': 'miss', 'by_kind': {},
                    'total': 0, 'note': 'scope not found as theory'}
        return {'scope': scope, 'status': 'error', 'by_kind': {},
                'total': 0,
                'note': f'could not locate anchors in EC output ({len(matches)} found)'}

    block_start = matches[-2].end()
    block_end = matches[-1].start()
    block = out[block_start:block_end]

    # Strip emacs prefixes (`| `, `+ `)
    cleaned_lines = []
    for ln in block.splitlines():
        if ln.startswith('| ') or ln.startswith('+ '):
            cleaned_lines.append(ln[2:])
        elif ln in ('|', '+'):
            cleaned_lines.append('')
        else:
            cleaned_lines.append(ln)
    cleaned = '\n'.join(cleaned_lines)

    # Did we even get a theory body? Look for `theory NAME.` near the start
    if not re.search(rf'\b(?:local\s+)?theory\s+{re.escape(scope.split(".")[-1])}\b', cleaned):
        return {'scope': scope, 'status': 'miss', 'by_kind': {},
                'total': 0,
                'note': f'`{scope}` is not a theory (or not in scope as one). '
                        f'Try `-where {scope}` for module/op/lemma resolution.'}

    by_kind = _parse_decls(cleaned)
    # Skip the outer scope name itself if it appears (it always does as the
    # `theory SCOPE.` opener)
    base = scope.split('.')[-1]
    if 'theory' in by_kind:
        by_kind['theory'] = [n for n in by_kind['theory'] if n != base]
        if not by_kind['theory']:
            del by_kind['theory']

    total = sum(len(v) for v in by_kind.values())
    return {
        'scope': scope, 'status': 'ok', 'by_kind': by_kind,
        'total': total, 'note': '',
    }


def format_members(result: dict, max_per_kind: int = 30) -> str:
    """Format members result for the agent."""
    scope = result['scope']
    status = result['status']
    if status == 'error':
        return f"[MEMBERS-ERROR] {scope}: {result['note']}\n"
    if status == 'miss':
        return f"[MEMBERS-MISS] {scope}: {result['note']}\n"
    by_kind = result['by_kind']
    total = result['total']
    if not by_kind:
        return (f"[MEMBERS] {scope} (theory) — empty (or only contains "
                f"renamed clone artifacts not visible at AST level)\n")
    lines = [f"[MEMBERS] {scope} (theory) — {total} top-level entries"]
    # Stable order
    kind_order = ['module type', 'module', 'theory', 'type',
                  'op', 'pred', 'abbrev', 'lemma', 'axiom']
    for kind in kind_order:
        names = by_kind.get(kind)
        if not names:
            continue
        if len(names) > max_per_kind:
            shown = ', '.join(names[:max_per_kind])
            lines.append(f"  {kind:11}: {shown}, ... [+{len(names)-max_per_kind} more]")
        else:
            lines.append(f"  {kind:11}: {', '.join(names)}")
    lines.append('')
    lines.append(f"  → For body of any name, run `-where {scope}.NAME` "
                 f"(or just `-where NAME` if it's accessible at top level "
                 f"after import).")
    return '\n'.join(lines) + '\n'


def main():
    """CLI: ec_members.py SCOPE -f context.ec -I dir1 -I dir2"""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('scope')
    ap.add_argument('-f', '--file', dest='context', required=True)
    ap.add_argument('-I', dest='includes', action='append', default=[])
    args = ap.parse_args()
    res = members(args.scope, Path(args.context),
                  [Path(d) for d in args.includes])
    print(format_members(res))


if __name__ == '__main__':
    main()
