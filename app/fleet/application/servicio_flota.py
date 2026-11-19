"""Casos de uso del contexto Flota (RF02, CU04)."""
from __future__ import annotations

import random

from app.fleet.domain.eventos import UnidadActualizada
from app.fleet.domain.repositorios import BaseRepository, UnidadRepository
from app.fleet.domain.unidad import Base, Unidad
from app.shared.kernel.errores import NoEncontrado
from app.shared.kernel.eventos import BusDeEventos


class ServicioFlota:
    def __init__(self, unidades: UnidadRepository, bases: BaseRepository, bus: BusDeEventos):
        self._unidades = unidades
        self._bases = bases
        self._bus = bus

    # --- altas (las usa el escenario de simulación) ---
    def registrar_base(self, nombre: str, x: float, y: float, nodo: int) -> Base:
        b = Base(len(self._bases.todas()), nombre, x, y, nodo)
        self._bases.guardar(b)
        return b

    def registrar_unidad(self, tipo: str, id_base: int) -> Unidad:
        u = Unidad(len(self._unidades.todas()) + 1, tipo, id_base)
        self._unidades.guardar(u)
        return u

    # --- consultas ---
    def bases(self) -> list[Base]:
        return self._bases.todas()

    def unidades(self) -> list[Unidad]:
        return self._unidades.todas()

    def disponibles(self) -> list[Unidad]:
        return [u for u in self._unidades.todas() if u.disponible]

    def unidad_disponible(self, id_unidad: int) -> Unidad | None:
        u = self._unidades.por_id(id_unidad)
        return u if u and u.disponible else None

    def resumen_por_base(self) -> list[dict]:
        unidades = self._unidades.todas()
        return [{"id": b.id, "nombre": b.nombre,
                 "total": sum(1 for u in unidades if u.id_base == b.id),
                 "libres": sum(1 for u in unidades if u.id_base == b.id and u.disponible)}
                for b in self._bases.todas()]

    # --- comandos ---
    def cambiar_disponibilidad(self, id_unidad: int, disponible: bool) -> Unidad:
        u = self._unidades.por_id(id_unidad)
        if u is None:
            raise NoEncontrado("Unidad no encontrada.")
        u.cambiar_disponibilidad(disponible)
        self._unidades.guardar(u)
        self._bus.publicar(UnidadActualizada(unidad=u.etiqueta, disponible=disponible))
        return u

    def ocupar(self, id_unidad: int, id_incidente: str) -> None:
        u = self._unidades.por_id(id_unidad)
        if u is None:
            raise NoEncontrado("Unidad no encontrada.")
        u.ocupar(id_incidente)
        self._unidades.guardar(u)

    def sortear_disponibilidad(self, rng: random.Random, p: float) -> None:
        """Nuevo ciclo: cada unidad queda disponible con probabilidad p."""
        for u in self._unidades.todas():
            u.cambiar_disponibilidad(rng.random() < p)
            u.incidente_asignado = None
            self._unidades.guardar(u)
