from dataclasses import dataclass
from typing import ClassVar

from app.shared.kernel.eventos import EventoDeDominio


@dataclass(frozen=True, kw_only=True)
class IncidenteRegistrado(EventoDeDominio):
    tipo: ClassVar[str] = "incidente"
    incidente: str
    prioridad: str
