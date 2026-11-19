from __future__ import annotations

from threading import RLock

from fastapi import APIRouter

from app.simulation.application.servicio_escenario import ServicioEscenario


def crear_router(escenario: ServicioEscenario, lock: RLock) -> APIRouter:
    r = APIRouter(prefix="/api/ciclo", tags=["Simulación"])

    @r.post("/nuevo")
    def nuevo_ciclo(semilla: int | None = None):
        with lock:
            return {"ciclo": escenario.nuevo_ciclo(semilla)}

    return r
