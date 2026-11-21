"""Servicio de dominio Planificador: reparte los eventos entre los serenazgos a lo largo del turno.

Modelo: cada serenazgo tiene una *ruta* (lista ordenada de eventos). Se minimiza
    costo = Σ peso_prioridad·retraso + peso_respuesta·peso_prioridad·respuesta + peso_viaje·viaje
            + peso_balance·carga² + costo_activacion
sujeto a: el evento termina antes del fin del turno y la espera no supera la tolerancia.
Heurística: inserción más barata (por prioridad) + búsqueda local (reubicar eventos).
"""
from __future__ import annotations

import time

from app.scheduling.domain.modelos import Tarea
from app.scheduling.domain.plan import PlanDeTurno
from app.scheduling.domain.puertos import RedViaPort


class Planificador:
    def __init__(self, red: RedViaPort, k_candidatos: int = 30):
        self.red = red
        self.k = k_candidatos
        self._filas: dict[int, list[float]] = {}

    # ---- tiempos de viaje (Dijkstra, con caché por nodo) -------------------
    def fila(self, nodo: int) -> list[float]:
        f = self._filas.get(nodo)
        if f is None:
            f = self._filas[nodo] = self.red.tiempos_desde(nodo)
        return f

    def t(self, a: int, b: int) -> float:
        if a == b:
            return 0.0
        if b in self._filas:
            return self._filas[b][a]
        if a in self._filas:
            return self._filas[a][b]
        return self.fila(b)[a]

    # ---- simulación de una ruta ----------------------------------------------
    def simular(self, plan: PlanDeTurno, sid: int, ids: list[int]):
        """Devuelve (tareas, costo) o None si la ruta no es factible."""
        est, reglas = plan.estrategia, plan.reglas
        nodo, t = plan.estado_unidad(sid)
        limite = plan.turno.duracion_min
        carga = plan.carga_fija(sid)
        costo, tareas = 0.0, []
        for eid in ids:
            e = plan.eventos[eid]
            rep = plan.minutos_de(e)
            viaje = self.t(nodo, e.nodo)
            # si el evento es futuro (programado), la unidad sale justo a tiempo y puede hacer otra cosa antes
            salida = t if t + viaje >= rep else rep - viaje
            llegada = salida + viaje
            inicio = llegada
            respuesta = llegada - rep
            fin = inicio + e.duracion_min
            if respuesta > reglas.espera_max_min[e.prioridad] or fin > limite:
                return None
            retraso = respuesta - e.plazo_min if respuesta > e.plazo_min else 0.0
            w = reglas.peso[e.prioridad]
            costo += w * retraso + est.peso_respuesta * w * respuesta + est.peso_viaje * viaje
            tareas.append(Tarea("evento", eid, e.nodo, salida, llegada, inicio, fin, retraso, respuesta))
            nodo, t = e.nodo, fin
            carga += e.duracion_min
        costo += est.peso_balance * carga * carga
        if ids and not plan.usada(sid):
            costo += est.costo_activacion
        return tareas, costo

    def resimular(self, plan: PlanDeTurno) -> list[int]:
        """Recalcula tiempos y costos de todas las rutas. Si alguna dejó de ser factible,
        saca sus últimos eventos (quedan pendientes). Devuelve los ids sacados."""
        sacados: list[int] = []
        for sid in plan.serenazgos:
            r = self.simular(plan, sid, plan.futuras[sid])
            while r is None and plan.futuras[sid]:
                sacados.append(plan.futuras[sid].pop())
                r = self.simular(plan, sid, plan.futuras[sid])
            plan.tareas_futuras[sid], plan.costos[sid] = r
        return sacados

    # ---- candidatos ---------------------------------------------------------------
    def _candidatos(self, plan: PlanDeTurno, eid: int) -> list[int]:
        e = plan.eventos[eid]
        fila = self.fila(e.nodo)
        punt = []
        for sid, s in plan.serenazgos.items():
            if not s.en_servicio:
                continue
            nodo, _ = plan.estado_unidad(sid)
            d = fila[nodo]
            for x in plan.futuras[sid]:
                d = min(d, fila[plan.eventos[x].nodo])
            punt.append((d, sid))
        punt.sort()
        elegidos = [sid for _, sid in punt[: self.k]]
        if plan.estrategia.peso_balance > 0.001:      # para repartir, incluye a los menos cargados
            libres = sorted((sid for _, sid in punt), key=plan.carga_total)[:5]
            elegidos += [s for s in libres if s not in elegidos]
        return elegidos

    # ---- construcción e inserción ------------------------------------------------
    def insertar(self, plan: PlanDeTurno, eid: int) -> bool:
        mejor = None
        for sid in self._candidatos(plan, eid):
            ids, base = plan.futuras[sid], plan.costos[sid]
            for pos in range(len(ids) + 1):
                nuevo = ids[:pos] + [eid] + ids[pos:]
                r = self.simular(plan, sid, nuevo)
                if r is None:
                    continue
                delta = r[1] - base
                if mejor is None or delta < mejor[0]:
                    mejor = (delta, sid, nuevo, r)
        if mejor is None:
            return False
        _, sid, nuevo, (tareas, costo) = mejor
        plan.futuras[sid], plan.tareas_futuras[sid], plan.costos[sid] = nuevo, tareas, costo
        return True

    def _orden(self, plan: PlanDeTurno, ids: list[int]) -> list[int]:
        return sorted(ids, key=lambda i: (plan.eventos[i].prioridad.nivel,
                                          plan.minutos_de(plan.eventos[i]), i))

    def reintentar_pendientes(self, plan: PlanDeTurno) -> int:
        n = 0
        for eid in self._orden(plan, plan.pendientes_sin_asignar()):
            n += self.insertar(plan, eid)
        return n

    def construir(self, plan: PlanDeTurno) -> None:
        """Replanifica desde cero todo lo no comprometido (lo ya iniciado no se toca)."""
        for sid in plan.serenazgos:
            plan.futuras[sid], plan.tareas_futuras[sid] = [], []
        self.resimular(plan)
        self.reintentar_pendientes(plan)

    # ---- búsqueda local ------------------------------------------------------------
    def mejorar(self, plan: PlanDeTurno, presupuesto_s: float = 1.0) -> int:
        """Reubica eventos (entre unidades o dentro de la misma ruta) mientras baje el costo."""
        t0 = time.perf_counter()
        mejoras = 0
        hubo = True
        while hubo and time.perf_counter() - t0 < presupuesto_s:
            hubo = False
            pares = [(sid, eid) for sid, ids in plan.futuras.items() for eid in ids]
            pares.sort(key=lambda p: plan.eventos[p[1]].prioridad.nivel)
            for sid, eid in pares:
                if time.perf_counter() - t0 >= presupuesto_s:
                    break
                if eid not in plan.futuras[sid]:
                    continue
                ids = plan.futuras[sid]
                sin = [x for x in ids if x != eid]
                r_sin = self.simular(plan, sid, sin)
                if r_sin is None:
                    continue
                ahorro = plan.costos[sid] - r_sin[1]
                mejor = None
                for sid2 in self._candidatos(plan, eid):
                    misma = sid2 == sid
                    ids2 = sin if misma else plan.futuras[sid2]
                    for pos in range(len(ids2) + 1):
                        nuevo = ids2[:pos] + [eid] + ids2[pos:]
                        if misma and nuevo == ids:
                            continue
                        r = self.simular(plan, sid2, nuevo)
                        if r is None:
                            continue
                        delta = r[1] - plan.costos[sid] if misma else (r[1] - plan.costos[sid2]) - ahorro
                        if mejor is None or delta < mejor[0]:
                            mejor = (delta, sid2, nuevo, r)
                if mejor is not None and mejor[0] < -1e-6:
                    _, sid2, nuevo, (tareas, costo) = mejor
                    if sid2 != sid:
                        plan.futuras[sid], plan.tareas_futuras[sid], plan.costos[sid] = sin, r_sin[0], r_sin[1]
                    plan.futuras[sid2], plan.tareas_futuras[sid2], plan.costos[sid2] = nuevo, tareas, costo
                    mejoras += 1
                    hubo = True
        return mejoras
