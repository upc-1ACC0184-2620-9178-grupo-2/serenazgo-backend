"""Puertos de salida de Despacho: lo que necesita de los contextos vecinos."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.dispatch.domain.modelos import (
    BaseOperativa, CaminosDesde, IncidenteADespachar, ResumenBase, UnidadDisponible,
)


class RedVialPort(ABC):
    @abstractmethod
    def caminos_desde(self, nodo: int) -> CaminosDesde: ...


class IncidentesPort(ABC):
    @abstractmethod
    def activos(self) -> list[IncidenteADespachar]: ...

    @abstractmethod
    def verificar_activo(self, id_caso: str) -> None:
        """Lanza Conflicto si el incidente no está activo."""


class FlotaPort(ABC):
    @abstractmethod
    def disponibles(self) -> list[UnidadDisponible]: ...

    @abstractmethod
    def bases(self) -> list[BaseOperativa]: ...

    @abstractmethod
    def resumen_por_base(self) -> list[ResumenBase]: ...

    @abstractmethod
    def total_unidades(self) -> int: ...

    @abstractmethod
    def verificar_disponible(self, id_unidad: int) -> UnidadDisponible:
        """Lanza Conflicto si la unidad no está disponible."""
