"""Anti-corruption layer: traduce eventos de otros contextos a comandos de Flota."""
from __future__ import annotations

from app.dispatch.domain.eventos import AsignacionConfirmada
from app.fleet.application.servicio_flota import ServicioFlota
from app.shared.kernel.eventos import BusDeEventos


def registrar(bus: BusDeEventos, flota: ServicioFlota) -> None:
    # Cuando Despacho confirma una asignación, la unidad pasa a estar ocupada.
    bus.suscribir(AsignacionConfirmada,
                  lambda e: flota.ocupar(e.unidad_id, e.incidente_id))
