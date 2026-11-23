"""Casos de uso del contexto Incidentes (RF01, CU01)."""
from __future__ import annotations

import random

from app.incidents.domain.catalogo import TIPOLOGIAS
from app.incidents.domain.eventos import IncidenteRegistrado
from app.incidents.domain.incidente import Incidente
from app.incidents.domain.puertos import UbicadorEnRed
from app.incidents.domain.repositorio import IncidenteRepository
from app.shared.kernel.errores import Conflicto, Invalido
from app.shared.kernel.eventos import BusDeEventos
from app.shared.kernel.prioridad import Prioridad


class ServicioIncidentes:
    def __init__(self, repo: IncidenteRepository, ubicador: UbicadorEnRed, bus: BusDeEventos):
        self._repo = repo
        self._ubicador = ubicador
        self._bus = bus
        self._llegada = 0
        self._manuales = 0

    # --- consultas ---
    def tipologias(self) -> list[str]:
        return list(TIPOLOGIAS)

    def activos(self) -> list[Incidente]:
        return [i for i in self._repo.todos() if i.activo]

    def esta_activo(self, id_caso: str) -> bool:
        i = self._repo.por_id(id_caso)
        return bool(i and i.activo)

    # --- comandos ---
    def registrar(self, tipologia: str, direccion: str, prioridad: Prioridad,
                  x: float, y: float) -> Incidente:
        if not self._ubicador.contiene(x, y):
            raise Invalido("La ubicación está fuera de Ventanilla (otro distrito o el mar).")
        nodo = self._ubicador.ubicar(x, y, 2)
        self._manuales += 1
        self._llegada += 1
        inc = Incidente.reportado(self._manuales, tipologia, direccion, prioridad, x, y, nodo,
                                  self._llegada)
        self._repo.guardar(inc)
        self._bus.publicar(IncidenteRegistrado(incidente=inc.id_caso, prioridad=prioridad.value))
        return inc

    def cargar(self, incidente: Incidente) -> None:
        """Carga masiva (escenario de simulación)."""
        self._repo.guardar(incidente)

    def abrir_ciclo(self, rng: random.Random, n_activos: int) -> None:
        """Nuevo ciclo: deja activos n incidentes al azar."""
        pool = self._repo.todos()
        for i in pool:
            i.desactivar()
        for k, i in enumerate(rng.sample(pool, min(n_activos, len(pool)))):
            i.activar(k)
        for i in pool:
            self._repo.guardar(i)
        self._llegada = n_activos

    def marcar_atendido(self, id_caso: str) -> None:
        i = self._repo.por_id(id_caso)
        if i is None:
            raise Conflicto(f"El incidente {id_caso} no está activo.")
        i.marcar_atendido()
        self._repo.guardar(i)
