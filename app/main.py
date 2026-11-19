"""Punto de entrada de la API REST (el frontend Angular se ejecuta aparte).

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.audit.interfaces.router import crear_router as router_auditoria
from app.container import Contenedor
from app.dispatch.interfaces.router import crear_router as router_despacho
from app.fleet.interfaces.router import crear_router as router_flota
from app.incidents.interfaces.router import crear_router as router_incidentes
from app.network.interfaces.router import crear_router as router_red
from app.presentation.vista_despacho import crear_router as router_vista
from app.shared.kernel.errores import Conflicto, ErrorDeDominio, Invalido, NoEncontrado
from app.simulation.interfaces.router import crear_router as router_simulacion


def crear_app(c: Contenedor | None = None) -> FastAPI:
    c = c or Contenedor()
    app = FastAPI(title="Asignación de serenazgo - Ventanilla", version="3.0")

    origenes = os.getenv("ORIGENES_PERMITIDOS", "http://localhost:4200,http://127.0.0.1:4200").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origenes],
                       allow_methods=["*"], allow_headers=["*"])

    # errores de dominio -> HTTP (el frontend lee `detail`)
    for tipo, codigo in ((NoEncontrado, 404), (Conflicto, 409), (Invalido, 422), (ErrorDeDominio, 400)):
        def _manejador(_: Request, e: ErrorDeDominio, codigo: int = codigo):
            return JSONResponse(status_code=codigo, content={"detail": str(e)})
        app.add_exception_handler(tipo, _manejador)

    @app.get("/")
    def raiz():
        return {"servicio": "API de asignación de serenazgo", "docs": "/docs"}

    app.include_router(router_vista(c.red, c.flota, c.incidentes, c.despacho, c.escenario))
    app.include_router(router_red(c.red, c.lock))
    app.include_router(router_incidentes(c.incidentes, c.lock))
    app.include_router(router_flota(c.flota, c.lock))
    app.include_router(router_despacho(c.despacho, c.lock))
    app.include_router(router_auditoria(c.auditoria))
    app.include_router(router_simulacion(c.escenario, c.lock))
    app.state.contenedor = c
    return app


app = crear_app()
