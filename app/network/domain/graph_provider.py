"""Puerto del contexto Red vial: fuente del grafo G1 (RNF02).

La red simulada (NetworkX) o la real (OSMnx) se intercambian sin tocar los algoritmos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class GraphProvider(ABC):
    @property
    @abstractmethod
    def version(self) -> int:
        """Cambia cada vez que se modifica el grafo (invalida cachés)."""

    @abstractmethod
    def coordenadas(self) -> list[tuple[float, float]]: ...

    @abstractmethod
    def adyacencia(self) -> list[list[tuple[int, float]]]:
        """Lista de adyacencia [(vecino, tiempo_min), ...] por nodo."""

    @abstractmethod
    def aristas_viales(self) -> list[tuple[int, int]]:
        """Tramos de calle entre intersecciones (para dibujar el mapa)."""

    @abstractmethod
    def n_intersecciones(self) -> int: ...

    @abstractmethod
    def n_aristas(self) -> int: ...

    @abstractmethod
    def limites(self) -> dict: ...

    @abstractmethod
    def ubicar(self, x: float, y: float, k: int = 2) -> int:
        """Ubica un punto (base o incidente) en la red y devuelve su nodo."""

    @abstractmethod
    def nodo_mas_cercano(self, x: float, y: float) -> int:
        """Intersección más cercana al punto (no modifica el grafo)."""

    @abstractmethod
    def bloquear_tramo(self, a: int, b: int) -> bool: ...

    @abstractmethod
    def restablecer(self) -> None: ...

    @abstractmethod
    def bloqueados(self) -> list[tuple[int, int]]: ...

    def n_nodos(self) -> int:
        return len(self.coordenadas())
