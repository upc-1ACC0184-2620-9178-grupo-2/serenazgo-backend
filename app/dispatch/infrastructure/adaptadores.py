"""Anti-corruption layer: implementa los puertos de Despacho con los servicios de otros contextos."""
from __future__ import annotations

from app.dispatch.domain.modelos import (
    BaseOperativa, IncidenteADespachar, ResumenBase, UnidadDisponible,
)
from app.dispatch.domain.puertos import FlotaPort, IncidentesPort, RedVialPort
from app.fleet.application.servicio_flota import ServicioFlota
from app.incidents.application.servicio_incidentes import ServicioIncidentes
from app.network.application.servicio_red_vial import ServicioRedVial
from app.shared.kernel.errores import Conflicto


class _Caminos:
    """Adapta CaminosMinimos (Red vial) a lo que Despacho necesita: tiempo y ruta en coordenadas."""

    def __init__(self, red: ServicioRedVial, caminos):
        self._red, self._c = red, caminos

    def tiempo_a(self, nodo: int) -> float:
        return self._c.tiempo_a(nodo)

    def ruta_a(self, nodo: int) -> list[list[float]]:
        return self._red.coordenadas_de_ruta(self._c.ruta_a(nodo))


class RedVialAdapter(RedVialPort):
    def __init__(self, red: ServicioRedVial):
        self._red = red

    def caminos_desde(self, nodo: int):
        return _Caminos(self._red, self._red.caminos_desde(nodo))


class IncidentesAdapter(IncidentesPort):
    def __init__(self, incidentes: ServicioIncidentes):
        self._s = incidentes

    def activos(self):
        return [IncidenteADespachar(i.id_caso, i.prioridad, i.nodo_vial) for i in self._s.activos()]

    def verificar_activo(self, id_caso: str) -> None:
        if not self._s.esta_activo(id_caso):
            raise Conflicto(f"El incidente {id_caso} no está activo.")


class FlotaAdapter(FlotaPort):
    def __init__(self, flota: ServicioFlota):
        self._s = flota

    def disponibles(self):
        return [UnidadDisponible(u.id, u.etiqueta, u.id_base) for u in self._s.disponibles()]

    def bases(self):
        return [BaseOperativa(b.id, b.nombre, b.nodo) for b in self._s.bases()]

    def resumen_por_base(self):
        return [ResumenBase(**r) for r in self._s.resumen_por_base()]

    def total_unidades(self):
        return len(self._s.unidades())

    def verificar_disponible(self, id_unidad: int) -> UnidadDisponible:
        u = self._s.unidad_disponible(id_unidad)
        if u is None:
            raise Conflicto(f"La unidad {id_unidad} no está disponible.")
        return UnidadDisponible(u.id, u.etiqueta, u.id_base)
