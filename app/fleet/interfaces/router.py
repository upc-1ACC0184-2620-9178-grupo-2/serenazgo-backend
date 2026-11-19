from __future__ import annotations

from threading import RLock

from fastapi import APIRouter
from pydantic import BaseModel

from app.fleet.application.servicio_flota import ServicioFlota


class UnidadIn(BaseModel):
    disponible: bool


def crear_router(flota: ServicioFlota, lock: RLock) -> APIRouter:
    r = APIRouter(prefix="/api/unidades", tags=["Flota"])

    @r.patch("/{id_unidad}")  # RF02 / CU04
    def actualizar(id_unidad: int, d: UnidadIn):
        with lock:
            return flota.cambiar_disponibilidad(id_unidad, d.disponible).a_dict()

    return r
