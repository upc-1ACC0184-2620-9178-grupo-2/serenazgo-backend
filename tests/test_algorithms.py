"""Verificación contra NetworkX (RNF05), como en la sección 4.8 del informe."""
import random

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.algorithms import asignar_ford_fulkerson, dijkstra
from app.graph_provider import SimulatedGraphProvider

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
    p = rng.choices("AMB", weights=[20, 50, 30], k=n_i)
    return t, p


def _flujo_ref(t, n_u, n_i):
    g = nx.DiGraph()
    for u in range(n_u):
        g.add_edge("S", ("u", u), capacity=1)
        for i in range(n_i):
            if t[u][i] <= TMAX:
                g.add_edge(("u", u), ("i", i), capacity=1)
    for i in range(n_i):
        g.add_edge(("i", i), "T", capacity=1)
    return nx.maximum_flow_value(g, "S", "T") if "T" in g and "S" in g else 0


def test_flujo_maximo_y_emparejamiento_valido():
    rng = random.Random(1)
    for _ in range(100):
        t, p = _escenario(rng)
        pares, flujo = asignar_ford_fulkerson(t, p, UMBRALES, TMAX)
        assert flujo == len(pares) == _flujo_ref(t, len(t), len(p))
        assert len({u for u, _ in pares}) == len(pares)
        assert len({i for _, i in pares}) == len(pares)
        assert all(t[u][i] <= TMAX for u, i in pares)


def test_prioridad_alta_no_pierde_cobertura():
    """Con una sola unidad y dos incidentes alcanzables, gana el de prioridad alta."""
    t = [[8.0, 8.0]]
    pares, _ = asignar_ford_fulkerson(t, ["B", "A"], UMBRALES, TMAX)
    assert pares == [(0, 1)]


def test_api_flujo_completo():
    from app.main import app
    c = TestClient(app)
    a = c.get("/api/asignacion").json()
    assert a["metricas"]["atendibles"] == len(a["asignaciones"])
    primera = a["asignaciones"][0]
    r = c.post("/api/asignacion/confirmar", json={"pares": [
        {"incidente_id": primera["incidente_id"], "unidad_id": primera["unidad_id"],
         "tiempo": primera["tiempo"]}]})
    assert r.status_code == 200
    # confirmar de nuevo la misma unidad debe fallar
    r = c.post("/api/asignacion/confirmar", json={"pares": [
        {"incidente_id": primera["incidente_id"], "unidad_id": primera["unidad_id"]}]})
    assert r.status_code == 409
    assert c.get("/api/red").json()["n_nodos"] >= 1503
