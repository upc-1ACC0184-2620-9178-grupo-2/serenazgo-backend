"""Genera el día de trabajo: serenazgos, eventos con zonas calientes y cancelaciones.

Dos modos:
- simulado: un día completo pregenerado que se recorre con el reloj manual;
- en vivo: los eventos nuevos (accidentes, robos...) aparecen solos conforme pasa la hora real.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from app.scheduling.domain.modelos import (
    ESTRATEGIAS, Evento, ReglasDeAtencion, Serenazgo, Turno,
)
from app.scheduling.domain.plan import PlanDeTurno
from app.scheduling.domain.puertos import BasesPort, RedViaPort
from app.shared.kernel.prioridad import Prioridad

FLOTA = (("Camioneta", 0.27), ("Auto", 0.20), ("Moto", 0.53))
HORAS_DE_TURNO = 8
INICIO_TURNOS = 7          # turnos de 8 h: 07-15, 15-23 y 23-07 (hora de Lima)

# intensidad relativa de eventos por hora del día (0-23)
FACTOR_HORA = [0.8, 0.7, 0.6, 0.5, 0.5, 0.6, 0.8, 0.9, 0.9, 1.0, 1.0, 1.0,
               1.1, 1.1, 1.0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.4, 1.4, 1.2, 1.0]
# tipologías con su frecuencia relativa (los accidentes de tránsito son de los más comunes)
PESO_TIPOLOGIA = {"Accidente de tránsito": 22, "Robo en vía pública": 18, "Disturbios en vía pública": 12,
                  "Persona sospechosa": 12, "Ruidos molestos": 8, "Violencia familiar": 8,
                  "Agresión física": 8, "Vehículo abandonado": 6, "Robo a vivienda": 6}


def inicio_de_turno(ahora: datetime) -> datetime:
    """Inicio del turno de 8 h que contiene `ahora` (turnos 07:00, 15:00 y 23:00)."""
    ref = ahora.replace(hour=INICIO_TURNOS, minute=0, second=0, microsecond=0)
    bloques = math.floor((ahora - ref).total_seconds() / (HORAS_DE_TURNO * 3600))
    return ref + timedelta(hours=HORAS_DE_TURNO * bloques)


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


class GeneradorDeEscenario:
    def __init__(self, red: RedViaPort, bases: BasesPort):
        self._red = red
        self._bases = bases

    # ------------------------------------------------------------------ comunes
    def _serenazgos(self, rng: random.Random, n: int) -> list[Serenazgo]:
        bases = self._bases.bases()
        tipos = [t for t, p in FLOTA for _ in range(round(n * p))]
        tipos = (tipos + ["Moto"] * n)[:n]
        rng.shuffle(tipos)
        return [Serenazgo(i + 1, t, bases[i % len(bases)].id, bases[i % len(bases)].nodo)
                for i, t in enumerate(tipos)]

    def _focos(self, rng: random.Random) -> list[tuple[float, float]]:
        lim = self._red.limites()
        return [(lim["xmin"] + rng.random() * (lim["xmax"] - lim["xmin"]),
                 lim["ymin"] + rng.random() * (lim["ymax"] - lim["ymin"])) for _ in range(4)]

    def _evento(self, plan: PlanDeTurno, rng: random.Random, eid: int, minuto: float,
                pct_cancelados: float = 0.15) -> Evento:
        lim = self._red.limites()
        if rng.random() < 0.7 and plan.focos:
            fx, fy = rng.choice(plan.focos)
            x = min(lim["xmax"], max(lim["xmin"], rng.gauss(fx, 0.6)))
            y = min(lim["ymax"], max(lim["ymin"], rng.gauss(fy, 0.6)))
        else:
            x = lim["xmin"] + rng.random() * (lim["xmax"] - lim["xmin"])
            y = lim["ymin"] + rng.random() * (lim["ymax"] - lim["ymin"])
        prio = Prioridad(rng.choices(["A", "M", "B"], weights=[20, 50, 30])[0])
        tip = rng.choices(list(PESO_TIPOLOGIA), weights=list(PESO_TIPOLOGIA.values()))[0]
        if tip == "Accidente de tránsito" and rng.random() < 0.5:
            prio = Prioridad.ALTA
        reglas = plan.reglas
        rep = plan.turno.a_fecha(minuto)
        ev = Evento(eid, tip, f"Mz. {rng.choice('ABCDEFGHJK')} Lt. {rng.randint(1, 30)}", prio, x, y,
                    self._red.nodo_mas_cercano(x, y), rep,
                    round(reglas.duracion_min[prio] * rng.uniform(0.75, 1.25), 1), reglas.plazo_min[prio])
        if rng.random() < pct_cancelados:
            ev.cancelar_en = rep + timedelta(minutes=rng.uniform(5, 40))
        return ev

    # --------------------------------------------------------------- modo simulado
    def generar(self, n_serenazgos: int = 100, n_eventos: int = 300, horas: float = 8.0,
                inicio: datetime | None = None, semilla: int = 42, estrategia: str = "rapida",
                pct_cancelados: float = 0.15, pct_programados: float = 0.5) -> PlanDeTurno:
        rng = random.Random(semilla)
        inicio = inicio or datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        turno = Turno(inicio, horas)
        plan = PlanDeTurno(turno, self._serenazgos(rng, n_serenazgos), ReglasDeAtencion(), ESTRATEGIAS[estrategia])
        plan.focos = self._focos(rng)
        dur = turno.duracion_min

        def instante() -> float:      # picos de demanda a ~40 % y ~75 % del turno
            r = rng.random()
            if r < 0.30:
                return rng.uniform(0, dur - 30)
            centro = 0.40 if r < 0.65 else 0.75
            return min(dur - 30, max(0.0, rng.gauss(centro * dur, 55)))

        instantes = sorted(instante() for _ in range(n_eventos))
        if instantes:
            instantes[0] = 0.0
        eventos = [self._evento(plan, rng, k, m, pct_cancelados=pct_cancelados)
                   for k, m in enumerate(instantes, start=1)]
        programados = [e for e in eventos if rng.random() < pct_programados]
        ids = {e.id for e in programados}
        for e in programados:
            plan.reportar(e)
        plan.guion = [e for e in eventos if e.id not in ids]
        return plan

    # --------------------------------------------------------------- modo en vivo
    def generar_en_vivo(self, ahora: datetime, n_serenazgos: int = 100, horas: float = 8.0,
                        eventos_por_hora: float = 40.0, velocidad: float = 1.0, semilla: int = 42,
                        estrategia: str = "rapida", pct_agenda: float = 0.15,
                        inicio: datetime | None = None, ref_min: float | None = None,
                        serenazgos: list[Serenazgo] | None = None) -> PlanDeTurno:
        """Turno alineado a la hora real de Lima. Los eventos nuevos se generan con `eventos_en_vivo`."""
        rng = random.Random(semilla)
        inicio = inicio or inicio_de_turno(ahora)
        turno = Turno(inicio, horas)
        ser = serenazgos if serenazgos is not None else self._serenazgos(rng, n_serenazgos)
        plan = PlanDeTurno(turno, ser, ReglasDeAtencion(), ESTRATEGIAS[estrategia])
        plan.tiempo_real, plan.velocidad = True, velocidad
        plan.ref_real = ahora
        plan.ref_min = ref_min if ref_min is not None else (ahora - inicio).total_seconds() / 60
        plan.eventos_por_hora = eventos_por_hora
        plan.rng = rng
        plan.focos = self._focos(rng)
        # agenda: algunos eventos programados para más adelante en el turno
        dur = turno.duracion_min
        desde = plan.ref_min + 10
        if dur - 30 > desde and pct_agenda > 0:
            n = round(eventos_por_hora * (dur - 30 - desde) / 60 * pct_agenda)
            for m in sorted(rng.uniform(desde, dur - 30) for _ in range(n)):
                plan.reportar(self._evento(plan, rng, plan.siguiente_id(), m))
        return plan

    def eventos_en_vivo(self, plan: PlanDeTurno, t0: float, t1: float) -> list[Evento]:
        """Eventos nuevos (accidentes, robos...) que ocurren entre los minutos t0 y t1 del turno."""
        rng, out, t = plan.rng, [], t0
        nid = plan.siguiente_id()
        while t < t1 - 1e-9:
            t2 = min(t1, t + 5.0)
            hora = plan.turno.a_fecha(t).hour
            lam = plan.eventos_por_hora * FACTOR_HORA[hora] / 60 * (t2 - t)
            for _ in range(_poisson(rng, lam)):
                out.append(self._evento(plan, rng, nid, rng.uniform(t, t2)))
                nid += 1
            t = t2
        return sorted(out, key=lambda e: e.reportado_en)
