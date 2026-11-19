from dataclasses import dataclass
from typing import ClassVar

from app.shared.kernel.eventos import EventoDeDominio


@dataclass(frozen=True, kw_only=True)
class UnidadActualizada(EventoDeDominio):
    tipo: ClassVar[str] = "unidad"
    unidad: str
    disponible: bool
