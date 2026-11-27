"""Patrullaje (serenazgos "afuera"), tráfico por horarios y asignación al que llega antes."""
import statistics
from datetime import datetime, timedelta

import pytest

from app.container import Contenedor
from app.scheduling.domain.modelos import Evento
from app.scheduling.domain.planificador import Planificador
from app.shared.kernel.prioridad import Prioridad
from app.shared.kernel.trafico import LIBRE, trafico_a_las


class Reloj:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


# ------------------------------------------------------------------ tráfico por horarios
def test_el_trafico_depende_de_la_hora_y_pega_mas_a_las_avenidas():
    madrugada, punta, noche = (trafico_a_las(datetime(2026, 11, 20, h)) for h in (3, 8, 22))
    assert madrugada == LIBRE and madrugada.nivel == "fluido"
    assert punta.nivel == "hora punta" and punta.arterial > punta.local > 1.0
    assert 1.0 < noche.arterial < punta.arterial


def test_los_tiempos_de_viaje_son_mayores_en_hora_punta():
    c = Contenedor()
    nodo = c.flota.bases()[1].nodo
    libre = c.red.caminos_desde(nodo, LIBRE).dist[:900]
    for hora, minimo, maximo in ((3, 1.0, 1.0), (8, 1.4, 2.1), (13, 1.1, 1.5)):
        d = c.red.caminos_desde(nodo, trafico_a_las(datetime(2026, 11, 20, hora))).dist[:900]
        razones = [b / a for a, b in zip(libre, d) if a > 1]
        assert minimo - 1e-9 <= statistics.mean(razones) <= maximo, hora
        assert all(b >= a - 1e-9 for a, b in zip(libre, d))              # nunca es más rápido que vía libre


def test_en_hora_punta_la_respuesta_es_peor_que_de_madrugada():
    def respuesta(h, m):
        svc = Contenedor(reloj=Reloj(datetime(2026, 11, 20, h, m))).plan
        return svc.vista()["metricas"]["respuesta_media_min"]
    assert respuesta(8, 30) > respuesta(3, 30)


def test_la_vista_informa_el_trafico_del_momento():
    v = Contenedor(reloj=Reloj(datetime(2026, 11, 20, 8, 15))).plan.vista()
    assert v["turno"]["trafico"]["nivel"] == "hora punta" and v["turno"]["trafico"]["arterial"] > 1.8


# ------------------------------------------------------------------ patrullaje
def test_los_serenazgos_salen_de_las_bases_a_puestos_repartidos_por_ventanilla():
    reloj = Reloj(datetime(2026, 11, 20, 7, 0))
    c = Contenedor(reloj=reloj)
    plan = c.plan.plan()
    salidas = {sid: f[0] for sid, f in plan.fijas.items() if f and f[0].tipo == "reposicion"}
    assert len(salidas) >= 95 and len({t.nodo for t in salidas.values()}) >= 20      # varios puestos
    assert all(c.red.contiene(*c.red.coordenadas_de(t.nodo)) for t in salidas.values())   # dentro de Ventanilla
    reloj.t += timedelta(minutes=45)                                                 # ya están afuera
    c.plan.vista()
    bases = {s.nodo_base for s in plan.serenazgos.values()}
    en_base = sum(plan.estado_unidad(s.id)[0] in bases for s in plan.serenazgos.values())
    assert en_base <= 5
    v = c.plan.vista()
    assert sum(1 for s in v["serenazgos"] if s["puesto"]) >= 95
    assert all(s["puesto"]["minutos"] > 0 for s in v["serenazgos"] if s["puesto"])


def test_la_trayectoria_de_un_serenazgo_parte_de_su_base_pasa_por_el_puesto_y_sigue_a_sus_eventos():
    c = Contenedor(reloj=Reloj(datetime(2026, 11, 20, 10, 30)))
    plan = c.plan.plan()
    sid = max(plan.serenazgos, key=lambda i: len(plan.fijas[i]))
    ruta = c.plan.serenazgo_ruta(sid)
    base = c.red.coordenadas_de(plan.serenazgos[sid].nodo_base)
    assert ruta and ruta[0] == [round(base[0], 3), round(base[1], 3)]


def test_la_patrulla_se_reacomoda_sola_cada_20_minutos_en_tiempo_real():
    reloj = Reloj(datetime(2026, 11, 20, 9, 0))
    c = Contenedor(reloj=reloj)
    c.plan.vista()
    for _ in range(4):
        reloj.t += timedelta(minutes=25)
        c.plan.vista()
    tipos = [d["tipo"] for d in c.auditoria.listar(300)]
    assert tipos.count("redistribucion") >= 1


# ------------------------------------------------------------------ asignación al más rápido
@pytest.mark.parametrize("hora", [3, 8, 18])
def test_un_evento_nuevo_va_al_serenazgo_que_llega_antes_segun_el_trafico_del_momento(hora):
    """Con todos los serenazgos libres, el elegido es el de menor tiempo de viaje con el tráfico de esa hora
    (no el más cerca en línea recta), en toda la zona de Ventanilla."""
    reloj = Reloj(datetime(2026, 11, 20, hora, 20))
    c = Contenedor(reloj=reloj)
    c.plan.crear_escenario(100, 0, 8.0, None, 7, "rapida", tiempo_real=True, eventos_por_hora=0)
    plan = c.plan.plan()
    assert not plan.eventos
    for punto in range(5):                                  # cinco lugares distintos del distrito
        x, y = c.plan._gen._uniforme(plan.rng)
        r = c.plan.registrar_evento("Accidente de tránsito", "Av. principal", Prioridad.ALTA, x, y)
        e, sid = plan.eventos[r["evento_id"]], r["serenazgo_id"]
        pl = Planificador(c.plan._red, trafico=trafico_a_las(plan.turno.a_fecha(plan.ahora)))
        # viaje de cada serenazgo libre (antes de este evento) hasta el lugar
        previos = {s: plan.estado_unidad(s) for s in plan.serenazgos
                   if s == sid or (not plan.futuras[s] and not any(t.evento_id == e.id for t in plan.fijas[s]))}
        viajes = {s: pl.t(n, e.nodo) for s, (n, libre) in previos.items()}
        tarea = next(t for t in (*plan.fijas[sid], *plan.tareas_futuras[sid]) if t.evento_id == e.id)
        mejor_otro = min(v for s, v in viajes.items() if s != sid)
        assert tarea.llegada - tarea.salida <= mejor_otro + 1e-6, (punto, sid)
        plan.cancelar(e.id)                                  # libera para el siguiente punto
        Planificador(c.plan._red).resimular(plan)
