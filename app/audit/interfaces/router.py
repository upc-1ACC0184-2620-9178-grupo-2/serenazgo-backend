from fastapi import APIRouter

from app.audit.application.servicio_auditoria import ServicioAuditoria


def crear_router(auditoria: ServicioAuditoria) -> APIRouter:
    r = APIRouter(prefix="/api/decisiones", tags=["Auditoría"])

    @r.get("")  # RNF04
    def decisiones():
        return auditoria.listar()

    return r
