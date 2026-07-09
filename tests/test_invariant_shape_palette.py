"""Tests for the invariant-shape vocabulary palette (lamp b).

Show, from real in-scope predicates, that an invariant conjunct can be a guarded
implication / size bound / domain fact — possibility space grouped by form, never
ranked as the answer.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis import ec_relational_invariant as R  # noqa: E402


def test_shape_classifier_buckets_bodies() -> None:
    assert R._invariant_shape_classes("size lbad1{2} <= nth0 => 0 = cbadi{2}") == [
        "guarded_implication", "size_or_count_bound",
    ]
    assert R._invariant_shape_classes("forall n c, (n,c) \\in mr1 => n \\in ls1") == [
        "guarded_implication", "domain_membership",
    ]
    assert R._invariant_shape_classes("size ls1 = size ls2") == ["size_or_count_bound"]
    assert R._invariant_shape_classes("a{1} = a{2}") == ["relational_equality"]


def test_palette_groups_by_form_and_marks_relevance(monkeypatch) -> None:
    monkeypatch.setattr(R, "relational_predicates", lambda _d: [
        {"name": "inv_lbad1_i", "body_preview": "size lbad1{2} <= nth0 => 0 = cbadi{2}"},
        {"name": "inv_dom", "body_preview": "forall n c, (n,c) \\in UFCMA_l.lbad1{1} => n \\in used{1}"},
        {"name": "inv_eq", "body_preview": "a{1} = a{2} /\\ b{1} = b{2}"},
        {"name": "inv_size", "body_preview": "size xs{1} = size xs{2}"},
    ])
    pal = R.invariant_shape_palette("/fake", "goal with UFCMA_l.lbad1{1} and cbadi{2}")
    classes = pal["classes"]
    # the missing-vocabulary shapes are present, from real example predicates
    assert {"inv_lbad1_i", "inv_dom"} <= {
        it["name"] for it in classes["guarded_implication"]
    }
    assert "inv_lbad1_i" in {it["name"] for it in classes["size_or_count_bound"]}
    assert "inv_eq" in {it["name"] for it in classes["relational_equality"]}
    # relevance only sorts; goal-relevant predicate floats first, not filtered out
    assert classes["guarded_implication"][0]["relevant"] is True
    assert pal["predicates_examined"] == 4


def test_palette_none_when_no_predicates(monkeypatch) -> None:
    monkeypatch.setattr(R, "relational_predicates", lambda _d: [])
    assert R.invariant_shape_palette("/fake", "goal") is None
