"""Single source of truth for the ProverWorkspaceView panel design philosophy.

Both the runtime gate (the manager's agent-view sanitization, which calls
`enforce`) and the CI audit (`workflow/validation/view_philosophy_audit.py`,
which uses the read-only predicates) import their rules from here so the two
never drift. See `core/easycrypt/TOOLS.md` "Panel design philosophy".

Enforcement policy (decided 2026-05-28):
  - framing / size  -> HARD gate (the manager strips/collapses at runtime).
  - provenance      -> FLAG only (transition period): surfaced as a WARN by the
                       audit; the runtime does not drop a verified tactic that
                       lacks markers, so good options are not lost before the
                       producers attach `derivation`/`verified`/`guarantee`.
"""
from __future__ import annotations

import re
from typing import Any
from core.easycrypt.value_shapes import as_dict as _dict

# Size budget applies to *framing* panels only; the truth layers (the goal and
# program frontier) are exempt — a genuinely large goal must not be trimmed.
TRUTH_PANELS = ("last_result", "proof_status", "current_goal", "program_frontier")
FRAMING_PANELS = (
    "application_context", "facts_and_diagnostics",
    "candidate_moves", "inspect_lookup_handles",
)
# Size is a *secondary* signal: calibration against compliant pre-refactor
# views showed a legitimately-rich equiv goal needs ~6.5 KB of framing context,
# more than a *bloated* Pr goal — so raw size cannot distinguish rich-but-clean
# from bloated. The real bloat detector is framing *presence* (FRAMING_STRIP);
# size is only a soft target + a generous runaway hard backstop.
SIZE_TARGET = 5120   # framing-panels total: WARN above this
SIZE_HARD = 8192     # framing-panels total: ERROR only on true runaway

MAX_CANDIDATE_MOVES = 3
MAX_INSPECT_TOPICS = 6   # the canonical inspect menu; WARN only above this

# Framing to strip outright (L3 route-hypothesis / risk-as-default-framing that
# must not be a standing panel). (panel_key, subkey).
FRAMING_STRIP = (
    ("application_context", "proof_story"),   # active_route_objective + risk_map
)
# `candidate_moves.limitations` is dual-purpose: default-risk framing (sourced
# from the removed proof_story) is stripped, but a *failure-specific*
# explanation (risk-after-failure, which the philosophy allows) is kept. Only
# entries with this source are stripped.
FRAMING_LIMITATION_SOURCE = "proof_story"
# Bare risk panels, stripped wherever they appear at panel top level.
FRAMING_STRIP_TOPLEVEL = ("risk_map", "proof_story")

# Imperative / ordering wording — panels must stay neutral.
IMPERATIVE_PATTERNS = [
    re.compile(r"\bdo this first\b", re.I),
    re.compile(r"\bbefore opening\b", re.I),
    re.compile(r"\bresolve\b[^.]*\bbefore\b", re.I),
    re.compile(r"\byou (?:must|should)\b", re.I),
    re.compile(r"\bfirst\b[^.]*\bthen\b", re.I),
]

# A verified tactic surfaced as a committable option must carry these.
REQUIRED_TACTIC_MARKERS = ("derivation", "verified", "guarantee")
OPTION_CONTAINER = re.compile(
    r"(candidate_moves\.moves|\.recommendations|selected_handles|"
    r"named_call_templates)")
EXCLUDE_TACTIC_PATH = re.compile(
    r"(limitations|risk_map|last_result|anti_route|"
    r"structural_transitions)")
_TACTIC_HEAD = re.compile(
    r"^\s*(have\b|rewrite\b|apply\b|call\b|byequiv\b|byphoare\b|bypr\b|"
    r"proc\b|inline\b|seq\b|sim\b|wp\b|sp\b|conseq\b|rnd\b|skip\b|auto\b|"
    r"smt\b|move\b|case\b|congr\b)")


# ── shared helpers (used by both runtime and audit) ──────────────────────────


