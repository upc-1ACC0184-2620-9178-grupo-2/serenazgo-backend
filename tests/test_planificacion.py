"""Planificación de turno: reloj, rutas multi-evento, cancelaciones, redistribución y estrategias."""
import itertools
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.container import Contenedor
from app.main import crear_app
from app.scheduling.domain.hungaro import asignacion_minima
from app.scheduling.domain.modelos import Turno
from app.shared.kernel.errores import Conflicto, Invalido


@pytest.fixture(scope="module")
def contenedor():
    return Contenedor()


@pytest.fixture()
def svc(contenedor):
    contenedor.plan.crear_escenario(100, 300, 8.0, datetime(2026, 11, 20, 8, 0), 7, "rapida")
    return contenedor.plan


def _invariantes(plan):
    for sid in plan.serenazgos:
        tareas = [*plan.fijas[sid], *plan.tareas_futuras[sid]]
        for a, b in zip(tareas, tareas[1:]):
            assert b.salida >= a.fin - 1e-6 or a.tipo == "cancelada", f"solape en serenazgo {sid}"
        assert all(t.fin <= plan.turno.duracion_min + 1e-6 for t in tareas), "fuera del turno"
    asig = plan.asignacion()
    assert len(asig) == len(set(asig)), "evento asignado dos veces"
    for e in plan.eventos.values():
        assert not (e.cancelado and e.id in asig and plan.indice()[e.id][1].tipo == "evento")


def test_turno_dura_al_menos_8_horas():
    assert Turno(datetime(2026, 1, 1, 8), 8).duracion_min == 480
    with pytest.raises(Invalido):
        Turno(datetime(2026, 1, 1, 8), 6)


def test_hungaro_igual_a_fuerza_bruta():
    import random
    rng = random.Random(3)
    for _ in range(100):
        n = rng.randint(1, 6)
        c = [[rng.randint(0, 20) for _ in range(n)] for _ in range(n)]
        r = asignacion_minima(c)
        assert sum(c[i][r[i]] for i in range(n)) == min(
            sum(c[i][p[i]] for i in range(n)) for p in itertools.permutations(range(n)))


def test_escenario_de_100_serenazgos_con_agenda(svc):
    plan = svc.plan()
    assert len(plan.serenazgos) == 100 and plan.turno.horas == 8
    assert plan.guion and plan.eventos                 # parte programada, parte por llegar
    assert plan.pendientes_sin_asignar() == []
    _invariantes(plan)


def test_dia_completo_cumple_invariantes_y_atiende_todo(svc):
    for _ in range(8):
        svc.avanzar_reloj(60)
    plan = svc.plan()
    m = plan.resumen()
    assert m["programados"] == 0 and m["atendidos"] + m["cancelados"] == 300
    assert m["sin_cobertura"] == 0
    _invariantes(plan)


def test_un_serenazgo_puede_tener_varios_eventos(svc):
    plan = svc.plan()
    por_unidad = {}
    for eid, sid in plan.asignacion().items():
        por_unidad.setdefault(sid, []).append(eid)
    assert any(len(v) > 1 for v in por_unidad.values())


def test_cancelar_evento_reasigna_y_libera(svc):
    plan = svc.plan()
    idx = plan.indice()
    futuro = next(e for e, (_, _, fija) in idx.items() if not fija)
    sid = idx[futuro][0]
    r = svc.cancelar_evento(futuro)
    assert plan.eventos[futuro].cancelado and futuro not in plan.asignacion()
    assert futuro not in plan.futuras[sid]
    _invariantes(plan)
    with pytest.raises(Conflicto):
        svc.cancelar_evento(futuro)                    # ya estaba cancelado
    assert isinstance(r["reasignados"], list)


