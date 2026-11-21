"""Composition root: crea los servicios de cada contexto y los conecta (puertos y eventos)."""
from __future__ import annotations

import os
from threading import RLock

from app.audit.application.servicio_auditoria import ServicioAuditoria
from app.audit.infrastructure.memoria import AuditoriaEnMemoria
from app.dispatch.application.servicio_despacho import ServicioDespacho
from app.dispatch.domain.politica import PoliticaDePrioridad
from app.dispatch.infrastructure.adaptadores import FlotaAdapter, IncidentesAdapter, RedVialAdapter
from app.fleet.application.servicio_flota import ServicioFlota
from app.fleet.infrastructure import suscriptores as suscriptores_flota
from app.fleet.infrastructure.memoria import BasesEnMemoria, UnidadesEnMemoria
from app.incidents.application.servicio_incidentes import ServicioIncidentes
from app.incidents.infrastructure import suscriptores as suscriptores_incidentes
from app.incidents.infrastructure.memoria import IncidentesEnMemoria
from app.incidents.infrastructure.red_adapter import UbicadorRedAdapter
from app.network.application.servicio_red_vial import ServicioRedVial
from app.network.domain.graph_provider import GraphProvider
from app.network.infrastructure.simulated_graph_provider import SimulatedGraphProvider
from app.scheduling.application.servicio_plan import ServicioPlan
from app.scheduling.infrastructure.adaptadores import BasesAdapter, RedViaAdapter
from app.scheduling.infrastructure.generador import GeneradorDeEscenario
from app.scheduling.infrastructure.memoria import PlanEnMemoria
from app.shared.kernel.eventos import BusDeEventos
from app.simulation.application.servicio_escenario import ServicioEscenario
from app.simulation.domain.parametros import ParametrosDeEscenario


def crear_proveedor() -> GraphProvider:
    """RNF02: la fuente del grafo se elige sin tocar los algoritmos (RED=osmnx)."""
    if os.getenv("RED", "simulada").lower() == "osmnx":
        from app.network.infrastructure.osmnx_graph_provider import OsmnxGraphProvider
        return OsmnxGraphProvider()
    return SimulatedGraphProvider()


class Contenedor:
    def __init__(self, proveedor: GraphProvider | None = None,
                 params: ParametrosDeEscenario | None = None):
        self.lock = RLock()
        self.bus = BusDeEventos()

        # un servicio de aplicación por contexto
        self.red = ServicioRedVial(proveedor or crear_proveedor(), self.bus)
        self.flota = ServicioFlota(UnidadesEnMemoria(), BasesEnMemoria(), self.bus)
        self.incidentes = ServicioIncidentes(IncidentesEnMemoria(), UbicadorRedAdapter(self.red), self.bus)
        self.despacho = ServicioDespacho(RedVialAdapter(self.red), IncidentesAdapter(self.incidentes),
                                         FlotaAdapter(self.flota), self.bus, PoliticaDePrioridad())
        self.auditoria = ServicioAuditoria(AuditoriaEnMemoria())
        if params is None:
            params = ParametrosDeEscenario(dataset_csv=os.getenv("DATASET_CSV"))
        self.escenario = ServicioEscenario(self.red, self.flota, self.incidentes, self.bus, params)

        # planificación de turno (reloj, rutas multi-evento, reasignación, redistribución)
        _red, _bases = RedViaAdapter(self.red), BasesAdapter(self.flota)
        self.plan = ServicioPlan(_red, _bases, GeneradorDeEscenario(_red, _bases), PlanEnMemoria(), self.bus)

        # eventos: quién reacciona a quién
        suscriptores_incidentes.registrar(self.bus, self.incidentes)
        suscriptores_flota.registrar(self.bus, self.flota)
        self.bus.suscribir_todos(self.auditoria.al_evento)

        self.escenario.inicializar()
