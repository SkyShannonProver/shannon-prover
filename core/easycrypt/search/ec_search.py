#!/usr/bin/env python3
"""Search EasyCrypt theories for lemma names and analyze clone renamings.

Mini tools for session_cli:
  -search QUERY   Search for lemma/axiom/op names in EC theories and loaded context
  -clones         List all clone declarations and their lemma renamings

These replace the agent's manual grepping through easycrypt-src/theories/.
"""
from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Lemma form classification helpers
# ---------------------------------------------------------------------------

def _extract_full_decl(text: str, decl_start: int, max_chars: int = 600) -> str:
    """Extract the full declaration text up to (but not including) the trailing period."""
    chunk = text[decl_start:decl_start + max_chars]
    depth = 0
    i = 0
    while i < len(chunk):
        c = chunk[i]
        # Skip EC block comments (* ... *)
        if c == '(' and i + 1 < len(chunk) and chunk[i + 1] == '*':
            j = chunk.find('*)', i + 2)
            if j != -1:
                i = j + 2
                continue
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == '.' and depth == 0:
            next_c = chunk[i + 1] if i + 1 < len(chunk) else '\n'
            if next_c in ' \n\t\r':
                return chunk[:i].strip()
        i += 1
    return chunk.strip()


def _occurs_at_depth0(text: str, target: str) -> bool:
    """Return True if *target* appears at brace/paren depth 0 in *text*."""
    depth = 0
    n = len(target)
    for i in range(len(text)):
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif depth == 0 and text[i:i + n] == target:
            return True
    return False


def _occurs_impl_at_depth0(text: str) -> bool:
    """Return True if '=>' appears at depth 0 but is NOT part of '<='."""
    depth = 0
    n = len(text)
    for i in range(n):
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif depth == 0 and c == '=' and i + 1 < n and text[i + 1] == '>':
            if i == 0 or text[i - 1] != '<':
                return True
    return False


def _occurs_eq_at_depth0(text: str) -> bool:
    """Return True if a standalone '=' appears at depth 0 (not <=, >=, =>, <=>)."""
    depth = 0
    n = len(text)
    for i in range(n):
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif depth == 0 and c == '=':
            prev_c = text[i - 1] if i > 0 else ''
            next_c = text[i + 1] if i + 1 < n else ''
            if prev_c not in '<>!' and next_c != '>':
                return True
    return False


def _classify_decl(full_decl: str, kind: str) -> tuple[str, str, str]:
    """Classify a declaration by its logical form.

    Returns (tag, annotation, body_preview) where:
      tag         — one of '[EQ]', '[IFF]', '[IMPL]', '[PRED]', or ''
      annotation  — human-readable usage note
      body_preview — the statement body (after ':'), truncated

    Classification rules:
      [EQ]   — unconditional equation (A = B) — suitable for ``rewrite``
      [IFF]  — biconditional (A <=> B) — suitable for ``rewrite`` / ``iff``
      [IMPL] — conditional implication (hyp => concl) — NOT for ``rewrite``,
               use as ``have`` / ``apply``
      [PRED] — predicate / property — use with ``apply`` / ``exact``
    """
    if kind in ('op', 'type', 'clone', 'abbrev'):
        return '', '', ''

    # Find the last ':' at depth 0 — that separates params from statement
    depth = 0
    last_colon = -1
    for i, c in enumerate(full_decl):
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ':' and depth == 0:
            # Skip '::' (list cons / type ascription with two colons)
            if i + 1 < len(full_decl) and full_decl[i + 1] == ':':
                continue
            last_colon = i

    if last_colon == -1:
        return '', '', ''

    body = full_decl[last_colon + 1:].strip()
    if not body:
        return '', '', ''

    # Normalise whitespace for a compact preview
    body_single = ' '.join(body.split())

    # Build a truncated preview (≤100 chars)
    preview = body_single if len(body_single) <= 100 else body_single[:97] + '...'

    # Classify: check <=> before => to avoid false positives
    if _occurs_at_depth0(body_single, '<=>'):
        return '[IFF]', 'biconditional — suitable for: rewrite / iff', preview

    if _occurs_impl_at_depth0(body_single):
        return '[IMPL]', 'conditional implication — NOT suitable for: rewrite  (use: have/apply)', preview

    if _occurs_eq_at_depth0(body_single):
        return '[EQ]', 'unconditional equation — suitable for: rewrite', preview

    return '[PRED]', 'predicate/property — use with: apply/exact', preview


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _extract_clones_from_file(path: Path) -> list[tuple[str, str]]:
    """Return (source_theory, alias) pairs from clone declarations in *path*."""
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeDecodeError):
        return []
    pat = re.compile(r'^\s*clone\s+(?:import\s+|include\s+)?(\S+)\s+as\s+(\w+)', re.MULTILINE)
    return [(m.group(1), m.group(2)) for m in pat.finditer(text)]


