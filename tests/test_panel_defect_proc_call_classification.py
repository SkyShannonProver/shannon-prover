"""Panel-defect #1 root: a procedure-call frontier statement must NOT be summarized
as an absorbable `sp`/`wp` "setup statement".

See docs/reports/insights/l4_panel_defects_equiv_step4.md (Defect #1). The classifier
in core/easycrypt/session_prover_workspace_view.py placed proc calls (`ROout.set(..)`,
`Iter(Orcl).iter(..)`) into a setup region and `_setup_side_text` summarized them as
"N setup statement(s): …" advertised as sp/wp-absorbable. EC rejects sp/wp across a
proc call. The fix flags such statements as calls while preserving the literal
"N setup statement(s):" prefix the _leading_statement parser depends on.
"""
from __future__ import annotations

import re

from core.easycrypt import session_prover_workspace_view as V
from workflow import surface_panels as SC

_SETUP_PREFIX_RE = re.compile(r"^\d+\s+setup statement\(s\):")


def _setup_row_view(left: str):
    return {
        "program_frontier": {
            "frontier_alignment": {
                "rows": [
                    {
                        "role": "left-only setup",
                        "left": left,
                        "right": "",
                        "location": {"left_paths": [1, 2]},
                    }
                ]
            }
        }
    }


def test_statement_is_proc_call_detector() -> None:
    is_call = V.statement_is_procedure_call
    # Real proc calls (from the equiv_step4 evidence).
    assert is_call("ROout.set((n, C.ofintd 0), witness)")
    assert is_call("Iter(Orcl).iter(ns)")
    assert is_call("t <@ M.p(x)")
    # NOT calls.
    assert not is_call("i <- i + 1")
    assert not is_call("x <- C.ofintd 0")          # assignment whose RHS has a dotted op
    assert not is_call("while (c) { }")
    assert not is_call("")
    assert not is_call(None)


def test_setup_side_text_flags_proc_call_among_setup() -> None:
    # Two "setup" statements where the FIRST is actually a proc call.
    regions = [
        {"statement": "ROout.set((n, C.ofintd 0), witness)"},
        {"statement": "i <- i + 1"},
    ]
    text = V._setup_side_text(regions, absent="none")
    # The literal parser-contract prefix is preserved (regex at ~:3101 / surface).
    assert _SETUP_PREFIX_RE.match(text), text
    # And the proc-call fact is present without tactic advice.
    assert "procedure-call prefix:" in text, text
    assert "inline" not in text and "sp/wp" not in text, text
    assert "ROout.set" in text, text


def test_setup_side_text_single_proc_call_is_flagged() -> None:
    text = V._setup_side_text([{"statement": "Iter(Orcl).iter(ns)"}], absent="none")
    assert "procedure-call prefix:" in text, text
    assert "inline" not in text and "sp/wp" not in text, text
    assert "Iter(Orcl).iter(ns)" in text, text


def test_setup_side_text_plain_assignments_unchanged() -> None:
    # Regression: genuine assignments still read as plain setup, no call warning.
    single = V._setup_side_text([{"statement": "i <- i + 1"}], absent="none")
    assert single == "i <- i + 1"
    assert "procedure-call prefix:" not in single

    multi = V._setup_side_text(
        [{"statement": "i <- 0"}, {"statement": "j <- 1"}], absent="none"
    )
    assert _SETUP_PREFIX_RE.match(multi), multi
    assert "procedure-call prefix:" not in multi


def test_leading_statement_parser_still_extracts_head() -> None:
    # The downstream head parser must still recover the first statement from the
    # (now call-warned) setup summary.
    text = V._setup_side_text(
        [
            {"statement": "ROout.set((n, C.ofintd 0), witness)"},
            {"statement": "i <- i + 1"},
        ],
        absent="none",
    )
    head = V._leading_statement(text)
    assert head.startswith("ROout.set"), head


# --- Panel composition side (workflow.surface_panels._surgery_where) ---------
#
# The producer flags the call, and the agent-facing surgery panel renderer must
# keep that as structural evidence rather than tactic advice. For a multi-statement
# summary row whose concatenated text contains a proc call, statement_is_procedure_call
# on the whole summary short-circuits to False on the leading `<-` assignment, so
# the renderer must split per-statement.

_RECORDED_MULTI = "2 setup statement(s): UF.forged <- false; Iter(Orcl).iter(ns)"


def test_surgery_where_multi_statement_summary_with_call_not_sp_wp() -> None:
    # The exact shape the recorded equiv_step4 run produced.
    lines = SC._surgery_where(_setup_row_view(_RECORDED_MULTI))
    joined = "\n".join(lines)
    assert "absorb with `sp`/`wp`" not in joined, joined
    assert "procedure-call prefix" in joined, joined
    assert "inline" not in joined and "sp/wp" not in joined
    # The call statement must survive (not be truncated away).
    assert "Iter(Orcl).iter(ns)" in joined, joined


def test_surgery_where_multi_summary_with_producer_call_tag() -> None:
    # Same, but with a legacy producer "[call: ...]" tag present.
    tagged = (
        _RECORDED_MULTI
        + " [call: Iter(Orcl).iter(ns) — use inline/call, not sp/wp]"
    )
    joined = "\n".join(SC._surgery_where(_setup_row_view(tagged)))
    assert "absorb with `sp`/`wp`" not in joined, joined
    assert "procedure-call prefix" in joined and "Iter(Orcl).iter(ns)" in joined, joined
    assert "inline" not in joined and "sp/wp" not in joined


def test_surgery_where_multi_summary_with_new_producer_call_tag() -> None:
    tagged = (
        _RECORDED_MULTI
        + " [procedure-call prefix: Iter(Orcl).iter(ns)]"
    )
    joined = "\n".join(SC._surgery_where(_setup_row_view(tagged)))
    assert "procedure-call prefix" in joined and "Iter(Orcl).iter(ns)" in joined, joined
    assert "inline" not in joined and "sp/wp" not in joined


def test_surgery_where_assignment_only_summary_is_structural_setup_prefix() -> None:
    # Regression: a multi-statement summary of genuine assignments stays structural.
    joined = "\n".join(
        SC._surgery_where(_setup_row_view("2 setup statement(s): i <- 0; j <- 1"))
    )
    assert "assignment/setup prefix" in joined, joined
    assert "inline" not in joined and "sp/wp" not in joined


def test_render_surgery_skeleton_multi_summary_with_call() -> None:
    # End-to-end through the skeleton renderer the agent actually sees.
    skeleton = SC._render_surgery_skeleton(_setup_row_view(_RECORDED_MULTI))
    assert skeleton is not None
    where = "\n".join(skeleton.get("where") or [])
    assert "absorb with `sp`/`wp`" not in where, where
    assert "procedure-call prefix" in where and "Iter(Orcl).iter(ns)" in where, where
    assert "inline" not in where and "sp/wp" not in where
