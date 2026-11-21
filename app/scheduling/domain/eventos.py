from dataclasses import dataclass
from typing import ClassVar

from app.shared.kernel.eventos import EventoDeDominio


@dataclass(frozen=True, kw_only=True)
class PlanGenerado(EventoDeDominio):
    tipo: ClassVar[str] = "plan_generado"
    serenazgos: int
    eventos: int
    estrategia: str


@dataclass(frozen=True, kw_only=True)
class EventoReportado(EventoDeDominio):
    tipo: ClassVar[str] = "evento_reportado"
    evento: int
    prioridad: str
    serenazgo: int | None


@dataclass(frozen=True, kw_only=True)
class EventoCancelado(EventoDeDominio):
    tipo: ClassVar[str] = "evento_cancelado"
    evento: int
    reasignados: int


@dataclass(frozen=True, kw_only=True)
class SerenazgoDadoDeBaja(EventoDeDominio):
    tipo: ClassVar[str] = "serenazgo_baja"
    serenazgo: int
    reasignados: int


@dataclass(frozen=True, kw_only=True)
class SerenazgosRedistribuidos(EventoDeDominio):
    tipo: ClassVar[str] = "redistribucion"
    movimientos: int
    cobertura_antes: float
    cobertura_despues: float


@dataclass(frozen=True, kw_only=True)
class RelojAvanzado(EventoDeDominio):
    tipo: ClassVar[str] = "reloj"
    minutos: float
    hora: str


@dataclass(frozen=True, kw_only=True)
class EstrategiaCambiada(EventoDeDominio):
    tipo: ClassVar[str] = "estrategia"
    nombre: str
