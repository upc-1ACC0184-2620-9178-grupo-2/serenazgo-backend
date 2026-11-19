"""API Composition (BFF): modelos de lectura que combinan varios contextos para la pantalla
de despacho. Solo lee; no contiene reglas de negocio."""
from __future__ import annotations

from fastapi import APIRouter

from app.dispatch.application.servicio_despacho import ServicioDespacho
from app.fleet.application.servicio_flota import ServicioFlota
from app.incidents.application.servicio_incidentes import ServicioIncidentes
from app.network.application.servicio_red_vial import ServicioRedVial
from app.simulation.application.servicio_escenario import ServicioEscenario


def crear_router(red: ServicioRedVial, flota: ServicioFlota, incidentes: ServicioIncidentes,
                 despacho: ServicioDespacho, escenario: ServicioEscenario) -> APIRouter:
    r = APIRouter(prefix="/api", tags=["Vista de despacho"])

    def bases() -> list[dict]:
        return [b.a_dict() for b in flota.bases()]

    @r.get("/red")  # RF05: G1 + bases
    def red_vial():
        return {**red.vista(), "bases": bases()}

    @r.get("/estado")
    def estado():
        pol = despacho.politica
        return {
            "ciclo": escenario.ciclo, "hora": escenario.hora, "tmax": pol.tmax,
            "umbrales": list(pol.umbrales), "tipologias": incidentes.tipologias(),
            "incidentes": [i.a_dict() for i in incidentes.activos()],
            "unidades": [u.a_dict() for u in flota.unidades()],
            "bases": bases(),
        }

    return r
