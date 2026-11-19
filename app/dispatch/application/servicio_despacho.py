"""Casos de uso del contexto Despacho: recomendar, confirmar y escalar (CU02, CU03, RF08)."""
from __future__ import annotations

import time
from dataclasses import replace

from app.dispatch.domain.despachador import Despachador
from app.dispatch.domain.eventos import AsignacionConfirmada, IncidentesEscalados, RecomendacionCalculada
from app.dispatch.domain.modelos import ParDeConfirmacion, Propuesta
from app.dispatch.domain.politica import PoliticaDePrioridad
from app.dispatch.domain.puertos import FlotaPort, IncidentesPort, RedVialPort
from app.shared.kernel.errores import Conflicto
from app.shared.kernel.eventos import BusDeEventos


class ServicioDespacho:
    def __init__(self, red: RedVialPort, incidentes: IncidentesPort, flota: FlotaPort,
                 bus: BusDeEventos, politica: PoliticaDePrioridad | None = None):
        self._red, self._incidentes, self._flota, self._bus = red, incidentes, flota, bus
        self.politica = politica or PoliticaDePrioridad()

    def recomendar(self) -> Propuesta:
        t0 = time.perf_counter()
        unidades = self._flota.disponibles()
        incidentes = self._incidentes.activos()
        bases = self._flota.bases()
        caminos = {b.id: self._red.caminos_desde(b.nodo) for b in bases}
        p = Despachador(self.politica).proponer(
            unidades, incidentes, bases, caminos,
            self._flota.resumen_por_base(), self._flota.total_unidades())
        ms = round((time.perf_counter() - t0) * 1000, 1)
        p = replace(p, metricas=replace(p.metricas, calculo_ms=ms))
        self._bus.publicar(RecomendacionCalculada(
            atendibles=p.metricas.atendibles, sin_cobertura=len(p.sin_cobertura),
            tiempo_medio=p.metricas.tiempo_medio))
        return p

    def confirmar(self, pares: list[ParDeConfirmacion], operador: str = "GJ") -> int:
        """Valida todo y confirma (todo o nada). Publica un evento por asignación."""
        vistos_i: set[str] = set()
        vistos_u: set[int] = set()
        validadas = []
        for p in pares:
            self._incidentes.verificar_activo(p.incidente_id)
            unidad = self._flota.verificar_disponible(p.unidad_id)
            if p.incidente_id in vistos_i or p.unidad_id in vistos_u:
                raise Conflicto("Hay incidentes o unidades repetidos.")
            vistos_i.add(p.incidente_id)
            vistos_u.add(p.unidad_id)
            validadas.append((p, unidad))
        for p, unidad in validadas:
            self._bus.publicar(AsignacionConfirmada(
                incidente_id=p.incidente_id, unidad_id=p.unidad_id, unidad=unidad.etiqueta,
                tiempo=p.tiempo, modificada=p.modificada, operador=operador))
        return len(validadas)

    def escalar(self, ids: list[str]) -> int:
        self._bus.publicar(IncidentesEscalados(incidentes=tuple(ids)))
        return len(ids)
