"""Pruebas unitarias de dominio: sin servidor, sin base de datos."""
import pytest

from app.dispatch.domain.despachador import Despachador
from app.dispatch.domain.modelos import (
    BaseOperativa, IncidenteADespachar, Propuesta, ResumenBase, UnidadDisponible, Asignacion, Metricas,
)
from app.dispatch.domain.politica import PoliticaDePrioridad
from app.fleet.domain.unidad import Unidad
from app.incidents.domain.incidente import EstadoIncidente, Incidente
from app.shared.kernel.errores import Conflicto
from app.shared.kernel.eventos import BusDeEventos, EventoDeDominio
from app.shared.kernel.prioridad import Prioridad


def test_incidente_solo_se_atiende_si_esta_activo():
    i = Incidente("1", "Robo", "Calle 1", Prioridad.ALTA, 0, 0, 5)
    with pytest.raises(Conflicto):
        i.marcar_atendido()
    i.activar(0)
    i.marcar_atendido()
    assert i.estado == EstadoIncidente.ATENDIDO
    with pytest.raises(Conflicto):
        i.marcar_atendido()


def test_unidad_ocupada_no_puede_ocuparse_de_nuevo():
    u = Unidad(1, "Moto", 0)
    u.ocupar("A1")
    assert not u.disponible and u.incidente_asignado == "A1"
    with pytest.raises(Conflicto):
        u.ocupar("A2")
    u.cambiar_disponibilidad(True)
    assert u.incidente_asignado is None


def test_prioridad_ordena_de_mas_a_menos_urgente():
    assert [p.nivel for p in (Prioridad.ALTA, Prioridad.MEDIA, Prioridad.BAJA)] == [0, 1, 2]
    assert Prioridad("A") is Prioridad.ALTA


def test_bus_entrega_a_suscriptores_y_globales():
    class E(EventoDeDominio):
        pass
    visto = []
    bus = BusDeEventos()
    bus.suscribir(E, lambda e: visto.append("tipo"))
    bus.suscribir_todos(lambda e: visto.append("todos"))
    bus.publicar(E())
    assert visto == ["tipo", "todos"]


def test_propuesta_rechaza_unidad_repetida():
    a = Asignacion("1", 7, "M-07", 0, "B", 3.0, [], [])
    b = Asignacion("2", 7, "M-07", 0, "B", 4.0, [], [])
    with pytest.raises(ValueError):
        Propuesta([a, b], [], [], Metricas(2, 2, 1, 1, 3.5, 2, 10.0))


class _Caminos:
    def __init__(self, t): self._t = t
    def tiempo_a(self, nodo): return self._t[nodo]
    def ruta_a(self, nodo): return [[0.0, 0.0]]


def test_despachador_prefiere_alta_y_reporta_sin_cobertura():
    """1 unidad, 2 incidentes alcanzables: se cubre el de prioridad alta; el otro queda sin cobertura."""
    d = Despachador(PoliticaDePrioridad())
    p = d.proponer(
        [UnidadDisponible(1, "Moto M-01", 0)],
        [IncidenteADespachar("baja", Prioridad.BAJA, 0), IncidenteADespachar("alta", Prioridad.ALTA, 1),
         IncidenteADespachar("lejos", Prioridad.ALTA, 2)],
        [BaseOperativa(0, "Base Norte", 9)], {0: _Caminos({0: 2.0, 1: 8.0, 2: 30.0})},
        [ResumenBase(0, "Base Norte", 1, 1)], 1)
    assert [a.incidente_id for a in p.asignaciones] == ["alta"]
    motivos = {s.incidente_id: s.motivo for s in p.sin_cobertura}
    assert motivos == {"baja": "unidades_insuficientes", "lejos": "fuera_de_alcance"}
