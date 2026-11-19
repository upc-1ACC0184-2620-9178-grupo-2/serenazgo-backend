from __future__ import annotations

from threading import RLock
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.incidents.application.servicio_incidentes import ServicioIncidentes
from app.shared.kernel.prioridad import Prioridad


class IncidenteIn(BaseModel):
    tipologia: str = Field(min_length=3, max_length=80)
    direccion: str = Field(min_length=3, max_length=120)
    prioridad: Literal["A", "M", "B"]
    x: float
    y: float


def crear_router(incidentes: ServicioIncidentes, lock: RLock) -> APIRouter:
    r = APIRouter(prefix="/api/incidentes", tags=["Incidentes"])

    @r.post("", status_code=201)  # RF01 / CU01
    def registrar(d: IncidenteIn):
        with lock:
            return incidentes.registrar(d.tipologia, d.direccion, Prioridad(d.prioridad),
                                        d.x, d.y).a_dict()

    return r
