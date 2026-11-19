from dataclasses import dataclass
from typing import ClassVar

from app.shared.kernel.eventos import EventoDeDominio


@dataclass(frozen=True, kw_only=True)
class RecomendacionCalculada(EventoDeDominio):
    tipo: ClassVar[str] = "recomendacion"
    atendibles: int
    sin_cobertura: int
    tiempo_medio: float


@dataclass(frozen=True, kw_only=True)
class AsignacionConfirmada(EventoDeDominio):
    """Evento de integración: Incidentes marca el caso atendido y Flota ocupa la unidad."""
    tipo: ClassVar[str] = "confirmacion"
    incidente_id: str
    unidad_id: int
    unidad: str
    tiempo: float | None
    modificada: bool
    operador: str


@dataclass(frozen=True, kw_only=True)
class IncidentesEscalados(EventoDeDominio):
    tipo: ClassVar[str] = "escalamiento"
    incidentes: tuple[str, ...]
