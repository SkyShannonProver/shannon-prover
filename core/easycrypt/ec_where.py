"""ec_where: structural lookup of a NAME in the loaded EC context.

Wraps EC's native `print NAME.` query. If NAME doesn't resolve at the
top level, falls back through known clone-instance prefixes (extracted
from `clone X as Y` declarations in the context file) to find the
fully qualified form.

The point: agents searching for "ofintd" / "max_counter" / "MainD" by
grep get either a wall of false positives or only a declaration line.
This returns a single structured answer:

  [HIT|HIT-VIA-CLONE|MISS]  resolved-name  kind
  <full pretty-printed body>
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


# ---------- helpers ----------

_KIND_HEADERS = (
    'modules',
    'theories',
    'operators or predicates',
    'lemmas or axioms',
    'module types',
    'types',
)

_HEADER_RE = re.compile(
    r'^\* In \[(' + '|'.join(re.escape(h) for h in _KIND_HEADERS) + r')\]:\s*$',
    re.MULTILINE,
)


def _kind_to_label(kind_str: str, body: str = '') -> str:
    base = {
        'modules': 'module',
        'theories': 'theory',
        'operators or predicates': 'op',
        'lemmas or axioms': 'lemma',
        'module types': 'module type',
        'types': 'type',
    }.get(kind_str, kind_str)
    # Refine: 'op' could be op, pred, or abbrev; 'lemma' could be lemma,
    # axiom, or an equivalence declaration printed under the same EC section.
    if base == 'op' and body:
        if re.search(r'\bpred\s+', body):
            return 'pred'
        if re.search(r'\babbrev\s+', body):
            return 'abbrev'
    if base == 'lemma' and body:
        if re.search(r'\bequiv\s+', body):
            return 'equiv'
        if re.search(r'\baxiom\s+', body):
            return 'axiom'
    return base


def _extract_clone_aliases(context_file: Path | None) -> list[str]:
    """Return prefix candidates for clone-fallback resolution.

    Includes:
      - aliases Y from `clone X as Y` declarations
      - names N from `theory N.` and `local theory N.` declarations
        (these are not clones but provide qualified access like `N.member`)
      - common nested forms `Y.RO`, `Y.I1`, etc. (subtype/split patterns)
    """
    if context_file is None or not context_file.exists():
        return []
    try:
        text = context_file.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeDecodeError):
        return []

    aliases: list[str] = []

    # clone X as Y  /  clone import X as Y  /  clone include X as Y
    clone_pat = re.compile(
        r'^\s*clone\s+(?:import\s+|include\s+)?(?:\S+)\s+as\s+(\w+)',
        re.MULTILINE,
    )
    for m in clone_pat.finditer(text):
        a = m.group(1)
        if a not in aliases:
            aliases.append(a)

    # theory NAME.  /  local theory NAME.
    theory_pat = re.compile(
        r'^\s*(?:local\s+)?theory\s+(\w+)\s*\.', re.MULTILINE,
    )
    for m in theory_pat.finditer(text):
        n = m.group(1)
        if n not in aliases:
            aliases.append(n)

    # Common nested-clone patterns under each prefix
    nested: list[str] = []
    for a in aliases:
        for sub in ('I1', 'I2', 'RO', 'RO_Pair', 'ROF', 'ROin', 'ROout'):
            nested.append(f'{a}.{sub}')
    return aliases + nested


_ANCHOR_NAME = '__ec_where_anchor_does_not_exist_zXyQ__'


def _build_probe_file(context_file: Path, base_lines: int,
                      print_targets: list[str]) -> Path:
    """Build a probe file: first base_lines of context_file, then for each
    target an anchor `print __anchor__.` (emits "no such object") followed
    by `print TARGET.`. The anchor markers split the output reliably.
    """
    src = context_file.read_text(encoding='utf-8', errors='replace')
    head = ''.join(src.splitlines(keepends=True)[:base_lines])
    probe_path = Path(f'/tmp/ec_where_probe_{os.getpid()}_'
                      f'{abs(hash(tuple(print_targets)))}.ec')
    body = head + '\n(* === EC_WHERE PROBE === *)\n'
    for t in print_targets:
        body += f'print {_ANCHOR_NAME}.\n'
        body += f'print {t}.\n'
    body += f'print {_ANCHOR_NAME}.\n'  # trailing anchor
    probe_path.write_text(body, encoding='utf-8')
    return probe_path


def _ec_env() -> dict:
    """Return os.environ enriched with the EC opam switch env so that
    `easycrypt` resolves on PATH. Tolerates missing ec_env import."""
    import os as _os
    env = dict(_os.environ)
    try:
        from core.easycrypt.ec_env import get_ec_env  # type: ignore
        env.update(get_ec_env())
    except Exception:
        pass
    return env


def _run_ec(probe_path: Path, include_dirs: list[Path],
            timeout: int = 60) -> str:
    """Run easycrypt on probe_path, return stdout. Raises on PATH or
    spawn errors — silent failure here used to cause every probe to
    look like a miss."""
    args = ['easycrypt']
    for d in include_dirs:
        args.extend(['-I', str(d)])
    args.append(str(probe_path))
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           timeout=timeout, env=_ec_env())
        return r.stdout
    except FileNotFoundError as e:
        raise RuntimeError(
            f"easycrypt not in PATH. Run `eval \"$(opam env "
            f"--switch=easycrypt)\"` first. Original: {e}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"easycrypt timed out after {timeout}s")


def _parse_print_blocks(output: str, target_name: str) -> dict | None:
    """Parse EC output for a single `print NAME.` result.

    Returns {'kind': str, 'body': str, 'has_error': bool} on hit, None on miss.

    Strategy:
      - If the output contains `no such object in any category` AND no
        section header matches the target name's basename, return None.
      - Otherwise find a section block whose body mentions target_name's
        basename in a declaration position.
    """
    base = target_name.split('.')[-1]
    # Patterns: a successful print produces a section header followed by
    # a declaration that includes `base` as the name.
    # Cover all EC top-level declaration kinds emitted by `print`.
    decl_patterns = [
        rf'\bmodule\s+(?:type\s+)?{re.escape(base)}\s*[\(={{ ]',
        rf'\b(?:local\s+)?theory\s+{re.escape(base)}\.',
        rf'\b(?:local\s+)?op\s+{re.escape(base)}\b',
        rf'\b(?:local\s+)?pred\s+{re.escape(base)}\b',
        rf'\b(?:local\s+)?abbrev\s+{re.escape(base)}\b',
        rf'\b(?:local\s+)?lemma\s+{re.escape(base)}[:\s\[]',
        rf'\b(?:local\s+)?equiv\s+{re.escape(base)}\s*:',
        rf'\b(?:local\s+)?axiom\s+{re.escape(base)}[:\s\[]',
        rf'\btype\s+{re.escape(base)}\b',
        rf'\(\*\s*{re.escape(target_name)}\s*\*\)',  # e.g. (* C.gt0_max_counter *)
    ]
    matched_pat = None
    for p in decl_patterns:
        if re.search(p, output):
            matched_pat = p
            break
    if matched_pat is None:
        return None

    # Find the section header that precedes the matching declaration
    decl_match = re.search(matched_pat, output)
    decl_pos = decl_match.start()
    # Walk backwards from decl_pos to find the nearest "* In [..]" header
    headers = list(_HEADER_RE.finditer(output, 0, decl_pos))

    # Body: from the matched header (or the decl) to the next header or EOF
    body_start = headers[-1].start() if headers else decl_pos
    next_header = _HEADER_RE.search(output, decl_match.end())
    body_end = next_header.start() if next_header else len(output)
    body = output[body_start:body_end].strip()

    if not headers:
        kind = 'unknown'
    else:
        kind = _kind_to_label(headers[-1].group(1), body)

    return {'kind': kind, 'body': body, 'has_error': False}


_PROOF_KINDS = {"lemma", "equiv", "hoare", "phoare", "ehoare"}
_PROOF_TERMINATORS = ("qed.", "admitted.", "abort.")


def _strip_ec_comments(s: str) -> str:
    """Remove EC `(* … *)` comments (non-nested approximation) so a `qed.` /
    `admit.` inside a comment is not mistaken for proof structure."""
    return re.sub(r"\(\*.*?\*\)", " ", s, flags=re.S)


def classify_proof_status(text: str, line_num: int, kind: str) -> str | None:
    """STATIC proof-status FACT for a source lemma: is it actually PROVEN, or
    declared-but-`admit`ed / aborted? The source-scan body deliberately omits the
    proof text (ec_def_resolver cuts at `proof.`), so classify the `proof. … qed.`
    block here. This is a verifier-style fact the agent otherwise has to reconstruct
    by reading the file by hand (e.g. learning `swap_Double_sample` is `admit`); it
    returns a 1-word classification, never the proof text. Boundary-safe: it states
    what IS (the body says admit or it does not), it recommends nothing.

    Returns "proven" | "admit" | "contains_admit" | "aborted", or None when the
    declaration is not a proof obligation (axiom/op/module/type) or can't be read."""
    if str(kind or "").lower() not in _PROOF_KINDS:
        return None
    lines = text.splitlines()
    if not (0 < line_num <= len(lines)):
        return None
    region = _strip_ec_comments("\n".join(lines[line_num - 1:]))
    pi = region.find("proof.")
    if pi < 0:
        return None
    rest = region[pi + len("proof."):]
    cands = [(rest.find(t), t) for t in _PROOF_TERMINATORS if rest.find(t) >= 0]
    if not cands:
        return None
    pos, term = min(cands)
    body = rest[:pos]
    if term == "admitted.":
        return "admit"
    if term == "abort.":
        return "aborted"
    if "admit." in body:
        return "admit" if not body.replace("admit.", "").strip() else "contains_admit"
    return "proven"


