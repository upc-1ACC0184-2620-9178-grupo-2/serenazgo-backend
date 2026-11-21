"""Raíz de agregado PlanDeTurno: el día de trabajo de todos los serenazgos."""
from __future__ import annotations

from dataclasses import replace

from app.scheduling.domain.modelos import (
    ESTRATEGIAS, EstrategiaDePlanificacion, Evento, Movimiento, ReglasDeAtencion, Serenazgo, Tarea, Turno,
)
from app.shared.kernel.errores import Conflicto, NoEncontrado

EPS = 1e-9


class PlanDeTurno:
    """Las tareas con salida <= ahora están *comprometidas* (`fijas`) y ya no se reasignan;
    las demás (`futuras`) se replanifican cuando algo cambia."""

    def __init__(self, turno: Turno, serenazgos: list[Serenazgo], reglas: ReglasDeAtencion | None = None,
                 estrategia: EstrategiaDePlanificacion | None = None):
        self.turno = turno
        self.reglas = reglas or ReglasDeAtencion()
        self.estrategia = estrategia or ESTRATEGIAS["rapida"]
        self.serenazgos: dict[int, Serenazgo] = {s.id: s for s in serenazgos}
        self.eventos: dict[int, Evento] = {}       # ya reportados
        self.guion: list[Evento] = []              # aún no ocurren (simulación)
        self.ahora = 0.0                           # minutos desde el inicio del turno
        self.fijas: dict[int, list[Tarea]] = {i: [] for i in self.serenazgos}
        self.futuras: dict[int, list[int]] = {i: [] for i in self.serenazgos}
        self.tareas_futuras: dict[int, list[Tarea]] = {i: [] for i in self.serenazgos}
        self.costos: dict[int, float] = {i: 0.0 for i in self.serenazgos}

    # ---- tiempo y estado de cada serenazgo --------------------------------
    def minutos_de(self, e: Evento) -> float:
        return self.turno.a_minutos(e.reportado_en)

    def estado_unidad(self, sid: int) -> tuple[int, float]:
        """(nodo donde queda libre, minuto desde el que está libre)."""
        f = self.fijas[sid]
        if f:
            return f[-1].nodo, max(self.ahora, f[-1].fin)
        return self.serenazgos[sid].nodo_base, self.ahora

    def carga_fija(self, sid: int) -> float:
        return sum(t.fin - t.inicio for t in self.fijas[sid] if t.tipo != "reposicion")

    def carga_total(self, sid: int) -> float:
        return self.carga_fija(sid) + sum(t.fin - t.inicio for t in self.tareas_futuras[sid])

    def usada(self, sid: int) -> bool:
        return any(t.tipo == "evento" for t in self.fijas[sid])

    def fijar(self, t: float) -> None:
        """Compromete las tareas que ya salieron en el minuto t."""
        for sid, tareas in self.tareas_futuras.items():
            while tareas and tareas[0].salida <= t + EPS:
                self.fijas[sid].append(tareas.pop(0))
                self.futuras[sid].pop(0)

    # ---- consultas ------------------------------------------------------------
    def indice(self) -> dict[int, tuple[int, Tarea, bool]]:
        """evento_id -> (serenazgo, tarea, comprometida)."""
        idx: dict[int, tuple[int, Tarea, bool]] = {}
        for sid in self.serenazgos:
            for t in self.fijas[sid]:
                if t.evento_id is not None:
                    idx[t.evento_id] = (sid, t, True)
            for t in self.tareas_futuras[sid]:
                idx[t.evento_id] = (sid, t, False)
        return idx

    def pendientes_sin_asignar(self) -> list[int]:
        idx = self.indice()
        return [e.id for e in self.eventos.values() if not e.cancelado and e.id not in idx]

    def asignacion(self) -> dict[int, int]:
        return {eid: sid for eid, (sid, t, _) in self.indice().items() if t.tipo == "evento"}

    def estado_evento(self, e: Evento, idx: dict) -> str:
        if e.cancelado:
            return "cancelado"
        if e.id not in idx:
            return "sin_cobertura"
        _, t, fija = idx[e.id]
        if not fija:
            return "asignado"
        if self.ahora >= t.fin - EPS:
            return "atendido"
        return "atendiendo" if self.ahora >= t.inicio - EPS else "en_camino"

    # ---- comandos --------------------------------------------------------------
    def reportar(self, e: Evento) -> None:
        self.eventos[e.id] = e

    def cancelar(self, eid: int) -> None:
        e = self.eventos.get(eid)
        if e is None:
            g = next((x for x in self.guion if x.id == eid), None)
            if g is None:
                raise NoEncontrado("Evento no encontrado.")
            self.guion.remove(g)
            return
        if e.cancelado:
            raise Conflicto("El evento ya está cancelado.")
        for sid, ids in self.futuras.items():
            if eid in ids:
                k = ids.index(eid)
                ids.pop(k)
                self.tareas_futuras[sid].pop(k)
                break
        else:
            for tareas in self.fijas.values():
                for k, t in enumerate(tareas):
                    if t.evento_id == eid and t.tipo == "evento":
                        if self.ahora >= t.fin - EPS:
                            raise Conflicto("El evento ya fue atendido.")
                        tareas[k] = replace(t, tipo="cancelada", llegada=min(t.llegada, self.ahora),
                                            inicio=min(t.inicio, self.ahora), fin=self.ahora, retraso=0.0)
        e.cancelado = True
        e.cancelado_en = self.turno.a_fecha(self.ahora)

    def dar_de_baja(self, sid: int) -> list[int]:
        """El serenazgo sale de servicio: termina lo que hace; sus eventos futuros se reasignan."""
        s = self.serenazgos.get(sid)
        if s is None:
            raise NoEncontrado("Serenazgo no encontrado.")
        if not s.en_servicio:
            raise Conflicto("El serenazgo ya está fuera de servicio.")
        s.en_servicio = False
        quitados = list(self.futuras[sid])
        self.futuras[sid] = []
        self.tareas_futuras[sid] = []
        return quitados

    def aplicar_movimientos(self, movs: list[Movimiento]) -> None:
        for m in movs:
            llegada = self.ahora + m.minutos
            self.fijas[m.serenazgo_id].append(
                Tarea("reposicion", None, m.nodo_hasta, self.ahora, llegada, llegada, llegada))

    # ---- métricas --------------------------------------------------------------
    def resumen(self) -> dict:
        tareas = [t for sid in self.serenazgos for t in (*self.fijas[sid], *self.tareas_futuras[sid])
                  if t.tipo == "evento"]
        idx = self.indice()
        estados = [self.estado_evento(e, idx) for e in self.eventos.values()]
        cargas = [self.carga_total(s) / 60 for s in self.serenazgos if self.serenazgos[s].en_servicio]
        n = len(cargas) or 1
        media = sum(cargas) / n
        return {
            "eventos_reportados": len(self.eventos), "programados": len(self.guion),
            "atendidos": estados.count("atendido"),
            "en_curso": estados.count("atendiendo") + estados.count("en_camino"),
            "asignados": estados.count("asignado"), "cancelados": estados.count("cancelado"),
            "sin_cobertura": estados.count("sin_cobertura"),
            "retraso_total_min": round(sum(t.retraso for t in tareas), 1),
            "respuesta_media_min": round(sum(t.respuesta for t in tareas) / len(tareas), 1) if tareas else 0.0,
            "pct_en_plazo": round(100 * sum(1 for t in tareas if t.retraso <= EPS) / len(tareas), 1) if tareas else 100.0,
            "serenazgos_usados": sum(1 for s in self.serenazgos if self.carga_total(s) > 0),
            "serenazgos_activos": sum(1 for s in self.serenazgos.values() if s.en_servicio),
            "carga_media_h": round(media, 2), "carga_max_h": round(max(cargas, default=0.0), 2),
            "carga_min_h": round(min(cargas, default=0.0), 2),
            "desviacion_carga_h": round((sum((c - media) ** 2 for c in cargas) / n) ** 0.5, 2),
            "utilizacion_pct": round(100 * media * 60 / self.turno.duracion_min, 1),
        }
