"""Contexto de soporte: arma el escenario y avanza los ciclos.

Es el único contexto que orquesta a los demás a través de sus servicios de aplicación.
"""
from __future__ import annotations

import random
from datetime import datetime

from app.fleet.application.servicio_flota import ServicioFlota
from app.incidents.application.servicio_incidentes import ServicioIncidentes
from app.incidents.domain.incidente import Incidente
from app.network.application.servicio_red_vial import ServicioRedVial
from app.shared.kernel.eventos import BusDeEventos
from app.shared.kernel.prioridad import Prioridad
from app.simulation.domain.eventos import CicloIniciado
from app.simulation.domain.parametros import ParametrosDeEscenario
from app.simulation.infrastructure.generador import muestra_de_incidentes


class ServicioEscenario:
    def __init__(self, red: ServicioRedVial, flota: ServicioFlota, incidentes: ServicioIncidentes,
                 bus: BusDeEventos, params: ParametrosDeEscenario | None = None):
        self._red, self._flota, self._incidentes, self._bus = red, flota, incidentes, bus
        self.params = params or ParametrosDeEscenario()
        self.ciclo = 0
        self.hora = ""

    def inicializar(self) -> None:
        p = self.params
        rng = random.Random(p.semilla)
        lim = self._red.limites()
        ancho, alto = lim["xmax"] - lim["xmin"], lim["ymax"] - lim["ymin"]

        for nombre, fx, fy in p.bases:
            x, y = lim["xmin"] + fx * ancho, lim["ymin"] + fy * alto
            self._flota.registrar_base(nombre, x, y, self._red.ubicar_punto(x, y, 3))

        tipos = [t for t, n in p.flota for _ in range(n)]
        rng.shuffle(tipos)
        for i, t in enumerate(tipos):
            self._flota.registrar_unidad(t, i % len(p.bases))

        for caso, tip, dire in muestra_de_incidentes(rng, p.n_incidentes, p.dataset_csv):
            x, y = lim["xmin"] + rng.random() * ancho, lim["ymin"] + rng.random() * alto
            prio = Prioridad(rng.choices(["A", "M", "B"], weights=[20, 50, 30])[0])
            self._incidentes.cargar(
                Incidente(caso, tip, dire, prio, x, y, self._red.ubicar_punto(x, y, 2)))
        self.nuevo_ciclo()

    def nuevo_ciclo(self, semilla: int | None = None) -> int:
        self.ciclo += 1
        rng = random.Random(semilla if semilla is not None else self.params.semilla + self.ciclo - 1)
        self._incidentes.abrir_ciclo(rng, self.params.n_activos)
        self._flota.sortear_disponibilidad(rng, self.params.p_disponible)
        self.hora = datetime.now().strftime("%H:%M")
        self._bus.publicar(CicloIniciado(ciclo=self.ciclo, activos=len(self._incidentes.activos()),
                                         disponibles=len(self._flota.disponibles())))
        return self.ciclo