_SCOPE_DECL_RE = re.compile(
    r'^\s*local\s+(?:lemma|equiv|hoare|phoare|op|pred|abbrev|axiom)\b'
)
_SECTION_START_RE = re.compile(r'^\s*section\b')
_SECTION_END_RE = re.compile(r'^\s*end\s+section\b')


def classify_scope(text: str, line_num: int) -> str | None:
    """STATIC scope/export FACT for a source declaration. A pure name-resolution
    fact — exactly what EasyCrypt itself enforces on use: a `local` declaration
    raises `unknown identifier` if cited from outside its section. The agent
    otherwise reconstructs this by reading the file by hand (e.g. learning that a
    section-`local` helper is not callable, then hunting the exported sibling).
    Recommends nothing; surfaces no other symbol.

    Returns:
      "local"                  — `local` declaration; never exported.
      "exported_after_section" — non-local, but inside an open `section`; exported
                                  once the section closes, abstracted over its params.
      "exported"               — plain top-level declaration.
      None                     — line out of range.
    """
    lines = text.splitlines()
    if not (0 < line_num <= len(lines)):
        return None
    if _SCOPE_DECL_RE.match(lines[line_num - 1]):
        return "local"
    depth = 0
    for ln in lines[:line_num - 1]:
        if ln.lstrip().startswith('(*'):
            continue
        if _SECTION_START_RE.match(ln):
            depth += 1
        elif _SECTION_END_RE.match(ln):
            depth = max(0, depth - 1)
    return "exported_after_section" if depth > 0 else "exported"


