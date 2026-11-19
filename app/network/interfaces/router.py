from __future__ import annotations

from threading import RLock

from fastapi import APIRouter
from pydantic import BaseModel

from app.network.application.servicio_red_vial import ServicioRedVial


class TramoIn(BaseModel):
    desde: int
    hasta: int


def crear_router(red: ServicioRedVial, lock: RLock) -> APIRouter:
    r = APIRouter(prefix="/api/red", tags=["Red vial"])

    @r.post("/bloqueo")  # RF07 / CU05
    def bloquear(t: TramoIn):
        with lock:
            red.bloquear_tramo(t.desde, t.hasta)
        return {"bloqueados": red.cantidad_bloqueados()}

    @r.delete("/bloqueo")
    def restablecer():
        with lock:
            red.restablecer()
        return {"bloqueados": 0}

    return r
