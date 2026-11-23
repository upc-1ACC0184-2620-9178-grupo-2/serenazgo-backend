"""Anti-corruption layer hacia el contexto Red vial."""
from __future__ import annotations

from app.incidents.domain.puertos import UbicadorEnRed
from app.network.application.servicio_red_vial import ServicioRedVial


class UbicadorRedAdapter(UbicadorEnRed):
    def __init__(self, red: ServicioRedVial):
        self._red = red

    def ubicar(self, x, y, k=2):
        return self._red.ubicar_punto(x, y, k)

    def limites(self):
        return self._red.limites()

    def contiene(self, x, y):
        return self._red.contiene(x, y)

    def contiene(self, x, y):
        return self._red.contiene(x, y)
