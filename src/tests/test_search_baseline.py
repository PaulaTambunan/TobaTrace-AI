"""
test_search_baseline.py
------------------------
Pengujian otomatis (pytest) untuk modul src/search_baseline.py.
Dijalankan dengan:  uv run pytest  (atau)  pytest -v
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from search_baseline import (  # noqa: E402
    GOAL_NODE,
    GRAPH,
    START_NODE,
    a_star_search,
    build_graph,
    haversine_km,
    heuristic,
    uniform_cost_search,
)


def test_graph_is_symmetric_undirected():
    """Setiap edge (a,b,c) harus punya pasangan (b,a,c) karena graf tidak berarah."""
    for node, neighbors in GRAPH.items():
        for neighbor, cost in neighbors:
            reverse_costs = [c for n, c in GRAPH[neighbor] if n == node]
            assert cost in reverse_costs, f"Edge {node}->{neighbor} tidak simetris"


def test_ucs_reaches_goal():
    result = uniform_cost_search(GRAPH, START_NODE, GOAL_NODE)
    assert result.path[0] == START_NODE
    assert result.path[-1] == GOAL_NODE
    assert result.total_cost > 0


def test_astar_reaches_goal():
    result = a_star_search(GRAPH, START_NODE, GOAL_NODE)
    assert result.path[0] == START_NODE
    assert result.path[-1] == GOAL_NODE
    assert result.total_cost > 0


def test_astar_cost_equals_ucs_cost_when_admissible():
    """A* dengan heuristik admissible wajib menghasilkan biaya optimal = UCS."""
    ucs = uniform_cost_search(GRAPH, START_NODE, GOAL_NODE)
    astar = a_star_search(GRAPH, START_NODE, GOAL_NODE)
    assert math.isclose(ucs.total_cost, astar.total_cost, rel_tol=1e-6)


def test_astar_explores_no_more_nodes_than_ucs():
    """Properti kunci A* dengan heuristik admissible & konsisten: tidak lebih boros dari UCS."""
    ucs = uniform_cost_search(GRAPH, START_NODE, GOAL_NODE)
    astar = a_star_search(GRAPH, START_NODE, GOAL_NODE)
    assert astar.nodes_expanded <= ucs.nodes_expanded


def test_heuristic_is_admissible_for_direct_neighbors():
    """
    Uji admissibility praktis: untuk setiap edge (a,b,cost) yang terhubung
    LANGSUNG ke goal, h(a) tidak boleh melebihi cost sebenarnya menuju goal.
    """
    for neighbor, cost in GRAPH[GOAL_NODE]:
        assert heuristic(neighbor, GOAL_NODE) <= cost + 1e-6


def test_heuristic_goal_is_zero():
    assert heuristic(GOAL_NODE, GOAL_NODE) == 0.0


def test_haversine_known_distance_jakarta_bandung():
    """Sanity check fungsi haversine dengan dua titik yang jaraknya sudah diketahui."""
    jakarta = (-6.2088, 106.8456)
    bandung = (-6.9175, 107.6191)
    dist = haversine_km(jakarta, bandung)
    # Jarak udara Jakarta-Bandung ~ 115-125 km
    assert 100 <= dist <= 140


def test_build_graph_creates_bidirectional_edges():
    """build_graph harus membuat edge dua arah dari satu definisi edge tak berarah."""
    edges = [("A", "B", 5.0), ("B", "C", 2.5)]
    graph = build_graph(edges)
    assert ("B", 5.0) in graph["A"]
    assert ("A", 5.0) in graph["B"]
    assert ("C", 2.5) in graph["B"]
    assert set(graph.keys()) == {"A", "B", "C"}


def test_no_route_raises_value_error():
    isolated_graph = {"X": [], "Y": []}
    import pytest

    with pytest.raises(ValueError):
        uniform_cost_search(isolated_graph, "X", "Y")