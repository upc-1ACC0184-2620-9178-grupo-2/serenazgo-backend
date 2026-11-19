from dataclasses import dataclass
from typing import ClassVar

from app.shared.kernel.eventos import EventoDeDominio


@dataclass(frozen=True, kw_only=True)
class CicloIniciado(EventoDeDominio):
    tipo: ClassVar[str] = "ciclo"
    ciclo: int
    activos: int
    disponibles: int