def _source_scope(
    name: str, context_file: "Path | None", base_lines: int | None = None,
) -> str | None:
    """Best-effort scope/export FACT from the in-scope source for a name EC `print`
    resolved directly (mirrors `_source_proof_status`). None when the name is not in
    the scannable source."""
    if context_file is None or not context_file.exists():
        return None
    try:
        from core.easycrypt.ec_def_resolver import parse_source_defs  # type: ignore
        text = context_file.read_text(encoding='utf-8', errors='replace')
        if base_lines is not None:
            text = ''.join(text.splitlines(keepends=True)[:base_lines])
        table = parse_source_defs(text)
        for cand in [name] + ([name.split(".")[-1]] if "." in name else []):
            hit = table.get(cand)
            if hit is not None:
                return classify_scope(text, hit.line_num)
    except Exception:
        return None
    return None


def _source_proof_status(
    name: str, context_file: "Path | None", base_lines: int | None = None,
) -> str | None:
    """Best-effort proof_status from the in-scope source for a name EC `print`
    resolved DIRECTLY. EC `print` treats an `admit`ed lemma as proven (it is in the
    environment), so it cannot tell us — only the source can. Returns None when the
    name is not in the scannable source (e.g. a compiled-library lemma, which is
    proven by construction)."""
    if context_file is None or not context_file.exists():
        return None
    try:
        from core.easycrypt.ec_def_resolver import parse_source_defs  # type: ignore
        text = context_file.read_text(encoding='utf-8', errors='replace')
        if base_lines is not None:
            text = ''.join(text.splitlines(keepends=True)[:base_lines])
        table = parse_source_defs(text)
        cands = [name] + ([name.split(".")[-1]] if "." in name else [])
        for cand in cands:
            hit = table.get(cand)
            if hit is not None:
                return classify_proof_status(text, hit.line_num, hit.kind)
    except Exception:
        return None
    return None


