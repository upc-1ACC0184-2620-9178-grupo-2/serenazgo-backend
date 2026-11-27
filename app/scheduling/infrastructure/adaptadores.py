"""Anti-corruption layer: implementa los puertos de Planificación con Red vial y Flota."""
from __future__ import annotations

from app.fleet.application.servicio_flota import ServicioFlota
from app.network.application.servicio_red_vial import ServicioRedVial
from app.scheduling.domain.puertos import BaseDePlan, BasesPort, RedViaPort


class RedViaAdapter(RedViaPort):
    def __init__(self, red: ServicioRedVial):
        self._red = red

    def tiempos_desde(self, nodo, trafico=None):
        return self._red.caminos_desde(nodo, trafico).dist

    def nodo_mas_cercano(self, x, y):
        return self._red.nodo_cercano(x, y)

    def coordenadas(self, nodo):
        return self._red.coordenadas_de(nodo)

    def limites(self):
        return self._red.limites()

    def contiene(self, x, y):
        return self._red.contiene(x, y)

    def contiene(self, x, y):
        return self._red.contiene(x, y)

    def ruta(self, origen, destino):
        return self._red.coordenadas_de_ruta(self._red.caminos_desde(origen).ruta_a(destino))


class BasesAdapter(BasesPort):
    def __init__(self, flota: ServicioFlota):
        self._f = flota

    def bases(self):
        return [BaseDePlan(b.id, b.nombre, b.x, b.y, b.nodo) for b in self._f.bases()]
