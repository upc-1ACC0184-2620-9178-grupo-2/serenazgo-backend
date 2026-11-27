"""Casos de uso del contexto Red vial (RF03, RF07, CU05)."""
from __future__ import annotations

from app.network.domain.eventos import RedRestablecida, TramoBloqueado
from app.network.domain.graph_provider import GraphProvider
from app.network.domain.shortest_path import CaminosMinimos, calcular_caminos
from app.shared.kernel.errores import NoEncontrado
from app.shared.kernel.eventos import BusDeEventos


class ServicioRedVial:
    def __init__(self, proveedor: GraphProvider, bus: BusDeEventos):
        self._p = proveedor
        self._bus = bus
        self._cache: dict[tuple, CaminosMinimos] = {}
        self._version = -1

    def limites(self) -> dict:
        return self._p.limites()

    def ubicar_punto(self, x: float, y: float, k: int = 2) -> int:
        return self._p.ubicar(x, y, k)

    def contiene(self, x: float, y: float) -> bool:
        return self._p.contiene(x, y)

    def nodo_cercano(self, x: float, y: float) -> int:
        return self._p.nodo_mas_cercano(x, y)

    def coordenadas_de(self, nodo: int) -> tuple[float, float]:
        return self._p.coordenadas()[nodo]

    def caminos_desde(self, nodo: int, trafico=None) -> CaminosMinimos:
        """Dijkstra desde `nodo` (con el tráfico de la hora si se indica), con caché que se invalida al cambiar la red."""
        if self._version != self._p.version:
            self._cache.clear()
            self._version = self._p.version
        clave = (nodo, trafico.clave if trafico else None)
        if clave not in self._cache:
            adj = self._p.adyacencia_en(trafico) if trafico else self._p.adyacencia()
            self._cache[clave] = calcular_caminos(adj, nodo)
        return self._cache[clave]

    def coordenadas_de_ruta(self, nodos: list[int]) -> list[list[float]]:
        xy = self._p.coordenadas()
        return [[round(xy[n][0], 3), round(xy[n][1], 3)] for n in nodos]

    def bloquear_tramo(self, desde: int, hasta: int) -> None:
        if not self._p.bloquear_tramo(desde, hasta):
            raise NoEncontrado("El tramo no existe o ya está bloqueado.")
        self._bus.publicar(TramoBloqueado(desde=desde, hasta=hasta))

    def restablecer(self) -> None:
        self._p.restablecer()
        self._bus.publicar(RedRestablecida())

    def cantidad_bloqueados(self) -> int:
        return len(self._p.bloqueados())

    def vista(self) -> dict:
        """Modelo de lectura de G1 para dibujar el mapa."""
        xy = self._p.coordenadas()
        n = self._p.n_intersecciones()
        return {
            "limites": self._p.limites(),
            "nodos": [[round(x, 3), round(y, 3)] for x, y in xy[:n]],
            "aristas": self._p.aristas_viales(),
            "bloqueados": self._p.bloqueados(),
            "n_nodos": self._p.n_nodos(),
            "n_aristas": self._p.n_aristas(),
            "anclaje": self._p.anclaje(),          # (lat, lng) del origen del plano, o None
            "distrito": self._p.region(),          # contorno del distrito en coordenadas del plano
        }
