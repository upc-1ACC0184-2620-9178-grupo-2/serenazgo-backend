"""Puertos de salida de Planificación: lo que necesita de Red vial y Flota."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class BaseDePlan:
    id: int
    nombre: str
    x: float
    y: float
    nodo: int


class RedViaPort(ABC):
    @abstractmethod
    def tiempos_desde(self, nodo: int, trafico=None) -> list[float]:
        """Minutos mínimos desde `nodo` a todos los demás nodos (el grafo no es dirigido), con el tráfico de la hora."""

    @abstractmethod
    def nodo_mas_cercano(self, x: float, y: float) -> int: ...

    @abstractmethod
    def coordenadas(self, nodo: int) -> tuple[float, float]: ...

    @abstractmethod
    def limites(self) -> dict: ...

    @abstractmethod
    def contiene(self, x: float, y: float) -> bool:
        """true si el punto está dentro de Ventanilla."""

    @abstractmethod
    def contiene(self, x: float, y: float) -> bool:
        """true si el punto está dentro de Ventanilla."""

    @abstractmethod
    def ruta(self, origen: int, destino: int) -> list[list[float]]:
        """Polilínea [x, y] por las calles."""


class BasesPort(ABC):
    @abstractmethod
    def bases(self) -> list[BaseDePlan]: ...


class PlanRepository(ABC):
    @abstractmethod
    def obtener(self): ...

    @abstractmethod
    def guardar(self, plan) -> None: ...
