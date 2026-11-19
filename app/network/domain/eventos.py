from dataclasses import dataclass
from typing import ClassVar

from app.shared.kernel.eventos import EventoDeDominio


@dataclass(frozen=True, kw_only=True)
class TramoBloqueado(EventoDeDominio):
    tipo: ClassVar[str] = "bloqueo"
    desde: int
    hasta: int


@dataclass(frozen=True, kw_only=True)
class RedRestablecida(EventoDeDominio):
    tipo: ClassVar[str] = "red_restablecida"
