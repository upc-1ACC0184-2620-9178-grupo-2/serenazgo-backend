"""Reloj en tiempo real (hora de Lima): el turno avanza solo y los eventos nuevos se integran."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.container import Contenedor
from app.main import crear_app
from app.scheduling.infrastructure.generador import inicio_de_turno
from app.shared.kernel.errores import Invalido


class Reloj:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def pasan(self, **kw):
        self.t += timedelta(**kw)


def _invariantes(plan):
    for sid in plan.serenazgos:
        tareas = [*plan.fijas[sid], *plan.tareas_futuras[sid]]
        for a, b in zip(tareas, tareas[1:]):
            assert b.salida >= a.fin - 1e-6 or a.tipo == "cancelada"
        assert all(t.fin <= plan.turno.duracion_min + 1e-6 for t in tareas)
    asig = plan.asignacion()
    assert len(asig) == len(set(asig))


def test_turnos_de_8_horas_segun_la_hora_de_lima():
    d = datetime(2026, 11, 20)
    esperado = {(5, 0): (19, 23), (7, 0): (20, 7), (10, 30): (20, 7), (14, 59): (20, 7), (15, 0): (20, 15),
                (22, 0): (20, 15), (23, 30): (20, 23), (0, 10): (19, 23)}
    for (h, m), (dia, hora) in esperado.items():
        i = inicio_de_turno(d.replace(hour=h, minute=m))
        assert (i.day, i.hour, i.minute) == (dia, hora, 0)


def test_el_plan_arranca_en_la_hora_real_y_recupera_lo_ocurrido():
    reloj = Reloj(datetime(2026, 11, 20, 10, 30))
    plan = Contenedor(reloj=reloj).plan.plan()
    assert plan.tiempo_real and plan.turno.inicio == datetime(2026, 11, 20, 7, 0)
    assert plan.ahora == pytest.approx(210, abs=0.01)                 # 10:30 son 210 min desde las 07:00
    assert plan.resumen()["atendidos"] > 0 and plan.resumen()["eventos_reportados"] > 50
    _invariantes(plan)


def test_con_el_paso_de_la_hora_real_se_integran_eventos_nuevos():
    reloj = Reloj(datetime(2026, 11, 20, 10, 30))
    svc = Contenedor(reloj=reloj).plan
    antes = svc.vista()["metricas"]["eventos_reportados"]
    hora0 = svc.vista()["turno"]["hora"]
    reloj.pasan(minutes=45)
    v = svc.vista()
    assert hora0 == "10:30" and v["turno"]["hora"] == "11:15"
    assert v["turno"]["ahora_min"] == pytest.approx(255, abs=0.01)
    assert v["metricas"]["eventos_reportados"] > antes                # llegaron accidentes, robos...
    nuevos = [e for e in v["eventos"] if e["reportado_min"] > 210]
    assert nuevos and all(e["estado"] != "sin_cobertura" for e in nuevos)
    assert {"Accidente de tránsito"} & {e["tipologia"] for e in v["eventos"]}
    _invariantes(svc.plan())


def test_si_no_pasa_el_tiempo_no_cambia_nada():
    reloj = Reloj(datetime(2026, 11, 20, 10, 30))
    svc = Contenedor(reloj=reloj).plan
    a = svc.vista()
    b = svc.vista()
    assert a["metricas"] == b["metricas"] and a["turno"]["ahora_min"] == b["turno"]["ahora_min"]


def test_al_terminar_el_turno_empieza_el_siguiente():
    reloj = Reloj(datetime(2026, 11, 20, 14, 50))
    svc = Contenedor(reloj=reloj).plan
    assert svc.vista()["turno"]["inicio"] == "2026-11-20T07:00"
    reloj.pasan(minutes=20)                                            # 15:10
    v = svc.vista()
    assert v["turno"]["inicio"] == "2026-11-20T15:00" and v["turno"]["hora"] == "15:10"
    assert len(v["serenazgos"]) == 100
    _invariantes(svc.plan())
    reloj.pasan(days=2, hours=3)                                       # servidor dormido: salta turnos
    assert svc.vista()["turno"]["hora"] == reloj().strftime("%H:%M")


def test_velocidad_acelera_el_reloj_para_demos():
    reloj = Reloj(datetime(2026, 11, 20, 8, 0))
    svc = Contenedor(reloj=reloj).plan
    svc.cambiar_velocidad(60)
    m0 = svc.vista()["turno"]["ahora_min"]
    reloj.pasan(minutes=2)                                             # 2 min reales = 120 min del plan
    assert svc.vista()["turno"]["ahora_min"] == pytest.approx(m0 + 120, abs=0.01)
    with pytest.raises(Invalido):
        svc.cambiar_velocidad(0)


def test_el_avance_manual_no_aplica_en_tiempo_real():
    svc = Contenedor(reloj=Reloj(datetime(2026, 11, 20, 10, 0))).plan
    with pytest.raises(Invalido):
        svc.avanzar_reloj(30)


def test_api_por_defecto_sigue_la_hora_real_de_lima():
    c = TestClient(crear_app(Contenedor()))
    v = c.post("/api/plan/escenario", json={"n_serenazgos": 100}).json()
    lima = datetime.now(timezone(timedelta(hours=-5))).replace(tzinfo=None)
    assert v["turno"]["tiempo_real"] is True and v["turno"]["zona_horaria"] == "Lima (UTC-5)"
    h, m = map(int, v["turno"]["hora"].split(":"))
    assert abs((h * 60 + m) - (lima.hour * 60 + lima.minute)) <= 2 or abs((h * 60 + m) - (lima.hour * 60 + lima.minute)) >= 1438
    assert c.post("/api/plan/reloj", json={"minutos": 30}).status_code == 422
    assert c.post("/api/plan/velocidad", json={"velocidad": 60}).status_code == 200
    assert c.get("/api/plan").json()["turno"]["velocidad"] == 60
    # el modo simulado sigue disponible
    s = c.post("/api/plan/escenario", json={"n_eventos": 100, "tiempo_real": False}).json()
    assert s["turno"]["tiempo_real"] is False and c.post("/api/plan/reloj", json={"minutos": 30}).status_code == 200