def test_baja_de_serenazgo_reasigna_sus_eventos(svc):
    plan = svc.plan()
    sid = max(plan.serenazgos, key=lambda i: len(plan.futuras[i]))
    pendientes = list(plan.futuras[sid])
    assert pendientes
    svc.baja_serenazgo(sid)
    asig = plan.asignacion()
    assert not plan.serenazgos[sid].en_servicio and plan.futuras[sid] == []
    assert all(asig.get(e) != sid for e in pendientes)
    _invariantes(plan)


def test_que_pasa_si_no_toca_el_plan_real(svc):
    plan = svc.plan()
    sid = max(plan.serenazgos, key=lambda i: len(plan.futuras[i]))
    antes = dict(plan.asignacion())
    r = svc.que_pasa_si("baja_serenazgo", serenazgo_id=sid)
    assert r["tipo"] == "baja_serenazgo" and "antes" in r and "despues" in r
    assert plan.serenazgos[sid].en_servicio and plan.asignacion() == antes


def test_estrategias_dividen_los_eventos_de_forma_distinta(svc):
    c = svc.comparar_estrategias()
    assert c["concentrada"]["serenazgos_usados"] < c["rapida"]["serenazgos_usados"] \
        < c["equilibrada"]["serenazgos_usados"]
    assert c["equilibrada"]["carga_max_h"] < c["concentrada"]["carga_max_h"]


def test_redistribuir_acerca_a_los_libres_a_la_demanda(svc):
    for _ in range(3):
        svc.avanzar_reloj(60)
    r = svc.redistribuir()
    assert r["libres"] > 0 and r["movimientos"]
    assert r["tiempo_medio_despues"] <= r["tiempo_medio_antes"]
    assert r["cobertura_despues"] >= r["cobertura_antes"]
    _invariantes(svc.plan())


def test_api_plan_completo():
    c = TestClient(crear_app(Contenedor()))
    v = c.post("/api/plan/escenario", json={"n_serenazgos": 100, "n_eventos": 150, "semilla": 5, "tiempo_real": False}).json()
    assert len(v["serenazgos"]) == 100 and v["turno"]["horas"] == 8
    assert set(v) >= {"turno", "estrategia", "estrategias", "serenazgos", "eventos", "sin_cobertura", "bases", "metricas"}
    assert c.post("/api/plan/escenario", json={"horas": 6, "tiempo_real": False}).status_code == 422      # mínimo 8 h

    r = c.post("/api/plan/reloj", json={"minutos": 90}).json()
    assert r["hora"] == "09:30" or r["ahora_min"] == 90
    x, y = c.get("/api/red").json()["nodos"][0]
    ev = c.post("/api/plan/eventos", json={"tipologia": "Robo en vía pública", "direccion": "Calle 1",
                                          "prioridad": "A", "x": x, "y": y})
    assert ev.status_code == 201 and ev.json()["serenazgo_id"] is not None
    nuevo = ev.json()["evento_id"]
    assert c.post(f"/api/plan/eventos/{nuevo}/cancelar").status_code == 200
    assert c.post(f"/api/plan/eventos/{nuevo}/cancelar").status_code == 409
    assert c.post("/api/plan/eventos/99999/cancelar").status_code == 404

    sid = v["serenazgos"][0]["id"]
    assert c.get(f"/api/plan/serenazgos/{sid}/ruta").status_code == 200
    assert c.post("/api/plan/redistribuir").json()["libres"] >= 0
    assert set(c.get("/api/plan/estrategias/comparar").json()) == {"rapida", "equilibrada", "concentrada"}
    assert c.post("/api/plan/estrategia", json={"nombre": "equilibrada"}).status_code == 200
    assert c.post("/api/plan/estrategia", json={"nombre": "xx"}).status_code == 422
    assert c.post("/api/plan/que-pasa-si", json={"tipo": "baja_serenazgo", "serenazgo_id": sid}).status_code == 200
    tipos = {d["tipo"] for d in c.get("/api/decisiones").json()}
    assert {"plan_generado", "reloj", "evento_reportado", "evento_cancelado", "redistribucion"} <= tipos
