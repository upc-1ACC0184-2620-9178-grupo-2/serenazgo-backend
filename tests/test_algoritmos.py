"""Verificación contra NetworkX (RNF05), como en la sección 4.8 del informe."""
import random

import networkx as nx
import pytest

from app.dispatch.domain.asignador import asignar_ford_fulkerson
from app.network.domain.shortest_path import dijkstra
from app.network.infrastructure.simulated_graph_provider import SimulatedGraphProvider

UMBRALES, TMAX = (3, 5, 7, 9), 10.0


@pytest.fixture(scope="module")
def prov():
    return SimulatedGraphProvider()


def test_dijkstra_igual_a_networkx(prov):
    dist, _ = dijkstra(prov.adyacencia(), 0)
    ref = nx.single_source_dijkstra_path_length(prov.grafo, 0, weight="tiempo")
    assert len(ref) == prov.n_nodos()
    assert all(abs(dist[n] - ref[n]) < 1e-9 for n in ref)


def _escenario(rng, n_u=42, n_i=50):
    t = [[rng.uniform(0, 14) for _ in range(n_i)] for _ in range(n_u)]
    return t, rng.choices("AMB", weights=[20, 50, 30], k=n_i)


def _flujo_ref(t, n_u, n_i):
    g = nx.DiGraph()
    for u in range(n_u):
        g.add_edge("S", ("u", u), capacity=1)
        for i in range(n_i):
            if t[u][i] <= TMAX:
                g.add_edge(("u", u), ("i", i), capacity=1)
    for i in range(n_i):
        g.add_edge(("i", i), "T", capacity=1)
    return nx.maximum_flow_value(g, "S", "T")


def test_flujo_maximo_y_emparejamiento_valido():
    rng = random.Random(1)
    for _ in range(100):
        t, p = _escenario(rng)
        pares, flujo = asignar_ford_fulkerson(t, p, UMBRALES, TMAX, orden=("A", "M", "B"))
        assert flujo == len(pares) == _flujo_ref(t, len(t), len(p))
        assert len({u for u, _ in pares}) == len(pares)
        assert len({i for _, i in pares}) == len(pares)
        assert all(t[u][i] <= TMAX for u, i in pares)


def test_prioridad_alta_no_pierde_cobertura():
    pares, _ = asignar_ford_fulkerson([[8.0, 8.0]], ["B", "A"], UMBRALES, TMAX, orden=("A", "M", "B"))
    assert pares == [(0, 1)]