def _extract_in_scope_stems(context_file: Path,
                            search_dirs: list[Path]) -> set[str]:
    """Extract lowercase theory file stems that are in scope for the context file.

    Parses ``require import``, ``require (*--*)``, ``clone ... as``, and
    ``import X.Y.Z`` declarations.  Also follows one level of transitive
    requires: for each directly-required theory, parse *its* ``require``
    lines from the search dirs.
    """
    try:
        text = context_file.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeDecodeError):
        return set()

    stems: set[str] = set()

    # The context file itself is always in scope
    stems.add(context_file.stem.lower())
    # Also add the original source file stem if this is an extracted file
    # (e.g., "extracted_PIR_s_uniform" → also add "pir")
    ctx_stem = context_file.stem.lower()
    if ctx_stem.startswith('extracted_'):
        # Try to recover the original file name from the extracted stem
        # extracted_<lemma_name>.ec — the original file is in include dirs
        pass
    # Also add stems from include dirs (files loaded with -I are in scope)
    for d in search_dirs:
        if d.is_dir():
            for f in d.iterdir():
                if f.suffix in ('.ec', '.eca'):
                    stems.add(f.stem.lower())

    # require import X Y Z.  /  require (*--*) X Y Z.
    req_pat = re.compile(
        r'^\s*require\s+(?:import\s+|(?:\(\*.*?\*\)\s*))?'
        r'([\w\s]+)\.',
        re.MULTILINE,
    )
    for m in req_pat.finditer(text):
        for tok in m.group(1).split():
            if tok and tok[0].isupper():
                stems.add(tok.lower())

    # clone X as Y  →  add X's stem
    for source_theory, _alias in _extract_clones_from_file(context_file):
        stem = Path(source_theory).stem
        # handle dotted paths like DH.GP.ZModE.ZModpField
        for part in stem.split('.'):
            stems.add(part.lower())

    # import X.Y.Z  →  add root stems
    imp_pat = re.compile(r'^\s*import\s+([\w.\s]+)\.', re.MULTILINE)
    for m in imp_pat.finditer(text):
        for tok in m.group(1).split():
            for part in tok.split('.'):
                if part and part[0].isupper():
                    stems.add(part.lower())

    # One-level transitive: for each direct stem, find its file and parse
    # its require lines (non-recursive).
    all_ec_files: dict[str, Path] = {}
    for d in search_dirs:
        if d.is_dir():
            for f in d.rglob('*.ec'):
                all_ec_files[f.stem.lower()] = f
            for f in d.rglob('*.eca'):
                all_ec_files[f.stem.lower()] = f

    transitive: set[str] = set()
    for s in list(stems):
        dep_file = all_ec_files.get(s)
        if dep_file:
            try:
                dep_text = dep_file.read_text(encoding='utf-8', errors='replace')
            except (OSError, UnicodeDecodeError):
                continue
            for m in req_pat.finditer(dep_text):
                for tok in m.group(1).split():
                    if tok and tok[0].isupper():
                        transitive.add(tok.lower())

    stems |= transitive
    return stems


