"""Modelo propio del contexto Despacho (lo que necesita saber de los demás contextos)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.shared.kernel.prioridad import Prioridad

FUERA_DE_ALCANCE = "fuera_de_alcance"
UNIDADES_INSUFICIENTES = "unidades_insuficientes"


# --- vistas de otros contextos (se obtienen por puertos) ---------------------
@dataclass(frozen=True)
class IncidenteADespachar:
    id_caso: str
    prioridad: Prioridad
    nodo_vial: int


@dataclass(frozen=True)
class UnidadDisponible:
    id: int
    etiqueta: str
    id_base: int


@dataclass(frozen=True)
class BaseOperativa:
    id: int
    nombre: str
    nodo: int


@dataclass(frozen=True)
class ResumenBase:
    id: int
    nombre: str
    total: int
    libres: int


class CaminosDesde(Protocol):
    """Caminos mínimos desde una base (los calcula el contexto Red vial)."""
    def tiempo_a(self, nodo: int) -> float: ...
    def ruta_a(self, nodo: int) -> list[list[float]]: ...


# --- resultado del despacho --------------------------------------------------
@dataclass(frozen=True)
class Alternativa:
    unidad_id: int
    unidad: str
    base_id: int
    base: str
    tiempo: float
    ruta: list[list[float]]


@dataclass(frozen=True)
class Asignacion:
    incidente_id: str
    unidad_id: int
    unidad: str
    base_id: int
    base: str
    tiempo: float
    ruta: list[list[float]]
    alternativas: list[Alternativa]


@dataclass(frozen=True)
class SinCobertura:
    incidente_id: str
    motivo: str


@dataclass(frozen=True)
class CargaDeBase:
    id: int
    nombre: str
    total: int
    libres: int
    asignaciones: int


@dataclass(frozen=True)
class Metricas:
    incidentes_activos: int
    atendibles: int
    unidades_disponibles: int
    unidades_total: int
    tiempo_medio: float
    flujo_maximo: int
    tmax: float
    calculo_ms: float = 0.0


@dataclass(frozen=True)
class Propuesta:
    """Raíz de agregado: recomendación de un ciclo. Invariante: una unidad atiende un
    solo incidente y un incidente recibe una sola unidad."""
    asignaciones: list[Asignacion]
    sin_cobertura: list[SinCobertura]
    por_base: list[CargaDeBase]
    metricas: Metricas

    def __post_init__(self) -> None:
        unidades = [a.unidad_id for a in self.asignaciones]
        incidentes = [a.incidente_id for a in self.asignaciones]
        if len(set(unidades)) != len(unidades) or len(set(incidentes)) != len(incidentes):
            raise ValueError("Propuesta inválida: unidad o incidente repetido.")


@dataclass(frozen=True)
class ParDeConfirmacion:
    incidente_id: str
    unidad_id: int
    tiempo: float | None = None
    modificada: bool = False
