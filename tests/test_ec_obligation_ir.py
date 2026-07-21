from core.easycrypt.analysis.ec_obligation_ir import (
    build_proof_obligation_ir,
    local_order_chains,
    named_local_hypotheses,
    obligation_is_trivial,
    one_sided_program_obligation,
)


def _goal(body: str) -> str:
    return "Current goal\n----------------------------------------\n" + body


def test_equivalence_is_not_split_as_implication() -> None:
    ir = build_proof_obligation_ir(_goal(
        "forall &1 &2, PRE => check_plaintext L{1} p{1} <=> check_plaintext L{2} p{2}"
    ))
    assert [part.kind for part in ir.binders] == ["forall_binder"]
    assert [part.kind for part in ir.premises] == ["proposition"]
    assert ir.conclusion.kind == "equivalence"
    assert not ir.conclusion_parts


def test_internal_equalities_do_not_change_outer_shape() -> None:
    ir = build_proof_obligation_ir(_goal(
        "forall x, (let y = x in y = x) => if x = x then P x else Q x"
    ))
    assert ir.premises[0].kind == "let_expression"
    assert ir.conclusion.kind == "conditional"


def test_implication_conclusion_is_split_into_mechanical_obligations() -> None:
    ir = build_proof_obligation_ir(_goal(
        "r = iter n f s => p <> [] => r = iter (n + 1) f s' /\\ size (drop k p) < size p"
    ))
    assert [part.kind for part in ir.premises] == ["iter_equality", "nonempty_list"]
    assert [part.kind for part in ir.conclusion_parts] == [
        "iter_equality",
        "size_drop_inequality",
    ]


def test_conjunction_with_inner_order_is_not_mislabeled_as_order() -> None:
    ir = build_proof_obligation_ir(_goal(
        "P /\\ size xs <= n /\\ Q => R /\\ size ys < size xs"
    ))
    assert [part.kind for part in ir.premises] == ["conjunction"]
    assert ir.conclusion.kind == "conjunction"
    assert [part.kind for part in ir.conclusion_parts] == [
        "proposition",
        "order",
    ]


def test_disjunction_with_inner_equality_is_not_mislabeled_as_equality() -> None:
    ir = build_proof_obligation_ir(_goal("x = y \\/ P x"))
    assert ir.conclusion.kind == "disjunction"


def test_binder_inside_implication_scopes_the_remaining_chain() -> None:
    ir = build_proof_obligation_ir(_goal(
        "A => forall (v : D), v \\in dD => P v /\\ Q v => R v"
    ))
    assert [part.text for part in ir.binders] == ["forall (v : D)"]
    assert [part.kind for part in ir.premises] == [
        "proposition",
        "membership",
        "conjunction",
    ]
    assert ir.conclusion.text == "R v"


def test_ambiguous_atomic_proposition_is_not_called_equality() -> None:
    ir = build_proof_obligation_ir(_goal("forall x, P (f x = x)"))
    assert ir.conclusion.kind == "unknown"


def test_named_multiline_hypotheses_and_exact_order_chain() -> None:
    goal = """Current goal
x y z : real
Hxy :
  x <= y
Hyz : y <= z
----------------------------------------
x <= z
"""
    hypotheses = named_local_hypotheses(goal)
    assert [item["hypothesis"] for item in hypotheses] == ["Hxy", "Hyz"]
    assert local_order_chains(goal) == [{
        "premises": ["Hxy", "Hyz"],
        "chain": ["x", "y", "z"],
        "relations": ["<=", "<=", "<="],
        "conclusion": "x <= z",
    }]


def test_similar_symbols_do_not_form_an_order_chain() -> None:
    goal = """Current goal
H1 : f x <= g y
H2 : f x <= h z
----------------------------------------
g y <= h z
"""
    assert local_order_chains(goal) == []


def test_trivial_goal_detection_is_outer_structure_only() -> None:
    assert obligation_is_trivial(_goal("forall x, x = x"))
    assert obligation_is_trivial(_goal("true"))
    assert not obligation_is_trivial(_goal("x < x"))
    assert not obligation_is_trivial(_goal("P (x = x)"))


def test_program_losslessness_obligation_requires_exact_phoare_shape() -> None:
    goal = """Current goal
Bound   : [=] 1%r

pre = true

x <- 0
while (x < 4) { x <- x + 1 }

post = true
"""
    obligation = one_sided_program_obligation(goal, goal_type="phoare")

    assert obligation["kind"] == "procedure_losslessness"
    assert obligation["bound_relation"] == "="
    assert obligation["bound_value"] == "1%r"

    assert one_sided_program_obligation(goal, goal_type="hoare") == {}
    assert one_sided_program_obligation(
        goal.replace("post = true", "post = res = 0"),
        goal_type="phoare",
    ) == {}
    assert one_sided_program_obligation(
        goal.replace("[=] 1%r", "[<=] 1%r"),
        goal_type="phoare",
    ) == {}
