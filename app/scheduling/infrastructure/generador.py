"""Genera un día de trabajo simulado: serenazgos, eventos con zonas calientes y cancelaciones."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from app.incidents.domain.catalogo import TIPOLOGIAS
from app.scheduling.domain.modelos import (
    ESTRATEGIAS, Evento, ReglasDeAtencion, Serenazgo, Turno,
)
from app.scheduling.domain.plan import PlanDeTurno
from app.scheduling.domain.puertos import BasesPort, RedViaPort
from app.shared.kernel.prioridad import Prioridad

FLOTA = (("Camioneta", 0.27), ("Auto", 0.20), ("Moto", 0.53))


class GeneradorDeEscenario:
    def __init__(self, red: RedViaPort, bases: BasesPort):
        self._red = red
        self._bases = bases

    def generar(self, n_serenazgos: int = 100, n_eventos: int = 120, horas: float = 8.0,
                inicio: datetime | None = None, semilla: int = 42, estrategia: str = "rapida",
                pct_cancelados: float = 0.15, pct_programados: float = 0.5) -> PlanDeTurno:
        rng = random.Random(semilla)
        inicio = inicio or datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        turno = Turno(inicio, horas)
        reglas = ReglasDeAtencion()
        bases = self._bases.bases()
        lim = self._red.limites()
        ancho, alto = lim["xmax"] - lim["xmin"], lim["ymax"] - lim["ymin"]

        tipos = [t for t, p in FLOTA for _ in range(round(n_serenazgos * p))]
        tipos = (tipos + ["Moto"] * n_serenazgos)[:n_serenazgos]
        rng.shuffle(tipos)
        serenazgos = [Serenazgo(i + 1, t, bases[i % len(bases)].id, bases[i % len(bases)].nodo)
                      for i, t in enumerate(tipos)]
        plan = PlanDeTurno(turno, serenazgos, reglas, ESTRATEGIAS[estrategia])

        # zonas calientes (4) + ruido uniforme; picos de demanda a ~40 % y ~75 % del turno
        focos = [(lim["xmin"] + rng.random() * ancho, lim["ymin"] + rng.random() * alto) for _ in range(4)]
        dur = turno.duracion_min

        def instante() -> float:
            r = rng.random()
            if r < 0.30:
                return rng.uniform(0, dur - 30)
            centro = 0.40 if r < 0.65 else 0.75
            return min(dur - 30, max(0.0, rng.gauss(centro * dur, 55)))

        instantes = sorted(instante() for _ in range(n_eventos))
        if instantes:
            instantes[0] = 0.0                     # hay un evento desde el primer minuto
        eventos = []
        for k, minuto in enumerate(instantes, start=1):
            if rng.random() < 0.7:
                fx, fy = rng.choice(focos)
                x = min(lim["xmax"], max(lim["xmin"], rng.gauss(fx, 0.6)))
                y = min(lim["ymax"], max(lim["ymin"], rng.gauss(fy, 0.6)))
            else:
                x, y = lim["xmin"] + rng.random() * ancho, lim["ymin"] + rng.random() * alto
            prio = Prioridad(rng.choices(["A", "M", "B"], weights=[20, 50, 30])[0])
            rep = turno.a_fecha(minuto)
            ev = Evento(k, rng.choice(TIPOLOGIAS), f"Mz. {rng.choice('ABCDEFGHJK')} Lt. {rng.randint(1, 30)}",
                        prio, x, y, self._red.nodo_mas_cercano(x, y), rep,
                        round(reglas.duracion_min[prio] * rng.uniform(0.75, 1.25), 1), reglas.plazo_min[prio])
            if rng.random() < pct_cancelados:
                ev.cancelar_en = rep + timedelta(minutes=rng.uniform(5, 40))
            eventos.append(ev)
        # parte de los eventos está en la agenda desde el inicio (programados); el resto va llegando
        programados = [e for e in eventos if rng.random() < pct_programados]
        ids_prog = {e.id for e in programados}
        for e in programados:
            plan.reportar(e)
        plan.guion = [e for e in eventos if e.id not in ids_prog]
        return plan