def search_lemmas(query: str, search_dirs: list[Path],
                  context_file: Path | None = None,
                  max_results: int = 30) -> str:
    """Search for lemma/axiom/op declarations matching a query pattern.

    Searches through .ec/.eca files in the given directories and optionally
    in the loaded context file.

    Args:
        query: regex pattern to match against declaration names
        search_dirs: list of directories to search (e.g., easycrypt-src/theories/)
        context_file: optional .ec file loaded as session context
        max_results: maximum number of results to return

    Returns:
        formatted search results
    """
    # Compile search pattern
    try:
        pat = re.compile(query, re.IGNORECASE)
    except re.error:
        return f"Invalid regex pattern: {query}\n"

    # Pattern for declarations: lemma/axiom/op/pred/type/equiv/hoare at start of line.
    # `local` prefix optional for local equiv/hoare helper declarations.
    decl_pat = re.compile(
        r'^\s*(?:local\s+)?(lemma|axiom|op|pred|type|clone|abbrev|equiv|hoare)\s+'
        r'(?:\[.*?\]\s+)?'  # optional type params like ['a]
        r'(\w+)',
        re.MULTILINE
    )

    # results: (rel_path, name, kind, line_no, first_line, tag, annotation, body_preview)
    results: list[tuple] = []
    # Deduplicate: track (name, kind) pairs to avoid showing the same lemma
    # from both the original source file and the extracted session file.
    seen_decls: set[tuple[str, str]] = set()

    # Collect files to search — put extracted/session files last so the
    # original source file wins deduplication.
    files: list[Path] = []
    for d in search_dirs:
        if d.is_dir():
            files.extend(d.rglob('*.ec'))
            files.extend(d.rglob('*.eca'))

    if context_file and context_file.exists():
        files.append(context_file)

    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='replace')
        except (OSError, UnicodeDecodeError):
            continue

        for m in decl_pat.finditer(text):
            kind = m.group(1)
            name = m.group(2)
            if pat.search(name):
                # Deduplicate across files: skip if we already have this
                # (name, kind, line_content) from another file (e.g.,
                # original source vs extracted session file).
                # Same name in the SAME file at different lines is kept
                # (e.g., expM for int vs exp types in Group.ec).
                kw_start = m.start(1)  # start of the keyword, not ^\s*
                line_start_tmp = text.rfind('\n', 0, kw_start) + 1
                line_end_tmp = text.find('\n', kw_start)
                if line_end_tmp == -1:
                    line_end_tmp = len(text)
                decl_line = text[line_start_tmp:line_end_tmp].strip()
                dedup_key = (name, kind, decl_line)
                if dedup_key in seen_decls:
                    continue
                seen_decls.add(dedup_key)

                line_no = text[:m.start()].count('\n') + 1
                # Get the first line for the header display
                line_start = text.rfind('\n', 0, m.start()) + 1
                line_end = text.find('\n', m.start())
                if line_end == -1:
                    line_end = len(text)
                first_line = text[line_start:line_end].strip()
                if len(first_line) > 100:
                    first_line = first_line[:97] + '...'

                # Extract full declaration and classify its logical form
                full_decl = _extract_full_decl(text, m.start())
                tag, annotation, body_preview = _classify_decl(full_decl, kind)

                rel_path = str(f)
                # Make path relative if possible
                for d in search_dirs:
                    try:
                        rel_path = str(f.relative_to(d.parent))
                    except ValueError:
                        pass

                results.append((rel_path, name, kind, line_no,
                                 first_line, tag, annotation, body_preview))

                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    if not results:
        return f"No matches for '{query}' in {len(files)} files.\n"

    # Build clone map: theory_stem -> list of alias names (from context file)
    clone_map: dict[str, list[str]] = {}
    if context_file and context_file.exists():
        for source_theory, alias in _extract_clones_from_file(context_file):
            # Normalise: strip leading path components and .ec suffix
            stem = Path(source_theory).stem.lower()
            clone_map.setdefault(stem, []).append(alias)

    # Scope-aware ranking: sort in-scope results first
    in_scope_stems: set[str] = set()
    if context_file and context_file.exists():
        in_scope_stems = _extract_in_scope_stems(context_file, search_dirs)

    def _is_in_scope(rel_path: str) -> bool:
        return Path(rel_path).stem.lower() in in_scope_stems

    if in_scope_stems:
        # Stable sort: in-scope first, preserving relative order within groups
        results.sort(key=lambda r: (0 if _is_in_scope(r[0]) else 1))

    in_scope_count = sum(1 for r in results if _is_in_scope(r[0]))
    lines = [f"=== Search results for '{query}' ({len(results)} matches"
             f"{f', {in_scope_count} in scope' if in_scope_stems else ''}) ===\n"]
    for rel_path, name, kind, line_no, first_line, tag, annotation, body_preview in results:
        scope_tag = " [IN SCOPE]" if _is_in_scope(rel_path) else ""
        lines.append(f"  {kind:6s} {name:30s}  {rel_path}:{line_no}{scope_tag}")
        if tag and annotation:
            # Pad tag to fixed width for alignment
            lines.append(f"    {tag:6s} {annotation}")
            if body_preview:
                lines.append(f"           {body_preview}")
        else:
            lines.append(f"           {first_line}")
        # Annotate if this lemma comes from a theory cloned in the context file
        result_stem = Path(rel_path).stem.lower()
        if result_stem in clone_map:
            for alias in clone_map[result_stem]:
                lines.append(f"    [CLONE] use as {alias}.{name}  "
                              f"(cloned in {context_file.name} via clone ... as {alias})")
    if len(results) >= max_results:
        lines.append(f"\n  (truncated at {max_results} results)")
    lines.append("")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Signature lookup (exact-name, returns full declaration)