def _source_scan_lookup(
    name: str,
    context_file: Path,
    *,
    base_lines: int | None = None,
) -> dict | None:
    """Resolve source-level definitions when EC `print` misses.

    This is intentionally lower authority than EasyCrypt `print`.  It is
    useful for clone override bindings such as `SplitD.test`, where the
    current source contains `clone ... as SplitD with op test = ...` but EC
    does not expose that override as a normal printable object.
    """
    try:
        from core.easycrypt.ec_def_resolver import (  # type: ignore
            derive_subtype_lemmas,
            parse_source_defs,
        )
    except Exception:
        return None
    try:
        text = context_file.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None
    if base_lines is not None:
        text = ''.join(text.splitlines(keepends=True)[:base_lines])
    table = parse_source_defs(text)
    candidates = [name]
    if "." in name:
        candidates.append(name.split(".")[-1])
    for candidate in candidates:
        hit = table.get(candidate)
        if hit is None:
            continue
        resolved = name if candidate != name and "." in name else hit.name
        body = _format_source_def_body(resolved, hit.kind, hit.body)
        return {
            'name': name,
            'status': 'source-resolved',
            'resolved': resolved,
            'kind': hit.kind,
            'body': body,
            'attempts': [],
            'other_hits': [],
            'note': hit.note,
            'source_line': hit.line_num,
            'proof_status': classify_proof_status(text, hit.line_num, hit.kind),
            'scope': classify_scope(text, hit.line_num),
        }
    if "." in name:
        prefix, tail = name.rsplit(".", 1)
        for entry in table.values():
            if getattr(entry, "kind", "") != "subtype":
                continue
            for derived in derive_subtype_lemmas(entry):
                if derived.name != tail:
                    continue
                body = _format_source_def_body(name, derived.kind, derived.body)
                return {
                    'name': name,
                    'status': 'source-resolved',
                    'resolved': name,
                    'kind': derived.kind,
                    'body': body,
                    'attempts': [],
                    'other_hits': [],
                    'note': (
                        f"{derived.note}; qualified through `{prefix}`"
                        if derived.note else f"qualified through `{prefix}`"
                    ),
                    'source_line': derived.line_num,
                    'proof_status': classify_proof_status(text, derived.line_num, derived.kind),
                    'scope': classify_scope(text, derived.line_num),
                }
    return None


def _format_source_def_body(name: str, kind: str, body: str) -> str:
    body = str(body or "").strip()
    kind = str(kind or "definition").strip()
    if kind in {"op", "pred", "abbrev"}:
        sep = " " if body.startswith((":", "=")) else " = "
        return f"{kind} {name}{sep}{body}".strip()
    if kind == "axiom":
        return f"axiom {name}: {body}".strip()
    if kind in {"lemma", "equiv"}:
        sep = " " if body.startswith(("[", ":")) else ": "
        return f"{kind} {name}{sep}{body}".strip()
    if kind == "subtype":
        return f"subtype {name} = {body}".strip()
    if kind == "subtype_lemma":
        return f"lemma {name}: {body}".strip()
    return f"{kind} {name}: {body}".strip()


# ---------- main entry ----------

