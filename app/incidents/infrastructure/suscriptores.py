"""Anti-corruption layer: traduce eventos de otros contextos a comandos de Incidentes."""
from __future__ import annotations

from app.dispatch.domain.eventos import AsignacionConfirmada
from app.incidents.application.servicio_incidentes import ServicioIncidentes
from app.shared.kernel.eventos import BusDeEventos


def registrar(bus: BusDeEventos, incidentes: ServicioIncidentes) -> None:
    # Cuando Despacho confirma una asignación, el incidente queda atendido.
    bus.suscribir(AsignacionConfirmada, lambda e: incidentes.marcar_atendido(e.incidente_id))
