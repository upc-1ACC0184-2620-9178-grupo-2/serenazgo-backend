from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegistroDeDecision:
    ts: str
    tipo: str
    datos: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        return {"ts": self.ts, "tipo": self.tipo, **self.datos}


class AuditoriaRepository(ABC):
    @abstractmethod
    def agregar(self, registro: RegistroDeDecision) -> None: ...
    @abstractmethod
    def recientes(self, limite: int) -> list[RegistroDeDecision]: ...
