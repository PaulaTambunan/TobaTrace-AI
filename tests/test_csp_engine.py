"""Pengujian mesin CSP generik (independen dari domain dokumen)."""
from src.csp_engine import CSP, SearchStats, ac3, backtracking_search


def _neq(x, y):
    return x != y


def australia():
    csp = CSP()
    for v in ["WA", "NT", "SA", "Q", "NSW", "V", "T"]:
        csp.add_variable(v, ["r", "g", "b"])
    for a, b in [("WA", "NT"), ("WA", "SA"), ("NT", "SA"), ("NT", "Q"), ("SA", "Q"),
                 ("SA", "NSW"), ("SA", "V"), ("Q", "NSW"), ("NSW", "V")]:
        csp.add_constraint(a, b, _neq, "beda_warna")
    return csp


def test_ac3_prunes_domains():
    csp = CSP()
    csp.add_variable("x", [1, 2, 3])
    csp.add_variable("y", [3])
    csp.add_constraint("x", "y", lambda x, y: x < y, "x<y")
    doms = {k: list(v) for k, v in csp.domains.items()}
    assert ac3(csp, doms) is True
    assert doms["x"] == [1, 2]


def test_ac3_detects_wipeout_and_names_constraint():
    csp = CSP()
    csp.add_variable("x", [5])
    csp.add_variable("y", [1, 2])
    csp.add_constraint("x", "y", lambda x, y: x < y, "x<y")
    st = SearchStats()
    doms = {k: list(v) for k, v in csp.domains.items()}
    assert ac3(csp, doms, st) is False
    assert st.wipeout[2] == "x<y"


def test_backtracking_solves_map_coloring():
    csp = australia()
    sol = backtracking_search(csp, {k: list(v) for k, v in csp.domains.items()})
    assert sol is not None and len(sol) == 7
    for (a, b), cons in csp._cons.items():
        assert sol[a] != sol[b]


def test_backtracking_unsat_returns_none():
    csp = CSP()
    for v in "abc":
        csp.add_variable(v, [1, 2])
    for a, b in [("a", "b"), ("b", "c"), ("a", "c")]:
        csp.add_constraint(a, b, _neq, "beda")
    assert backtracking_search(csp, {k: list(v) for k, v in csp.domains.items()}) is None


def test_mrv_uses_no_more_nodes_than_static_order():
    csp = CSP()
    csp.add_variable("big1", list(range(10)))
    csp.add_variable("big2", list(range(10)))
    csp.add_variable("tiny", [7])
    csp.add_constraint("big1", "tiny", lambda a, t: a == t, "eq")
    csp.add_constraint("big2", "tiny", lambda a, t: a == t, "eq")
    s1, s2 = SearchStats(), SearchStats()
    d = lambda: {k: list(v) for k, v in csp.domains.items()}
    backtracking_search(csp, d(), use_mrv=True, use_fc=False, stats=s1)
    backtracking_search(csp, d(), use_mrv=False, use_fc=False, stats=s2)
    assert s1.nodes <= s2.nodes


def test_optimize_branch_and_bound_finds_max_score():
    csp = CSP()
    csp.add_variable("a", [1, 2, 3])
    csp.add_variable("b", [1, 2, 3])
    csp.add_constraint("a", "b", lambda a, b: a != b, "neq")
    sol = backtracking_search(csp, {k: list(v) for k, v in csp.domains.items()},
                              score=lambda v, x: x, optimize=True)
    assert sorted(sol.values()) == [2, 3]


def test_node_limit_sets_timeout_flag():
    csp = australia()
    st = SearchStats()
    backtracking_search(csp, {k: list(v) for k, v in csp.domains.items()},
                        use_mrv=False, use_fc=False, node_limit=1, stats=st)
    assert st.timed_out


def test_duplicate_variable_and_self_constraint_rejected():
    import pytest
    csp = CSP()
    csp.add_variable("x", [1])
    with pytest.raises(ValueError):
        csp.add_variable("x", [2])
    with pytest.raises(ValueError):
        csp.add_constraint("x", "x", _neq, "n")