def _split_by_anchors(output: str, n_probes: int) -> list[str]:
    """Walk the output as a state machine to extract per-probe blocks.

    The probe file is structured as alternating anchor + target prints:
      print __anchor__.    -> always emits "no such object"
      print TARGET_0.      -> emits "no such object" (miss) or "* In [..]" block
      print __anchor__.
      print TARGET_1.
      ...
      print __anchor__.    (trailing)

    Both anchors and missed probes emit identical "no such object" lines.
    To disentangle: walk events in source order — anchor, probe, anchor,
    probe, ... — and consume one event per "no such object" or per
    "* In [..]" block (hit-probe).

    Returns a list `blocks` of length n_probes where blocks[i] is the
    text of probe i's output (or '' if the probe missed).
    """
    # Tokenize the output into events: each event is either a "no such
    # object" line or a "* In [..]:" section block.
    nso_re = re.compile(r'^no such object in any category\s*$', re.MULTILINE)
    nsos = [(m.start(), m.end()) for m in nso_re.finditer(output)]
    headers = [(m.start(), m.end(), m.group(1))
               for m in _HEADER_RE.finditer(output)]

    # Build sorted event list: (start_pos, kind, ...) where kind is
    # 'NSO' or 'HEADER'. For HEADERs, also compute end-of-block as the
    # start of the NEXT event (next NSO or next HEADER).
    events = []
    for s, e in nsos:
        events.append((s, 'NSO', e, None))
    for s, e, kind in headers:
        events.append((s, 'HEADER', e, kind))
    events.sort(key=lambda x: x[0])

    # Compute block end for each HEADER event = start of next event
    # (if next event is HEADER too, we still take just up to it because
    # consecutive HEADERs come from a SINGLE print emitting multiple
    # sections; group those).
    # Walk and group consecutive HEADER events into a single "hit" event.
    grouped = []  # list of (kind, start, end, label)
    i = 0
    while i < len(events):
        ev = events[i]
        if ev[1] == 'NSO':
            grouped.append(('NSO', ev[0], ev[2], None))
            i += 1
        else:
            # Group consecutive HEADERs
            start = ev[0]
            kind = ev[3]
            j = i + 1
            while j < len(events) and events[j][1] == 'HEADER':
                j += 1
            # End of grouped block = start of next NSO event, or EOF
            if j < len(events):
                end = events[j][0]
            else:
                end = len(output)
            grouped.append(('HIT', start, end, kind))
            i = j

    # Walk events in expected source order: anchor, target, anchor,
    # target, ..., anchor. For each pair of consecutive anchors, the
    # event(s) between them belong to the target.
    blocks = [''] * n_probes
    # Find indexes of grouped events that are anchors. Anchors are NSO
    # events that match the structure: there should be exactly one
    # anchor before each probe and one final trailing anchor, total
    # n_probes + 1 anchor events. Probe events between anchors are HIT
    # (1 event) or NSO (1 event = miss).
    # Algorithm: scan grouped, track 'state': after each anchor we
    # expect a probe slot.
    anchor_count = 0
    pi = 0
    n_grouped = len(grouped)
    k = 0
    while k < n_grouped and pi < n_probes:
        ev = grouped[k]
        if ev[0] == 'NSO':
            # This is an anchor (or could be a probe miss). Use position-
            # based heuristic: the FIRST NSO is anchor 0. After each
            # anchor, the NEXT event (HIT or NSO) is the probe slot.
            anchor_count += 1
            # Look at next event (k+1) for the probe slot
            if k + 1 < n_grouped:
                nxt = grouped[k + 1]
                if nxt[0] == 'HIT':
                    blocks[pi] = output[nxt[1]:nxt[2]]
                    pi += 1
                    k += 2  # consume anchor + hit
                    continue
                else:  # nxt is NSO → probe missed
                    blocks[pi] = ''  # miss
                    pi += 1
                    k += 2  # consume anchor + miss-NSO
                    continue
            else:
                k += 1
        else:
            # Should not happen if structure is correct (HIT without preceding anchor)
            k += 1
    return blocks


_THEORY_NAME_RE = re.compile(r'^[A-Z]\w*$')


def _cross_file_symbol_scope(
    name: str,
    context_file: "Path | None",
    include_dirs: "list[Path] | None",
) -> dict | None:
    """Bounded find-definition across the context file's `require import`ed theories:
    locate the EXACT name and report its scope/file as a FACT. Explains the common
    `unknown identifier` on a section-`local` helper in an imported theory. Pure
    name-resolution — returns ONLY the named symbol's scope/file; never sibling or
    close-match candidates (that would be a route recommendation, out of bounds)."""
    if context_file is None or not context_file.exists():
        return None
    try:
        from core.easycrypt.ec_file_index import index_ec_file, check_lemma  # type: ignore
    except Exception:
        return None
    base = name.split(".")[-1]
    try:
        ctx_idx = index_ec_file(context_file)
    except Exception:
        return None
    theories: list[str] = []
    for req in ctx_idx.get("requires", []):
        for tok in str(req).replace(".", " ").split():
            if tok in ("import", "export", "theory"):
                continue
            if _THEORY_NAME_RE.match(tok) and tok not in theories:
                theories.append(tok)
    dirs = [context_file.parent] + [d for d in (include_dirs or []) if d]
    seen: set = set()
    for theory in theories[:40]:
        tfile = next((d / f"{theory}.ec" for d in dirs
                      if (d / f"{theory}.ec").exists()), None)
        if tfile is None or tfile in seen:
            continue
        seen.add(tfile)
        try:
            res = check_lemma(tfile, base)
        except Exception:
            continue
        info = res.get("lemma_info") if res.get("exists") else None
        if not info:
            continue
        return {
            'name': name,
            'status': 'found-not-in-scope',
            'resolved': base,
            'kind': info.get("kind"),
            'body': info.get("statement"),
            'attempts': [],
            'other_hits': [],
            'note': f"declared in {tfile.name}",
            'source_line': info.get("line"),
            'source_file': tfile.name,
            'scope': info.get("scope"),
            'proof_status': None,
        }
    return None


