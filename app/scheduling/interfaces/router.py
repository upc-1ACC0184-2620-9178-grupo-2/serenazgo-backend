from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.scheduling.application.servicio_plan import ServicioPlan
from app.shared.kernel.prioridad import Prioridad


class EscenarioIn(BaseModel):
    n_serenazgos: int = Field(100, ge=1, le=500)
    n_eventos: int = Field(300, ge=0, le=1000)
    horas: float = Field(8.0, ge=8.0, le=24.0)         # al menos 8 horas
    inicio: datetime | None = None
    semilla: int = 42
    estrategia: str = "rapida"
    pct_programados: float | None = Field(None, ge=0.0, le=1.0)   # parte de la agenda conocida de antemano
    tiempo_real: bool = True                  # el turno sigue la hora de Lima y los eventos llegan solos
    eventos_por_hora: float = Field(40.0, ge=0, le=600)
    velocidad: float = Field(1.0, ge=1, le=600)        # 1 = hora real; >1 = demo acelerada


class RelojIn(BaseModel):
    minutos: float = Field(gt=0, le=1440)


class VelocidadIn(BaseModel):
    velocidad: float = Field(ge=1, le=600)


class EventoIn(BaseModel):
    tipologia: str = Field(min_length=3, max_length=80)
    direccion: str = Field(min_length=3, max_length=120)
    prioridad: Literal["A", "M", "B"]
    x: float
    y: float
    duracion_min: float | None = Field(None, gt=0, le=480)


class EstrategiaIn(BaseModel):
    nombre: str


class SiIn(BaseModel):
    tipo: Literal["cancelar_evento", "baja_serenazgo"]
    evento_id: int | None = None
    serenazgo_id: int | None = None


def crear_router(plan: ServicioPlan, lock: RLock) -> APIRouter:
    r = APIRouter(prefix="/api/plan", tags=["Planificación de turno"])

    @r.get("")
    def vista():
        with lock:
            return plan.vista()

    @r.post("/escenario")
    def escenario(d: EscenarioIn):
        with lock:
            plan.crear_escenario(d.n_serenazgos, d.n_eventos, d.horas, d.inicio, d.semilla, d.estrategia,
                                d.pct_programados, d.tiempo_real, d.eventos_por_hora, d.velocidad)
            return plan.vista()

    @r.post("/reloj")
    def reloj(d: RelojIn):
        with lock:
            return plan.avanzar_reloj(d.minutos)

    @r.post("/velocidad")
    def velocidad(d: VelocidadIn):
        with lock:
            return plan.cambiar_velocidad(d.velocidad)

    @r.post("/eventos", status_code=201)
    def registrar(d: EventoIn):
        with lock:
            return plan.registrar_evento(d.tipologia, d.direccion, Prioridad(d.prioridad), d.x, d.y, d.duracion_min)

    @r.post("/eventos/{evento_id}/cancelar")
    def cancelar(evento_id: int):
        with lock:
            return plan.cancelar_evento(evento_id)

    @r.post("/serenazgos/{serenazgo_id}/baja")
    def baja(serenazgo_id: int):
        with lock:
            return plan.baja_serenazgo(serenazgo_id)

    @r.get("/serenazgos/{serenazgo_id}/ruta")
    def ruta(serenazgo_id: int):
        with lock:
            return {"serenazgo_id": serenazgo_id, "ruta": plan.serenazgo_ruta(serenazgo_id)}

    @r.post("/optimizar")
    def optimizar():
        with lock:
            return plan.optimizar()

    @r.post("/estrategia")
    def estrategia(d: EstrategiaIn):
        with lock:
            return plan.cambiar_estrategia(d.nombre)

    @r.get("/estrategias/comparar")
    def comparar():
        with lock:
            return plan.comparar_estrategias()

    @r.post("/redistribuir")
    def redistribuir():
        with lock:
            return plan.redistribuir()

    @r.post("/que-pasa-si")
    def que_pasa_si(d: SiIn):
        with lock:
            return plan.que_pasa_si(d.tipo, d.evento_id, d.serenazgo_id)

    return r
