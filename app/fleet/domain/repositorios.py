from __future__ import annotations

from abc import ABC, abstractmethod

from app.fleet.domain.unidad import Base, Unidad


class UnidadRepository(ABC):
    @abstractmethod
    def todas(self) -> list[Unidad]: ...
    @abstractmethod
    def por_id(self, id_unidad: int) -> Unidad | None: ...
    @abstractmethod
    def guardar(self, unidad: Unidad) -> None: ...


class BaseRepository(ABC):
    @abstractmethod
    def todas(self) -> list[Base]: ...
    @abstractmethod
    def guardar(self, base: Base) -> None: ...
