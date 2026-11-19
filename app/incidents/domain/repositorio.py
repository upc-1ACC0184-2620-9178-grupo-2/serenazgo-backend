from __future__ import annotations

from abc import ABC, abstractmethod

from app.incidents.domain.incidente import Incidente


class IncidenteRepository(ABC):
    @abstractmethod
    def todos(self) -> list[Incidente]: ...
    @abstractmethod
    def por_id(self, id_caso: str) -> Incidente | None: ...
    @abstractmethod
    def guardar(self, incidente: Incidente) -> None: ...