def where(name: str,
          context_file: Path | None,
          include_dirs: list[Path],
          base_lines: int | None = None,
          max_clone_attempts: int = 30) -> dict:
    """Resolve NAME via `print` with clone-prefix fallback.

    Probes top-level NAME first; if missing, tries every clone alias /
    theory prefix extracted from the context file in a single batched EC
    call. Returns the first hit (top-level preferred).

    Args:
        name: name to look up.
        context_file: the .ec file loaded as session context.
        include_dirs: -I dirs to pass to easycrypt.
        base_lines: lines of context_file to load. None = full file.
        max_clone_attempts: cap on number of clone-prefix fallbacks.

    Returns:
        dict with keys: name, status, resolved, kind, body, attempts, note.
    """
    if not name or not name.strip():
        return {'name': name, 'status': 'error', 'resolved': None,
                'kind': None, 'body': None, 'attempts': [],
                'note': 'empty name'}
    # Reject names that aren't valid EC identifiers — `print` would parse-fail
    if not re.match(r'^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)*$', name.strip()):
        return {'name': name, 'status': 'error', 'resolved': None,
                'kind': None, 'body': None, 'attempts': [],
                'note': f'name {name!r} is not a valid EC identifier '
                        '(letters/underscores/digits/dots only). For '
                        'pattern search use `-search REGEX` or '
                        '`-search-skeleton QUERY`.'}
    if context_file is None or not context_file.exists():
        return {'name': name, 'status': 'error', 'resolved': None,
                'kind': None, 'body': None, 'attempts': [],
                'note': 'no context file'}

    if base_lines is None:
        base_lines = len(context_file.read_text(
            encoding='utf-8', errors='replace').splitlines())

    aliases = _extract_clone_aliases(context_file)
    candidates = [name] + [f'{a}.{name}' for a in aliases]
    candidates = candidates[:1 + max_clone_attempts]

    # Build ONE batched probe file with anchors between targets
    probe = _build_probe_file(context_file, base_lines, candidates)
    try:
        out = _run_ec(probe, include_dirs)
    finally:
        try:
            probe.unlink()
        except OSError:
            pass

    blocks = _split_by_anchors(out, len(candidates))
    attempts: list[tuple[str, bool]] = []
    hits: list[tuple[str, dict]] = []  # (resolved_name, parsed_block) for all hits
    for i, cand in enumerate(candidates):
        block = blocks[i] if i < len(blocks) else ''
        parsed = _parse_print_blocks(block, cand) if block else None
        attempts.append((cand, parsed is not None))
        if parsed is not None:
            hits.append((cand, parsed))

    if hits:
        # Prefer direct (top-level) hit if present
        direct_hit = next((h for h in hits if h[0] == name), None)
        primary = direct_hit if direct_hit else hits[0]
        cand, parsed_hit = primary
        is_direct = (cand == name)
        # Other hits (for ambiguity surfacing)
        others = [(c, p) for c, p in hits if c != cand]
        return {
            'name': name,
            'status': 'direct' if is_direct else 'clone-resolved',
            'resolved': cand,
            'kind': parsed_hit['kind'],
            'body': parsed_hit['body'],
            'attempts': attempts,
            'other_hits': others,  # list of (resolved_name, {kind, body})
            'note': '',
            'proof_status': _source_proof_status(cand, context_file, base_lines),
            'scope': _source_scope(cand, context_file, base_lines),
        }

    fallback = _source_scan_lookup(name, context_file, base_lines=base_lines)
    if fallback is not None:
        fallback['attempts'] = attempts
        return fallback

    # Cross-file scope FACT: EC `print` and the current-file scan both missed. The
    # name may be a section-`local` helper in an imported theory (EC raises `unknown
    # identifier` for it) — explain that as a fact instead of a bare miss, so the agent
    # stops chasing a non-exported symbol by hand-reading the imported source.
    cross = _cross_file_symbol_scope(name, context_file, include_dirs)
    if cross is not None:
        cross['attempts'] = attempts
        return cross

    return {
        'name': name,
        'status': 'miss',
        'resolved': None,
        'kind': None,
        'body': None,
        'attempts': attempts,
        'note': f'tried {len(attempts)} candidate(s), none resolved',
    }


