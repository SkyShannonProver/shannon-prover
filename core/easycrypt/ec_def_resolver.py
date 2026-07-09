"""Context-driven resolver: extract definitions of names referenced in the
current goal from the source .ec file, so the agent can read them without
manual `-search`/`-sig` exploration.

Driving observation (step3 Run 9, 16:20-16:33):
  Agent stuck on `SplitD.test (n, C.ofintd 0)` — needed the subtype round-trip
  lemma `C.ofintdK`. Agent reverse-engineered the subtype-rename convention
  over ~13 minutes, ran multiple `-search` queries, and finally guessed
  `C.ofintdK`. All the relevant definitions (`SplitD.test = fun p => ...`,
  `subtype counter = { ... } rename "ofint", "toint"`, `axiom gt0_max_counter`)
  were in the SAME file the lemma was being proved in — visible to anyone
  who reads the source. Agent could read the source too, but didn't know
  WHICH lines to read.

  This module surfaces those definitions for free as part of `-goal-info`.
  Pure context-driven retrieval: scan goal text for identifiers, scan
  source file for their declarations, output. No hardcoded names.

Output is fed by `-goal-info` as a `[DEFS REFERENCED IN GOAL]` section.
This is a source-scan fallback. EC-native `-where` / `print` results are the
ground truth whenever they are available; this resolver only decides which
definitions are worth inspecting.
Empty when no user-defined identifiers in goal have findable declarations
(so the section doesn't bloat goal-info on every call).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Identifier extraction
# ---------------------------------------------------------------------------

_IDENT_RE = re.compile(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\b')

# EC keywords + builtins. Identifiers matching these are skipped before
# source lookup. Conservative: missing entries cause extra (harmless)
# lookup attempts that just return None.
_DENY = {
    # EC keywords
    "forall", "exists", "fun", "if", "then", "else", "let", "in", "with",
    "match", "do", "while", "for", "return", "import", "require", "module",
    "type", "op", "pred", "abbrev", "axiom", "lemma", "equiv", "hoare",
    "phoare", "section", "end", "proof", "qed", "admit", "true", "false",
    # pRHL display vocabulary
    "Pr", "glob", "arg", "res", "pre", "post", "Current", "goal", "remaining",
    # Standard types/ops (covers most of stdlib)
    "int", "bool", "unit", "nat", "real", "list", "fmap", "fset",
    "size", "length", "head", "tail", "nth", "map", "filter",
    "Some", "None", "true", "false", "witness", "tt",
    # Common mathematical operators (single-char skipped via regex)
    "div", "mod", "min", "max", "abs",
    # State annotations
    "m", "m0", "L", "R",
}

def _looks_like_ec_def_name(name: str) -> bool:
    """True if `name` is a plausible candidate for source-file lookup.

    Filters: keywords, single-char lowercase (loop vars), and obvious noise.
    Single-char UPPERCASE is allowed (real modules like `C`, `D`, `G` are
    common in EC). Final filtering happens at source-table lookup — no match
    → skipped silently — so this heuristic can be permissive.
    """
    if not name or not (name[0].isalpha() or name[0] == "_"):
        return False
    if name in _DENY:
        return False
    # Single-char names: keep ONLY uppercase (modules), drop lowercase (vars).
    if len(name) == 1:
        return name[0].isupper()
    # Skip names that look like generic local vars (lowercase 1-2 chars +
    # optional digit). Heuristic — may miss real defs but safer for noise reduction.
    if re.match(r'^[a-z][0-9]?$', name):
        return False
    return True


def extract_candidate_idents(goal_text: str) -> list[str]:
    """Pull all candidate identifiers (including dotted names) from goal."""
    # Strip pHRL side-marks `{1}`, `{2}`, `{m}`, `{m0}` before extraction —
    # otherwise the regex picks them up as part of identifiers.
    cleaned = re.sub(r'\{[12]\}|\{m\d*\}', '', goal_text)
    # Strip type annotations like `(x : T)` to avoid pulling type names
    # that are usually primitives. Keep the names themselves (like x), let
    # the deny-list filter further.
    seen: set[str] = set()
    out: list[str] = []
    for m in _IDENT_RE.finditer(cleaned):
        name = m.group(1)
        if name in seen:
            continue
        if not _looks_like_ec_def_name(name.split(".")[0]):
            continue
        seen.add(name)
        out.append(name)
    return out


# ---------------------------------------------------------------------------
# Source-file definition table
# ---------------------------------------------------------------------------

@dataclass
class ResolvedDef:
    name: str            # e.g. "SplitD.test", "max_counter", "C.ofintdK"
    kind: str            # "op" | "pred" | "abbrev" | "axiom" | "subtype" | "subtype_lemma"
    body: str            # the actual definition or statement
    line_num: int        # 1-indexed line in source
    note: str = ""       # extra context, e.g. "(declared inside `clone ... as SplitD with`)"
    authority: str = "source_scan_fallback"


# clone ... as ALIAS with op NAME = BODY.
# We capture the WITH clause and parse op-bindings inside it.
_CLONE_AS_RE = re.compile(
    r'clone\s+(?:import\s+)?[\w\'.\s,]+?\s+as\s+(\w+)\s+with\b',
    re.MULTILINE,
)


def parse_source_defs(ec_text: str) -> dict[str, ResolvedDef]:
    """Build a name → ResolvedDef table from an .ec source file.

    Handles:
    - `op NAME [: TYPE] [= BODY] .`
    - `pred NAME = BODY .`
    - `abbrev NAME = BODY .`
    - `axiom NAME : STMT .`
    - `lemma NAME ... : STMT .` and `equiv NAME : STMT .`
      declarations, cut before `proof.`
    - `subtype NAME = { ... } rename "X", "Y" .`
    - `clone ... as ALIAS with op NAME = BODY .` (extracts ALIAS.NAME)

    Skips the proof body of lemmas/equivs.
    """
    defs: dict[str, ResolvedDef] = {}
    lines = ec_text.split("\n")

    # Pass 1: line-by-line scan for op/pred/abbrev/axiom/subtype
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Skip comments / proof bodies
        if stripped.startswith("(*") or stripped.startswith("proof"):
            i += 1
            continue

        # op
        m = re.match(r'^\s*(?:local\s+)?op\s+([\w\']+)(?:\s*\[[^\]]*\])?\s*(.*)$', line)
        if m:
            name = m.group(1)
            rest = m.group(2)
            # Accumulate until `.` at end of line
            full_rest = rest
            j = i + 1
            while not full_rest.rstrip().endswith(".") and j < min(i + 10, len(lines)):
                full_rest += " " + lines[j].strip()
                j += 1
            full_rest = full_rest.rstrip().rstrip(".")
            # full_rest starts with `:` (type-only) or `=` (with body) or both
            kind = "op"
            body = full_rest.strip()
            defs[name] = ResolvedDef(name=name, kind=kind, body=body,
                                     line_num=i + 1)
            i = j
            continue

        # pred / abbrev
        m = re.match(r'^\s*(?:local\s+)?(pred|abbrev)\s+([\w\']+)\s*=\s*(.*)$', line)
        if m:
            kind = m.group(1)
            name = m.group(2)
            rest = m.group(3)
            full_rest = rest
            j = i + 1
            while not full_rest.rstrip().endswith(".") and j < min(i + 10, len(lines)):
                full_rest += " " + lines[j].strip()
                j += 1
            body = full_rest.rstrip().rstrip(".").strip()
            defs[name] = ResolvedDef(name=name, kind=kind, body=body,
                                     line_num=i + 1)
            i = j
            continue

        # axiom
        m = re.match(r'^\s*(?:local\s+)?axiom\s+([\w\']+)\s*:\s*(.*)$', line)
        if m:
            name = m.group(1)
            rest = m.group(2)
            full_rest = rest
            j = i + 1
            while not full_rest.rstrip().endswith(".") and j < min(i + 10, len(lines)):
                full_rest += " " + lines[j].strip()
                j += 1
            body = full_rest.rstrip().rstrip(".").strip()
            defs[name] = ResolvedDef(name=name, kind="axiom", body=body,
                                     line_num=i + 1)
            i = j
            continue

        # lemma / equiv declaration.  Keep only the statement before `proof.`;
        # never include proof body text in source-scan lookup.
        m = re.match(r'^\s*(?:local\s+)?(lemma|equiv)\s+([\w\']+)\b\s*(.*)$', line)
        if m:
            kind = m.group(1)
            name = m.group(2)
            rest = m.group(3)
            full_rest = rest
            j = i + 1
            while (
                "proof." not in full_rest
                and j < min(i + 40, len(lines))
            ):
                full_rest += " " + lines[j].strip()
                j += 1
            proof_pos = full_rest.find("proof.")
            if proof_pos >= 0:
                full_rest = full_rest[:proof_pos]
            body = full_rest.strip()
            if body:
                defs[name] = ResolvedDef(
                    name=name,
                    kind=kind,
                    body=body,
                    line_num=i + 1,
                    note="source declaration only; proof body intentionally omitted",
                )
            i = j
            continue

        # subtype
        m = re.match(r'^\s*subtype\s+(\w+)\s*=\s*(.*)$', line)
        if m:
            name = m.group(1)
            rest = m.group(2)
            full_rest = rest
            j = i + 1
            # Subtype decls span until `.` (typically 2-4 lines)
            while not full_rest.rstrip().endswith(".") and j < min(i + 10, len(lines)):
                full_rest += " " + lines[j].strip()
                j += 1
            body = full_rest.rstrip().rstrip(".").strip()
            # Extract rename info if present
            rename_m = re.search(r'rename\s+"([^"]+)"\s*,\s*"([^"]+)"', body)
            note = ""
            ctor_name = ""
            extract_name = ""
            if rename_m:
                ctor_name = rename_m.group(1)  # e.g. "ofint"
                extract_name = rename_m.group(2)  # e.g. "toint"
                note = (f"rename ctor → {ctor_name}, extract → {extract_name}; "
                        f"derived ops: `{ctor_name}d` (default-injection), "
                        f"`{extract_name}` (extraction)")
            defs[name] = ResolvedDef(name=name, kind="subtype", body=body,
                                     line_num=i + 1, note=note)
            i = j
            continue

        i += 1

    # Pass 2: find `clone ... as ALIAS with` blocks and extract op-bindings
    # inside their `with` clauses. The bindings have form `op X = body.`
    # and are scoped under ALIAS.
    for cm in _CLONE_AS_RE.finditer(ec_text):
        alias = cm.group(1)
        # Walk lines from cm.end() until we hit a line that doesn't start with
        # whitespace continuation OR another clone/module decl.
        start_line = ec_text[:cm.start()].count("\n")
        # Heuristic: walk up to 30 lines forward
        for k in range(start_line + 1, min(start_line + 30, len(lines))):
            sub = lines[k].strip()
            if not sub or sub.startswith("(*"):
                continue
            # End of clone-with block: a line that starts with non-whitespace
            # and isn't an op/pred/type/realize binding
            if sub.startswith("realize") or sub.startswith("clone") or \
               sub.startswith("module") or sub.startswith("section") or \
               sub.startswith("end") or sub == "proof *.":
                break
            # op-binding: `op X = BODY` or `op X <- BODY` (rebinding form)
            opm = re.match(r'^op\s+(\w+)\s*[=<-]+\s*(.+?)\.?\s*(?:,)?$', sub)
            if opm:
                op_name = opm.group(1)
                op_body = opm.group(2).strip().rstrip(",").rstrip(".")
                qualified = f"{alias}.{op_name}"
                defs[qualified] = ResolvedDef(
                    name=qualified, kind="op",
                    body=f"= {op_body}",
                    line_num=k + 1,
                    note=f"(bound at clone of `{alias}`)",
                )
            # type-binding: `type X = T` (non-op but worth mentioning)
            tm = re.match(r'^type\s+(\w+)\s*[<-=]+\s*(.+?)\.?\s*(?:,)?$', sub)
            if tm:
                ty_name = tm.group(1)
                ty_body = tm.group(2).strip().rstrip(",").rstrip(".")
                qualified = f"{alias}.{ty_name}"
                defs.setdefault(qualified, ResolvedDef(
                    name=qualified, kind="type",
                    body=f"= {ty_body}",
                    line_num=k + 1,
                    note=f"(type bound at clone of `{alias}`)",
                ))

    return defs


# ---------------------------------------------------------------------------
# Subtype derived-lemma generator
# ---------------------------------------------------------------------------

def derive_subtype_lemmas(subtype_def: ResolvedDef) -> list[ResolvedDef]:
    """Given a subtype declaration with `rename "ctor", "extract"`, generate
    descriptions of the conventional EC subtype-derived lemmas.

    The lemma names follow these EC conventions:
      - `<extract>_<ctor>d`     : forall x, <extract> (<ctor>d x) = if P x then x else <extract> witness
      - `<ctor>dK`              : forall x, P x => <extract> (<ctor>d x) = x
      - `<extract>K`            : forall y, <ctor>d (<extract> y) = y     (when extract is total)

    These descriptions help the agent know the lemma names to use in `smt(...)`
    hints without reverse-engineering EC's subtype rename conventions.
    """
    if subtype_def.kind != "subtype":
        return []
    body = subtype_def.body
    rename_m = re.search(r'rename\s+"([^"]+)"\s*,\s*"([^"]+)"', body)
    if not rename_m:
        return []
    ctor = rename_m.group(1)        # e.g. "ofint" → injection
    extract = rename_m.group(2)      # e.g. "toint" → extraction
    # Extract the predicate body (between `{ ... }`)
    pred_m = re.search(r'\{\s*[\w\s:]+?\|\s*([^}]+?)\s*\}', body)
    pred = pred_m.group(1).strip() if pred_m else "<predicate>"

    return [
        ResolvedDef(
            name=f"{ctor}dK",
            kind="subtype_lemma",
            body=f"forall x, {pred} => {extract} ({ctor}d x) = x",
            line_num=subtype_def.line_num,
            note=f"(derived from subtype `{subtype_def.name}` rename convention)",
        ),
        ResolvedDef(
            name=f"{extract}_{ctor}d",
            kind="subtype_lemma",
            body=(f"forall x, {extract} ({ctor}d x) = "
                  f"if {pred} then x else {extract} witness"),
            line_num=subtype_def.line_num,
            note=f"(derived from subtype `{subtype_def.name}` rename convention)",
        ),
    ]


# ---------------------------------------------------------------------------
# Top-level resolver
# ---------------------------------------------------------------------------

def resolve_defs_in_goal(goal_text: str, ec_file: Path) -> list[ResolvedDef]:
    """Find user-defined ops/preds/axioms/subtypes referenced in `goal_text`
    by scanning `ec_file`.

    Returns a list of ResolvedDef ordered by source line number. Skips
    definitions for identifiers not in the file (standard-library names,
    primitives, local variables).

    Subtype-derived lemmas are appended whenever a subtype is referenced
    (the agent typically needs the round-trip lemma, not the subtype itself).
    """
    if not ec_file.exists():
        return []
    try:
        ec_text = ec_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    table = parse_source_defs(ec_text)

    # Extract candidate identifiers (including dotted ones like `SplitD.test`)
    candidates = extract_candidate_idents(goal_text)
    # Add dotted-name variants: for `Module.proc.x`, also try `Module.proc`
    # and `Module`. This handles cases where the goal mentions `C.ofintd`
    # but the table has `C.counter` (different qualified name same module).
    expanded: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        if c not in seen:
            expanded.append(c)
            seen.add(c)
        # Add prefixes
        parts = c.split(".")
        for k in range(1, len(parts)):
            pref = ".".join(parts[:k])
            if pref not in seen:
                expanded.append(pref)
                seen.add(pref)

    # Look up each
    found: list[ResolvedDef] = []
    found_names: set[str] = set()
    for name in expanded:
        if name in table and name not in found_names:
            found.append(table[name])
            found_names.add(name)
            continue
        # Clone-alias fallback: `M.X` not in table directly → look up plain
        # `X`. Common when an abstract theory contains the decl and is
        # cloned as `M`. E.g. agent has `C.counter` in goal; source has
        # `subtype counter` inside theory cloned as `C`. Surface `counter`'s
        # def with note that it's accessed via the alias.
        if "." in name and name not in found_names:
            tail = name.split(".")[-1]
            head = name.split(".")[0]
            if tail in table and name not in found_names:
                base = table[tail]
                # Re-emit with the qualified name + a note about the alias
                aliased = ResolvedDef(
                    name=name,
                    kind=base.kind,
                    body=base.body,
                    line_num=base.line_num,
                    note=(f"(declared as `{tail}` at line {base.line_num}; "
                          f"accessed in goal via alias `{head}`)"
                          + (f"; {base.note}" if base.note else "")),
                )
                found.append(aliased)
                found_names.add(name)
                continue
        # Subtype-rename fallback: `M.<rename_target>` (or `M.<rename_target>d`
        # for default-injection) → find subtype in table with that rename.
        # E.g. agent has `C.ofintd` in goal; source has `subtype counter
        # rename "ofint", "toint"` → `ofintd` is the default-injection of
        # ctor `ofint`. Surface the subtype.
        if "." in name and name not in found_names:
            head = name.split(".")[0]
            tail = name.split(".")[-1]
            for entry in table.values():
                if entry.kind != "subtype":
                    continue
                m = re.search(r'rename\s+"([^"]+)"\s*,\s*"([^"]+)"', entry.body)
                if not m:
                    continue
                ctor, extract = m.group(1), m.group(2)
                # tail might be `<ctor>d` (default-inj) or `<extract>` (extract)
                # or `<ctor>` (raw ctor) — match all of these
                if tail in (f"{ctor}d", extract, ctor):
                    role = ("default-injection" if tail == f"{ctor}d"
                            else "extraction" if tail == extract
                            else "ctor (partial)")
                    aliased = ResolvedDef(
                        name=name,
                        kind="subtype_op",
                        body=entry.body,
                        line_num=entry.line_num,
                        note=(f"`{tail}` is the {role} of subtype "
                              f"`{entry.name}` (declared at line "
                              f"{entry.line_num}). See derived lemmas below."),
                    )
                    found.append(aliased)
                    found_names.add(name)
                    # Also surface the subtype's derived lemmas
                    for dl in derive_subtype_lemmas(entry):
                        # Re-name with alias prefix so agent sees `C.ofintdK`
                        alias_dl = ResolvedDef(
                            name=f"{head}.{dl.name}",
                            kind=dl.kind,
                            body=dl.body,
                            line_num=dl.line_num,
                            note=dl.note,
                        )
                        if alias_dl.name not in found_names:
                            found.append(alias_dl)
                            found_names.add(alias_dl.name)
                    break

    # For each found subtype, append its derived-lemma descriptions IF the
    # agent's identifiers mention the rename targets (e.g. `C.ofintd` /
    # `C.toint` in goal → include `C.ofintdK` derived lemma).
    for d in list(found):
        if d.kind != "subtype":
            continue
        derived = derive_subtype_lemmas(d)
        for dl in derived:
            # Only append if agent's identifiers mention the rename target
            # (otherwise we spam the agent with all derived lemmas).
            mentioned = any(
                dl.name.split("d")[0] in c or dl.name.replace("d", "") in c
                for c in candidates
            ) or any(
                # Also include if any candidate has the form `<prefix>.<rename_target>`
                # — e.g. agent has `C.ofintd` in goal, derived lemma is `ofintdK`,
                # we surface it because `ofintd` is in candidate `C.ofintd`.
                dl.name.replace("K", "").replace("d", "") in c
                for c in candidates
            )
            # Always include for MVP — false positives are tolerable; agent
            # filters. Tighten later based on usage.
            found.append(dl)

    # Dedupe + sort by line_num
    seen2: set[str] = set()
    uniq: list[ResolvedDef] = []
    for d in found:
        if d.name in seen2:
            continue
        uniq.append(d)
        seen2.add(d.name)
    uniq.sort(key=lambda d: (d.line_num, d.name))
    return uniq


def format_defs(defs: list[ResolvedDef], max_body_chars: int = 200) -> str:
    """Format a list of resolved defs for inclusion in `-goal-info` output.

    Returns "" when the list is empty (caller can skip the section header).
    """
    if not defs:
        return ""
    out = [
        "[DEFS REFERENCED IN GOAL]",
        "  authority: source_scan_fallback; EC `-where` / `print` is ground truth.",
    ]
    for d in defs:
        body = d.body
        if len(body) > max_body_chars:
            body = body[:max_body_chars].rstrip() + " ..."
        line_tag = f"line {d.line_num}"
        kind_tag = d.kind
        out.append(f"  {d.name} ({kind_tag}, {line_tag}):")
        # Indent body lines
        for ln in body.splitlines():
            out.append(f"      {ln}")
        if d.note:
            out.append(f"    note: {d.note}")
        out.append("")
    return "\n".join(out).rstrip()


# Manual test entry point
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("-f", "--source-file", required=True,
                   help="Path to .ec file containing user-defined names")
    p.add_argument("-g", "--goal-file", required=True,
                   help="Path to file containing goal text (e.g. session current.out)")
    args = p.parse_args()
    sf = Path(args.source_file)
    gf = Path(args.goal_file)
    goal = gf.read_text(encoding="utf-8", errors="replace")
    defs = resolve_defs_in_goal(goal, sf)
    print(format_defs(defs))
