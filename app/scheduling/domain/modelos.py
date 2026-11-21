"""Modelo del contexto Planificación de turno: turno, eventos, serenazgos y tareas."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.shared.kernel.errores import Invalido
from app.shared.kernel.prioridad import Prioridad

HORAS_MINIMAS_TURNO = 8.0
A, M, B = Prioridad.ALTA, Prioridad.MEDIA, Prioridad.BAJA


@dataclass(frozen=True)
class Turno:
    """Jornada de trabajo. Regla de negocio: dura al menos 8 horas."""
    inicio: datetime
    horas: float = 8.0

    def __post_init__(self) -> None:
        if self.horas < HORAS_MINIMAS_TURNO:
            raise Invalido("El turno debe durar al menos 8 horas.")

    @property
    def fin(self) -> datetime:
        return self.inicio + timedelta(hours=self.horas)

    @property
    def duracion_min(self) -> float:
        return self.horas * 60

    def a_fecha(self, minutos: float) -> datetime:
        return self.inicio + timedelta(minutes=minutos)

    def a_minutos(self, fecha: datetime) -> float:
        return (fecha - self.inicio).total_seconds() / 60


@dataclass(frozen=True)
class ReglasDeAtencion:
    """Por prioridad: plazo objetivo de respuesta, espera máxima tolerable, duración y peso."""
    plazo_min: dict = field(default_factory=lambda: {A: 10.0, M: 20.0, B: 40.0})
    espera_max_min: dict = field(default_factory=lambda: {A: 30.0, M: 60.0, B: 120.0})
    duracion_min: dict = field(default_factory=lambda: {A: 30.0, M: 20.0, B: 12.0})
    peso: dict = field(default_factory=lambda: {A: 10.0, M: 3.0, B: 1.0})


@dataclass(frozen=True)
class EstrategiaDePlanificacion:
    """Cómo repartir los eventos: pesos de la función objetivo del planificador."""
    nombre: str
    descripcion: str
    peso_viaje: float          # costo por minuto de traslado
    peso_respuesta: float      # costo por minuto de respuesta (ponderado por prioridad)
    peso_balance: float        # penaliza la carga acumulada al cuadrado (reparte el trabajo)
    costo_activacion: float    # costo de usar un serenazgo que aún no trabajó (agrupa eventos)


ESTRATEGIAS = {
    "rapida": EstrategiaDePlanificacion(
        "rapida", "Minimiza el tiempo de respuesta: cada evento va a la unidad que llega antes.",
        1.0, 0.3, 0.0005, 0.0),
    "equilibrada": EstrategiaDePlanificacion(
        "equilibrada", "Reparte la carga: evita que unas unidades trabajen mucho y otras casi nada.",
        0.5, 0.2, 0.01, 0.0),
    "concentrada": EstrategiaDePlanificacion(
        "concentrada", "Agrupa eventos cercanos en pocas unidades (1 y 2 al serenazgo 1, 3 y 4 al 2) "
        "y deja las demás libres para patrullar.", 1.0, 0.1, 0.0, 60.0),
}

_LETRA = {"Camioneta": "C", "Auto": "A", "Moto": "M"}


@dataclass(eq=False)
class Serenazgo:
    id: int
    tipo: str
    id_base: int
    nodo_base: int
    en_servicio: bool = True

    @property
    def etiqueta(self) -> str:
        return f"{self.tipo} {_LETRA.get(self.tipo, 'S')}-{self.id:03d}"


@dataclass(eq=False)
class Evento:
    id: int
    tipologia: str
    direccion: str
    prioridad: Prioridad
    x: float
    y: float
    nodo: int
    reportado_en: datetime
    duracion_min: float
    plazo_min: float
    cancelar_en: datetime | None = None   # guion de la simulación: cuándo se cancelará
    cancelado: bool = False
    cancelado_en: datetime | None = None


@dataclass(frozen=True)
class Tarea:
    """Un tramo del día de un serenazgo. Tiempos en minutos desde el inicio del turno."""
    tipo: str                 # "evento" | "reposicion" | "cancelada"
    evento_id: int | None
    nodo: int
    salida: float
    llegada: float
    inicio: float
    fin: float
    retraso: float = 0.0      # minutos por encima del plazo objetivo
    respuesta: float = 0.0    # minutos desde el reporte hasta la llegada


@dataclass(frozen=True)
class Movimiento:
    serenazgo_id: int
    nodo_desde: int
    nodo_hasta: int
    minutos: float
