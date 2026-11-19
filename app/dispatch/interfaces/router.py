from __future__ import annotations

from dataclasses import asdict
from threading import RLock

from fastapi import APIRouter
from pydantic import BaseModel

from app.dispatch.application.servicio_despacho import ServicioDespacho
from app.dispatch.domain.modelos import ParDeConfirmacion


class ParIn(BaseModel):
    incidente_id: str
    unidad_id: int
    tiempo: float | None = None
    modificada: bool = False


class ConfirmarIn(BaseModel):
    pares: list[ParIn]


class EscalarIn(BaseModel):
    incidentes: list[str]


def crear_router(despacho: ServicioDespacho, lock: RLock) -> APIRouter:
    r = APIRouter(prefix="/api", tags=["Despacho"])

    @r.get("/asignacion")  # RF03, RF04, RF08 / CU02
    def asignacion():
        with lock:
            return asdict(despacho.recomendar())

    @r.post("/asignacion/confirmar")  # RF06 / CU03
    def confirmar(d: ConfirmarIn):
        with lock:
            n = despacho.confirmar([ParDeConfirmacion(**p.model_dump()) for p in d.pares])
        return {"confirmadas": n}

    @r.post("/escalar")  # RF08
    def escalar(d: EscalarIn):
        return {"escalados": despacho.escalar(d.incidentes)}

    return r
