"""Todo lo que genera el sistema cae dentro del distrito de Ventanilla (no en el mar ni en otros distritos)."""
import pytest
from fastapi.testclient import TestClient

from app.container import Contenedor
from app.main import crear_app
from app.network.infrastructure.simulated_graph_provider import SimulatedGraphProvider


@pytest.fixture(scope="module")
def prov():
    return SimulatedGraphProvider()


def test_el_poligono_distingue_ventanilla_de_sus_vecinos_y_del_mar(prov):
    dentro = {"Ciudad Satélite": (-11.878, -77.127), "Pachacútec": (-11.832, -77.145)}
    fuera = {"Centro de Puente Piedra": (-11.8636, -77.0746), "Playa Costa Azul (mar)": (-11.8726, -77.159),
             "Mar abierto": (-11.87, -77.20), "Carabayllo": (-11.85, -77.03), "Callao (puerto)": (-12.05, -77.14)}
    for nombre, (la, lo) in dentro.items():
        assert prov.contiene(*prov.a_plano(la, lo)), nombre
    for nombre, (la, lo) in fuera.items():
        assert not prov.contiene(*prov.a_plano(la, lo)), nombre


def test_toda_la_red_vial_esta_dentro_del_distrito(prov):
    xy = prov.coordenadas()[: prov.n_intersecciones()]
    assert len(xy) == 900 and all(prov.contiene(x, y) for x, y in xy)


def test_incidentes_bases_y_eventos_del_plan_estan_dentro():
    c = Contenedor()
    assert all(c.red.contiene(i.x, i.y) for i in c.incidentes.activos())
    assert all(c.red.contiene(b.x, b.y) for b in c.flota.bases())
    plan = c.plan.plan()
    assert plan.eventos and all(c.red.contiene(e.x, e.y) for e in plan.eventos.values())
    assert all(c.red.contiene(*c.red.coordenadas_de(s.nodo_base)) for s in plan.serenazgos.values())
    for _ in range(3):                                   # los eventos en vivo también
        c.plan.crear_escenario(100, 200, 8.0, None, _, "rapida")
        assert all(c.red.contiene(e.x, e.y) for e in (*c.plan.plan().eventos.values(), *c.plan.plan().guion))


def test_la_api_rechaza_ubicaciones_fuera_de_ventanilla_y_publica_el_contorno():
    c = TestClient(crear_app(Contenedor()))
    red = c.get("/api/red").json()
    assert len(red["distrito"]) > 100 and red["anclaje"] and abs(red["anclaje"][0] + 11.88) < 0.02
    cuerpo = {"tipologia": "Robo en vía pública", "direccion": "Calle 1", "prioridad": "A"}
    lim = red["limites"]
    esquina = (lim["xmax"], lim["ymax"])                  # esquina del rectángulo: ya no es Ventanilla
    assert c.post("/api/incidentes", json={**cuerpo, "x": esquina[0], "y": esquina[1]}).status_code == 422
    assert c.post("/api/plan/eventos", json={**cuerpo, "x": esquina[0], "y": esquina[1]}).status_code == 422