# ---------------------------------------------------------------------------

def lookup_lemma_signature(name: str,
                           search_dirs: list[Path],
                           context_file: Path | None = None,
                           max_matches: int = 3) -> str:
    """Return the exact declaration text for `name` (lemma/axiom/op/pred).

    Unlike `search_lemmas` (regex, many kinds of output), this is targeted at
    the "before you `apply LEMMA`, read its signature" workflow:
      - Matches `name` exactly (no regex; no substring)
      - Scans the context file FIRST (most likely to be in scope), then dirs
      - Extracts the full multi-line declaration up to the terminating `.`
      - Tags each match with its source file and line
      - Deduplicates (name, kind, full_decl) across sources

    Returns a compact, apply-ready report. When no match found, returns a
    short message suggesting `-search` as a broader query.
    """
    # Build file list: context first (in-scope wins), then other dirs
    files: list[Path] = []
    if context_file and context_file.exists():
        files.append(context_file)
    for d in search_dirs:
        if d.is_dir():
            files.extend(d.rglob('*.ec'))
            files.extend(d.rglob('*.eca'))

    decl_pat = re.compile(
        # Recognise `equiv` / `hoare` too.  Local equivalence helpers often
        # carry explicit universal parameters; hiding their signatures makes
        # agents guess bare `call NAME.` forms that EC cannot instantiate.
        r'^\s*(?:local\s+)?(lemma|axiom|op|pred|abbrev|equiv|hoare)\s+'
        r'(?:\[.*?\]\s+)?'          # optional type params ['a]
        r'(\w+)\b',
        re.MULTILINE,
    )

    seen: set[tuple[str, str]] = set()
    matches: list[tuple[str, str, int, str]] = []   # (file, kind, line_no, full_decl)

    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='replace')
        except (OSError, UnicodeDecodeError):
            continue
        for m in decl_pat.finditer(text):
            if m.group(2) != name:
                continue
            kind = m.group(1)
            full_decl = _extract_full_decl(text, m.start(), max_chars=1200)
            key = (kind, full_decl.strip()[:400])
            if key in seen:
                continue
            seen.add(key)
            line_no = text[:m.start()].count('\n') + 1
            rel_path = str(f)
            for d in search_dirs:
                try:
                    rel_path = str(f.relative_to(d.parent))
                    break
                except ValueError:
                    continue
            if context_file and f == context_file:
                rel_path = context_file.name
            matches.append((rel_path, kind, line_no, full_decl))
            if len(matches) >= max_matches:
                break
        if len(matches) >= max_matches:
            break

    if not matches:
        return (
            f"No declaration named '{name}' found in {len(files)} files "
            f"(context + search dirs). Try `-search {name}` for regex match "
            f"or check for clone renamings via `-clones`.\n"
        )

    lines = [f"=== Signature of '{name}' ({len(matches)} match"
             f"{'es' if len(matches) > 1 else ''}) ==="]
    for rel_path, kind, line_no, decl in matches:
        lines.append("")
        lines.append(f"-- {rel_path}:{line_no} ({kind})")
        # Append with one trailing period if the decl doesn't already end with one
        cleaned = decl.rstrip()
        if not cleaned.endswith('.'):
            cleaned = cleaned + '.'
        lines.append(cleaned)
    lines.append("")
    lines.append(f"Usage: apply ({name} <module_arg1> <module_arg2> ... &m).")
    lines.append(f"Supply one token per module-typed argument, plus `&m` for "
                 f"the memory snapshot if the lemma is about Pr[...] @ &m.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Clones
# ---------------------------------------------------------------------------

def analyze_clones(context_file: Path | None = None,
                   search_dirs: list[Path] | None = None) -> str:
    """List all clone declarations and their lemma renamings.

    Parses `clone ... as ...` declarations, including `rename` clauses,
    from the context file and optionally from theory files.

    Args:
        context_file: the .ec file loaded as session context
        search_dirs: optional directories to also scan

    Returns:
        formatted clone analysis
    """
    files: list[Path] = []
    if context_file and context_file.exists():
        files.append(context_file)
    if search_dirs:
        for d in search_dirs:
            if d.is_dir():
                files.extend(d.rglob('*.ec'))
                files.extend(d.rglob('*.eca'))

    # Parse clone declarations
    clones: list[dict] = []

    # Pattern for clone: clone [import/include] Theory as Alias [with ...] [rename ...]
    # Also handles: clone include Theory with ... rename ...
    clone_start_pat = re.compile(
        r'^\s*clone\s+(?:import\s+|include\s+)?(\S+)\s+as\s+(\w+)',
        re.MULTILINE
    )
    # Pattern for clone include (no "as" alias — inlines into current scope)
    clone_include_pat = re.compile(
        r'^\s*clone\s+include\s+(\S+)\s+with\b',
        re.MULTILINE
    )
    # Pattern for rename clauses: rename "old" as "new"
    rename_pat = re.compile(r'rename\s+"(\w+)"\s+as\s+"(\w+)"')

    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='replace')
        except (OSError, UnicodeDecodeError):
            continue

        for m in clone_start_pat.finditer(text):
            source_theory = m.group(1)
            alias = m.group(2)
            line_no = text[:m.start()].count('\n') + 1

            # Find rename clauses in the clone block (search until next period or proof)
            block_start = m.start()
            # Find end of clone declaration (look for period, proof *, or end of indentation)
            block_end = text.find('.', block_start)
            if block_end == -1:
                block_end = min(block_start + 1000, len(text))
            else:
                block_end += 1

            block = text[block_start:block_end]
            renames = rename_pat.findall(block)

            rel_path = str(f)
            if context_file:
                try:
                    rel_path = f.name
                except Exception:
                    pass

            clones.append({
                'file': rel_path,
                'line': line_no,
                'source': source_theory,
                'alias': alias,
                'renames': renames,
            })

        # Also find clone include with rename
        for m in clone_include_pat.finditer(text):
            source_theory = m.group(1)
            line_no = text[:m.start()].count('\n') + 1

            block_start = m.start()
            block_end = text.find('.', block_start)
            if block_end == -1:
                block_end = min(block_start + 1000, len(text))
            else:
                block_end += 1

            block = text[block_start:block_end]
            renames = rename_pat.findall(block)

            if renames:  # only include if there are renames (otherwise not interesting)
                rel_path = str(f)
                if context_file:
                    try:
                        rel_path = f.name
                    except Exception:
                        pass

                clones.append({
                    'file': rel_path,
                    'line': line_no,
                    'source': source_theory,
                    'alias': '(included)',
                    'renames': renames,
                })

    if not clones:
        return "No clone declarations found.\n"

    lines = [f"=== Clone declarations ({len(clones)} found) ===\n"]
    for c in clones:
        lines.append(f"  clone {c['source']} as {c['alias']}  ({c['file']}:{c['line']})")
        if c['renames']:
            for old, new in c['renames']:
                lines.append(f"    rename \"{old}\" as \"{new}\"")
                lines.append(f"    -> {c['alias']}.{new} (was {c['source']}.{old})")
        else:
            lines.append(f"    (no explicit renames — lemmas available as {c['alias']}.original_name)")
    lines.append("")
    lines.append("Usage: when a lemma from a cloned theory is not found, check")
    lines.append("if the clone has a rename clause. Use Alias.new_name in tactics.")
    lines.append("")
    lines.append("NOTE: This only shows clones in the loaded context and include dirs.")
    lines.append("To also search EasyCrypt standard library theories, use:")
    lines.append("  python3 core/easycrypt/ec_search.py clones -d easycrypt-src/theories")
    lines.append("")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Search EC theories and analyze clones")
    sub = parser.add_subparsers(dest='cmd')

    p_search = sub.add_parser('search', help='Search for lemma names')
    p_search.add_argument('query', help='Regex pattern to search for')
    p_search.add_argument('-d', '--dirs', nargs='+', default=['easycrypt-src/theories'],
                          help='Directories to search')
    p_search.add_argument('-f', '--context', help='Context .ec file')
    p_search.add_argument('-n', '--max', type=int, default=30, help='Max results')

    p_clones = sub.add_parser('clones', help='List clone declarations')
    p_clones.add_argument('-f', '--context', help='Context .ec file')
    p_clones.add_argument('-d', '--dirs', nargs='+', default=[], help='Extra directories')

    p_sig = sub.add_parser('sig', help='Look up exact signature of a lemma/op')
    p_sig.add_argument('name', help='Exact name (no regex) of the declaration')
    p_sig.add_argument('-d', '--dirs', nargs='+', default=['easycrypt-src/theories'],
                       help='Directories to search')
    p_sig.add_argument('-f', '--context', help='Context .ec file')
    p_sig.add_argument('-n', '--max', type=int, default=3, help='Max matches')

    args = parser.parse_args()

    if args.cmd == 'search':
        dirs = [Path(d) for d in args.dirs]
        ctx = Path(args.context) if args.context else None
        print(search_lemmas(args.query, dirs, ctx, args.max))
    elif args.cmd == 'clones':
        dirs = [Path(d) for d in args.dirs]
        ctx = Path(args.context) if args.context else None
        print(analyze_clones(ctx, dirs))
    elif args.cmd == 'sig':
        dirs = [Path(d) for d in args.dirs]
        ctx = Path(args.context) if args.context else None
        print(lookup_lemma_signature(args.name, dirs, ctx, args.max))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
