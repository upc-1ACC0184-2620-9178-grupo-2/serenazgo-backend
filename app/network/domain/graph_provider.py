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

    def adyacencia_en(self, trafico) -> list[list[tuple[int, float]]]:
        """Adyacencia con los tiempos afectados por el tráfico (`Trafico`). Por defecto, vía libre."""
        return self.adyacencia()

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
    def contiene(self, x: float, y: float) -> bool:
        """true si el punto está dentro de la zona de operación (el distrito)."""

    @abstractmethod
    def region(self) -> list[tuple[float, float]] | None:
        """Contorno de la zona de operación en coordenadas del plano (o None si es un rectángulo)."""

    @abstractmethod
    def anclaje(self) -> tuple[float, float] | None:
        """(lat, lng) del origen del plano si el plano es un mapa local en km; None si ya es geográfico."""

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
