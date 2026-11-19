"""Puerto de salida: Incidentes necesita ubicar puntos en la red vial (otro contexto)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class UbicadorEnRed(ABC):
    @abstractmethod
    def ubicar(self, x: float, y: float, k: int = 2) -> int: ...

    @abstractmethod
    def limites(self) -> dict: ...