def where_multi(names: list[str],
                context_file: Path | None,
                include_dirs: list[Path],
                base_lines: int | None = None,
                max_clone_attempts: int = 30) -> dict[str, dict]:
    """Resolve MANY names in a single batched EC subprocess call.

    Unlike calling `where()` N times (which costs N × ~1.5s), this builds
    one probe file with all (name × clone-prefix) probes interleaved with
    anchors and parses the output state-machine-style.

    Returns: {name: result_dict_same_shape_as_where}.

    Skips names that fail validation (empty, non-identifier) — they get
    a 'status: error' result without contributing probes.
    """
    if context_file is None or not context_file.exists():
        return {n: {'name': n, 'status': 'error', 'resolved': None,
                    'kind': None, 'body': None, 'attempts': [],
                    'note': 'no context file'} for n in names}

    if base_lines is None:
        base_lines = len(context_file.read_text(
            encoding='utf-8', errors='replace').splitlines())

    aliases = _extract_clone_aliases(context_file)

    # Build per-name candidate lists, skipping invalid names
    valid: list[str] = []
    results: dict[str, dict] = {}
    name_to_cands: dict[str, list[str]] = {}
    for n in names:
        if not n or not n.strip():
            results[n] = {'name': n, 'status': 'error',
                          'resolved': None, 'kind': None, 'body': None,
                          'attempts': [], 'note': 'empty name'}
            continue
        if not re.match(r'^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)*$', n.strip()):
            results[n] = {'name': n, 'status': 'error',
                          'resolved': None, 'kind': None, 'body': None,
                          'attempts': [],
                          'note': f'not a valid EC identifier: {n!r}'}
            continue
        valid.append(n)
        cands = [n] + [f'{a}.{n}' for a in aliases]
        name_to_cands[n] = cands[:1 + max_clone_attempts]

    if not valid:
        return results

    # Flatten all probes into one list, remembering which name owns which
    flat: list[str] = []
    name_ranges: dict[str, tuple[int, int]] = {}
    for n in valid:
        start = len(flat)
        flat.extend(name_to_cands[n])
        name_ranges[n] = (start, len(flat))

    probe = _build_probe_file(context_file, base_lines, flat)
    try:
        out = _run_ec(probe, include_dirs)
    finally:
        try:
            probe.unlink()
        except OSError:
            pass

    blocks = _split_by_anchors(out, len(flat))

    for n in valid:
        start, end = name_ranges[n]
        attempts: list[tuple[str, bool]] = []
        hits: list[tuple[str, dict]] = []
        for i in range(start, end):
            cand = flat[i]
            block = blocks[i] if i < len(blocks) else ''
            parsed = _parse_print_blocks(block, cand) if block else None
            attempts.append((cand, parsed is not None))
            if parsed is not None:
                hits.append((cand, parsed))
        if hits:
            direct = next((h for h in hits if h[0] == n), None)
            primary = direct if direct else hits[0]
            cand, parsed_hit = primary
            others = [(c, p) for c, p in hits if c != cand]
            results[n] = {
                'name': n,
                'status': 'direct' if cand == n else 'clone-resolved',
                'resolved': cand,
                'kind': parsed_hit['kind'],
                'body': parsed_hit['body'],
                'attempts': attempts,
                'other_hits': others,
                'note': '',
                'proof_status': _source_proof_status(cand, context_file, base_lines),
            }
        else:
            fallback = _source_scan_lookup(n, context_file, base_lines=base_lines)
            if fallback is not None:
                fallback['attempts'] = attempts
                results[n] = fallback
                continue
            results[n] = {
                'name': n, 'status': 'miss', 'resolved': None,
                'kind': None, 'body': None, 'attempts': attempts,
                'note': f'tried {len(attempts)} candidate(s), none resolved',
            }
    return results