def is_runnable_tactic(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(_TACTIC_HEAD.match(text)) and text.rstrip().endswith(".")


def walk_strings(node: Any, path: str = ""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def find_option_tactics(node: Any, path: str = ""):
    """Outermost dicts carrying a runnable tactic that are surfaced as a
    committable option (not an anti-route / risk / echo)."""
    if isinstance(node, dict):
        if any(is_runnable_tactic(node.get(k)) for k in ("tactic", "action")):
            if OPTION_CONTAINER.search(path) and not EXCLUDE_TACTIC_PATH.search(path):
                yield path, node
            return
        for k, v in node.items():
            yield from find_option_tactics(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from find_option_tactics(v, f"{path}[{i}]")


def framing_size(view: dict[str, Any]) -> int:
    import json
    return sum(len(json.dumps(view.get(p), ensure_ascii=False))
               for p in FRAMING_PANELS if p in view)


def imperative_findings(view: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for jpath, s in walk_strings(view):
        if any(p.search(s) for p in IMPERATIVE_PATTERNS):
            out.append((jpath, s))
    return out


def provenance_flags(view: dict[str, Any]) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for jpath, entry in find_option_tactics(view):
        missing = [m for m in REQUIRED_TACTIC_MARKERS if m not in entry]
        if missing:
            out.append((jpath, missing))
    return out


_GUARANTEE = {
    "easycrypt_verified_on_current_goal": (
        "locally valid on the current goal (EasyCrypt-verified); NOT a claim it is "
        "the optimal route or that it reaches qed; reversible — commit, read the "
        "new state, undo if worse"),
    "unverified_tactic_candidate": (
        "candidate derived from current-state analysis; not yet accepted by "
        "EasyCrypt; committing it is the proof-state decision"),
    "unverified_suggestion": (
        "route-selection context only; not verified on the current goal"),
}


def attach_provenance(view: dict[str, Any]) -> int:
    """Fill honest `derivation`/`verified`/`guarantee` markers on every
    committable tactic option that lacks them, so the agent is never misled
    about how an option arose or what it guarantees. Values reflect the entry's
    *actual* status. Only EasyCrypt evidence earns the verified marker; static
    candidates remain unverified. Producer-supplied markers win. Returns the
    number of entries stamped."""
    def _classify(entry: dict[str, Any]) -> tuple[str, str]:
        conf = str(entry.get("confidence") or "").lower()
        producer = str(entry.get("producer") or "")
        source = str(entry.get("source") or "")
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        epistemic = str(
            entry.get("epistemic_status")
            or metadata.get("epistemic_status")
            or ""
        )
        category = str(entry.get("category") or "").lower()
        title = str(entry.get("title") or "")
        # "Verified" status may be inferred ONLY from producer-supplied
        # provenance fields (confidence / producer / source / an explicit
        # `verified` marker), never from free-text display fields (title /
        # category) — otherwise an entry merely titled e.g. "avoid daemon
        # timeout" would be mis-stamped as daemon-accepted.
        trusted = f"{conf} {producer} {source}".lower()
        vflag = entry.get("verified")
        verified_marker = (
            isinstance(vflag, str)
            and vflag not in ("", "unverified_suggestion",
                              "unverified_tactic_candidate"))
        if (
            conf in {"verified", "verified_by_easycrypt"}
            or vflag is True
            or verified_marker
            or epistemic in {
                "easycrypt_preflight_accepted",
                "easycrypt_verified",
                "verified_by_easycrypt",
            }
        ):
            src = source or producer or "ProofIR typed frontend"
            return ("easycrypt_verified_on_current_goal",
                    f"type-matched + EasyCrypt-verified on the current goal (source: {src})")
        if category == "candidate":
            return ("unverified_tactic_candidate",
                    f"candidate surfaced from "
                    f"{source or producer or 'current-state analysis'}")
        src = source or producer or "current-state analysis"
        return ("unverified_suggestion",
                f"surfaced from {src}; not EasyCrypt-verified on this goal")

    entries = [(entry, str(entry.get("tactic") or entry.get("action") or "").strip(),
                _classify(entry)) for _jp, entry in find_option_tactics(view)]
    # A tactic that EasyCrypt accepted in one entry is the same verified option
    # wherever else it appears (e.g. a thin selected_handles twin) — upgrade it
    # so the agent is never told a verified option is "unverified".
    verified_tactics = {tac for _e, tac, (v, _d) in entries
                        if tac and v == "easycrypt_verified_on_current_goal"}
    stamped = 0
    for entry, tac, (verified, derivation) in entries:
        if tac in verified_tactics and verified != "easycrypt_verified_on_current_goal":
            verified, derivation = _classify({"source": "proofir typed bridge frontend"})
        if all(m in entry for m in REQUIRED_TACTIC_MARKERS):
            continue
        entry.setdefault("derivation", derivation)
        entry.setdefault("verified", verified)
        entry.setdefault("guarantee", _GUARANTEE[verified])
        stamped += 1
    return stamped


# ── runtime enforcement (called by the manager's agent-view sanitization) ──

# Fields that carry an actual move or truth content and must never be deleted by
# the imperative-neutralization pass.
_PROTECTED_LEAF_KEYS = frozenset({
    "tactic", "action", "derivation", "verified", "guarantee",
    "goal", "lines", "name", "statement",
})
_JPATH_TOKEN = re.compile(r"\.([^.\[\]]+)|\[(\d+)\]")


def _delete_leaf_field(view: dict[str, Any], jpath: str) -> bool:
    """Delete the leaf addressed by a ``walk_strings`` jpath (e.g.
    ``.application_context.note``) from its parent dict, when that is safe: the
    leaf must be a *named* dict field (not a list element) and must not be a
    protected tactic/truth field. Returns True iff it deleted something."""
    tokens = [(k or None, int(i) if i else None)
              for k, i in _JPATH_TOKEN.findall(jpath)]
    if not tokens:
        return False
    node: Any = view
    for key, idx in tokens[:-1]:
        try:
            node = node[key] if key is not None else node[idx]
        except (KeyError, IndexError, TypeError):
            return False
    key, idx = tokens[-1]
    if key is None or key in _PROTECTED_LEAF_KEYS:
        return False
    if isinstance(node, dict) and key in node:
        del node[key]
        return True
    return False


def enforce(view: dict[str, Any]) -> dict[str, Any]:
    """Mutate ``view`` in place to satisfy the HARD gates (framing, size) and
    return a report. Provenance is reported only (FLAG), never dropped."""
    report: dict[str, Any] = {
        "stripped": [], "imperative_stripped": [], "collapsed": [],
        "provenance_flagged": [],
    }
    if not isinstance(view, dict):
        return report

    # HARD: strip standing framing (L3 route-hypothesis / risk framing).
    for panel, sub in FRAMING_STRIP:
        node = view.get(panel)
        if isinstance(node, dict) and sub in node:
            del node[sub]
            report["stripped"].append(f"{panel}.{sub}")
    for key in FRAMING_STRIP_TOPLEVEL:
        if key in view:
            del view[key]
            report["stripped"].append(key)
        ac = view.get("application_context")
        if isinstance(ac, dict) and key in ac:
            del ac[key]
            report["stripped"].append(f"application_context.{key}")

    # HARD: strip default-risk limitations (proof_story-sourced); keep
    # failure-specific explanations (risk-after-failure is allowed).
    cmoves = view.get("candidate_moves")
    if isinstance(cmoves, dict) and isinstance(cmoves.get("limitations"), list):
        kept = [it for it in cmoves["limitations"]
                if not (isinstance(it, dict)
                        and it.get("source") == FRAMING_LIMITATION_SOURCE)]
        if len(kept) != len(cmoves["limitations"]):
            report["stripped"].append("candidate_moves.limitations(default-risk)")
        if kept:
            cmoves["limitations"] = kept
        else:
            cmoves.pop("limitations", None)

    # HARD: neutralize residual imperative wording in framing panels by
    # dropping the offending leaf's containing field where safe. Collect first
    # (imperative_findings walks the view) then delete, so we never mutate mid-
    # walk; a protected/structural leaf is left in place (reported as kept).
    for jpath, _s in imperative_findings(view):
        if any(jpath.startswith(f".{p}") for p in FRAMING_PANELS):
            if _delete_leaf_field(view, jpath):
                report["imperative_stripped"].append(jpath)
            else:
                report.setdefault("imperative_kept_protected", []).append(jpath)

    # Curated menus (inspect topics, candidate moves) are the "buttons" the
    # philosophy wants — blindly trimming them drops useful, state-relevant
    # options (calibration showed trimming inspect to N dropped
    # `rewrite_candidates`). So they are FLAGGED over budget, never auto-trimmed;
    # the producer narrows them and the audit surfaces a WARN. The only safe
    # hard size lever is the framing strip above; the rest of size is
    # goal-context-driven and legitimate.
    inspect = _dict(view.get("inspect_lookup_handles")).get("ask_manager_for")
    if isinstance(inspect, list) and len(inspect) > MAX_INSPECT_TOPICS:
        report["inspect_over_budget"] = len(inspect)
    moves = _dict(view.get("candidate_moves")).get("moves")
    if isinstance(moves, list) and len(moves) > MAX_CANDIDATE_MOVES:
        report["moves_over_budget"] = len(moves)

    # FILL: stamp honest provenance markers on committable tactic options so the
    # agent is never misled about how an option arose or what it guarantees.
    report["provenance_stamped"] = attach_provenance(view)
    # Anything still missing markers is reported (FLAG) — should be empty now.
    report["provenance_flagged"] = [
        {"where": jp, "missing": miss} for jp, miss in provenance_flags(view)
    ]
    return report


# ── goal-dynamic panel ordering (ergonomics: highlight what drives the choice) ─
#
# "What matters" depends on the proof state. A stable skeleton keeps the agent
# oriented (the situation header at the top, the support/menu at the bottom);
# only the DECISION CLUSTER — the synthesized options plus the structural
# surfaces — is reordered by the current proof layer, so the surfaces that drive
# the next semantic move come first. Nothing decision-relevant is dropped; the
# ordering only changes prominence.

# Stable top, in work-continuity order: what my last action produced, then what
# I'm proving now, then where I am overall. After acting, the first question is
# "what did that do?" — so the result of the last move leads, the refreshed goal
# follows, and the orienting status sits third.
PANEL_SITUATION = ("last_result", "current_goal", "proof_status")
# The synthesized options always lead the decision cluster.
PANEL_DECISION_LEAD = ("candidate_moves",)
# Structural surfaces — reordered by layer (default = generic relational order).
PANEL_STRUCTURAL = (
    "program_frontier", "call_site_surface", "seq_cut_surface", "pure_tail_surface")
# Per-layer: the surface that drives the move at that layer comes first; the rest
# still follow (a call goal leads with call_site_surface, a seq goal with
# seq_cut_surface, etc.). Keyed on proof_status.current_layer / view_focus.
PANEL_STRUCTURAL_BY_LAYER = {
    "call_site": ("call_site_surface", "program_frontier",
                  "seq_cut_surface", "pure_tail_surface"),
    "seq_cut": ("seq_cut_surface", "program_frontier",
                "call_site_surface", "pure_tail_surface"),
    "pure_tail": ("pure_tail_surface", "program_frontier",
                  "call_site_surface", "seq_cut_surface"),
    "prhl_module": ("program_frontier", "call_site_surface",
                    "seq_cut_surface", "pure_tail_surface"),
}
# Support + stable footer (menu / undo).
PANEL_SUPPORT = ("application_context", "facts_and_diagnostics")
PANEL_FOOTER = ("inspect_lookup_handles", "structural_checkpoints")
# Machine config — no value for choosing the next semantic move; hidden.
PANEL_DROP = ("surface_profile",)

# Machine-only size bookkeeping — pure noise for the agent's choice. (Status
# booleans like `truncated` / `text_fully_shown` are kept; they are a real
# "there is more to see" signal, not a count.)
_MACHINE_METADATA_KEYS = frozenset({
    "line_count", "shown_lines", "char_count", "shown_chars",
})


def _layer_key(view: dict[str, Any]) -> str:
    ps = _dict(view.get("proof_status"))
    candidates = (
        str(ps.get("current_layer") or "").strip().lower(),
        str(ps.get("view_focus") or "").strip().lower(),
        str(_dict(view.get("current_goal")).get("view_focus") or "").strip().lower(),
    )
    for key in candidates:
        if key in PANEL_STRUCTURAL_BY_LAYER:
            return key
    return ""


def panel_order_for(view: dict[str, Any], *, pin_last: "tuple[str, ...]" = ()) -> "list[str]":
    """Goal-dynamic panel order for the present panels of ``view``.

    Stable situation header + decision cluster (options first, then the
    layer-relevant structural surfaces) + support + stable footer; ``pin_last``
    (e.g. audit/metadata keys) and any present-but-unlisted panel are preserved
    (the latter just before the footer) so nothing is lost. ``PANEL_DROP`` panels
    are omitted. Only the decision cluster's order changes with the proof layer.
    """
    if not isinstance(view, dict):
        return []
    struct = PANEL_STRUCTURAL_BY_LAYER.get(_layer_key(view), PANEL_STRUCTURAL)
    head = (list(PANEL_SITUATION) + list(PANEL_DECISION_LEAD)
            + list(struct) + list(PANEL_SUPPORT))
    foot = list(PANEL_FOOTER)
    reserved = set(head) | set(foot) | set(PANEL_DROP) | set(pin_last)
    leftovers = [k for k in view.keys() if k not in reserved]
    sequence = head + leftovers + foot + list(pin_last)
    out: list[str] = []
    seen: set[str] = set()
    for k in sequence:
        if k in view and k not in seen and k not in PANEL_DROP:
            out.append(k)
            seen.add(k)
    return out


def strip_machine_metadata(node: Any) -> Any:
    """Recursively drop machine-only size counts (line/char counts). Status
    flags (``truncated``, ``text_fully_shown``) are kept. Mutates + returns."""
    if isinstance(node, dict):
        for k in list(node.keys()):
            if k in _MACHINE_METADATA_KEYS:
                del node[k]
            else:
                strip_machine_metadata(node[k])
    elif isinstance(node, list):
        for item in node:
            strip_machine_metadata(item)
    return node