def format_where(result: dict, max_body_chars: int = 1500) -> str:
    """Pretty-print a where() result for the agent."""
    name = result['name']
    status = result['status']
    if status == 'error':
        return f"[WHERE-ERROR] {name}: {result['note']}\n"
    if status == 'miss':
        attempts = ', '.join(c for c, _ in result['attempts'])
        return (
            f"[WHERE-MISS] {name} not found.\n"
            f"  tried: {attempts}\n"
            f"  hint: no declaration resolved in the current EasyCrypt "
            f"context or source-scan fallback. Use a more exact qualified "
            f"name, ask the manager for `lemma_hints`, or read the current "
            f"source file for broader declaration context "
            f"before trying to apply it.\n"
        )

    resolved = result['resolved']
    kind = result['kind']
    body = result['body'] or ''
    if len(body) > max_body_chars:
        body = body[:max_body_chars] + f'\n  ... [truncated, {len(result["body"])} chars total]'

    # Proof-status FACT: surface whether a resolved lemma is actually PROVEN vs
    # declared-but-`admit`ed/aborted, so the agent does not have to read the file by
    # hand to learn (e.g.) that `swap_Double_sample` is `admit`. `admit`ed lemmas are
    # still citable in EC, so this is decision-relevant context, not a prohibition.
    ps = result.get('proof_status')
    kind_tag = kind if not ps else f"{kind} · {ps}"

    if status == 'direct':
        header = f"[WHERE-HIT] {name}  (kind: {kind_tag})"
    elif status == 'source-resolved':
        header = (
            f"[WHERE-HIT-SOURCE] {name}  "
            f"(kind: {kind_tag}; source-scan fallback)"
        )
    elif status == 'found-not-in-scope':
        src = result.get('source_file') or 'an imported theory'
        header = (f"[WHERE-OUT-OF-SCOPE] {name}  "
                  f"(kind: {kind_tag}; declared in {src} but NOT in scope here)")
    else:  # clone-resolved
        header = (f"[WHERE-HIT-VIA-CLONE] {name} -> {resolved}  "
                  f"(kind: {kind_tag}; not at top level — found via clone prefix)")

    out = header + '\n' + body + '\n'
    if ps in ("admit", "contains_admit", "aborted"):
        out += (
            f"PROOF STATUS: `{ps}` — this lemma is declared but "
            + ("its proof body is `admit.`" if ps == "admit"
               else "contains `admit.`" if ps == "contains_admit"
               else "the proof was `abort`ed")
            + " in the in-scope source (still citable in EC; you would be relying "
              "on an unproven obligation).\n"
        )
    # Scope/export FACT: a `local` declaration is unusable from outside its section;
    # a non-local section lemma is exported only after the section closes, abstracted
    # over its parameters. Surface the decision-relevant (non-plain-exported) cases.
    scope = result.get('scope')
    src = result.get('source_file')
    where_txt = f" in {src}" if src else ""
    if scope == "local":
        out += (
            f"SCOPE: `local`{where_txt} — declared `local`, so it is NOT exported; "
            f"`apply {name}` from the current context fails with `unknown identifier`. "
            "It is not a usable lemma here.\n"
        )
    elif scope == "exported_after_section":
        out += (
            f"SCOPE: `exported_after_section`{where_txt} — exported once its `section` "
            "closes, abstracted over the section's declared parameters (supply them, "
            "e.g. the adversary module, when you apply it).\n"
        )
    if status == 'source-resolved':
        line = result.get('source_line')
        note = str(result.get('note') or "")
        if line:
            out += f"\nSOURCE: current context line {line}.\n"
        out += (
            "NOTE: This is source-scan context because EasyCrypt `print` "
            "did not resolve the exact name. Treat it as definition context, "
            "not as a daemon-verified lemma signature.\n"
        )
        if note:
            out += f"DETAIL: {note}\n"
    if status == 'clone-resolved':
        out += (f"\nNOTE: Use `{resolved}` (not just `{name}`) in tactics. "
                f"This name was auto-generated by a clone instance.\n")

    # Surface ambiguity: if multiple clone instances expose this name
    others = result.get('other_hits') or []
    if others:
        out += (f"\n[AMBIGUOUS] {name} also resolves in {len(others)} other "
                f"clone instance(s):\n")
        for other_cand, other_parsed in others:
            obody = (other_parsed['body'] or '').strip().splitlines()
            head_line = obody[2] if len(obody) > 2 else (obody[0] if obody else '')
            out += f"  - {other_cand}  (kind: {other_parsed['kind']})  {head_line.strip()[:80]}\n"
        out += (f"  → If your goal references one specifically, use the "
                f"qualified name. Re-run `-where Foo.{name}` to get its body.\n")
    return out


def main():
    """CLI: ec_where.py NAME -f context.ec -I dir1 -I dir2"""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('-f', '--file', dest='context', required=True)
    ap.add_argument('-I', dest='includes', action='append', default=[])
    args = ap.parse_args()
    res = where(args.name, Path(args.context),
                [Path(d) for d in args.includes])
    print(format_where(res))


if __name__ == '__main__':
    main()
