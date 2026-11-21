"""Casos de uso de Planificación de turno."""
from __future__ import annotations

import copy
from datetime import datetime

from app.scheduling.domain import eventos as ev
from app.scheduling.domain.modelos import ESTRATEGIAS, Evento
from app.scheduling.domain.plan import EPS, PlanDeTurno
from app.scheduling.domain.planificador import Planificador
from app.scheduling.domain.puertos import BasesPort, PlanRepository, RedViaPort
from app.scheduling.domain.redistribuidor import Redistribuidor
from app.shared.kernel.errores import Conflicto, Invalido, NoEncontrado
from app.shared.kernel.eventos import BusDeEventos
from app.shared.kernel.prioridad import Prioridad

PRESUPUESTO_S = 1.0


class ServicioPlan:
    def __init__(self, red: RedViaPort, bases: BasesPort, generador, repo: PlanRepository, bus: BusDeEventos):
        self._red, self._bases, self._gen, self._repo, self._bus = red, bases, generador, repo, bus

    # ---- acceso -----------------------------------------------------------------
    def plan(self) -> PlanDeTurno:
        p = self._repo.obtener()
        if p is None:                       # primer uso: escenario por defecto
            self.crear_escenario()
            p = self._repo.obtener()
        return p

    def _planificador(self) -> Planificador:
        return Planificador(self._red)

    # ---- escenario --------------------------------------------------------------
    def crear_escenario(self, n_serenazgos: int = 100, n_eventos: int = 300, horas: float = 8.0,
                        inicio: datetime | None = None, semilla: int = 42,
                        estrategia: str = "rapida", pct_programados: float = 0.5) -> PlanDeTurno:
        if estrategia not in ESTRATEGIAS:
            raise Invalido(f"Estrategia desconocida: {estrategia}.")
        if not (1 <= n_serenazgos <= 500) or not (0 <= n_eventos <= 1000):
            raise Invalido("Cantidad de serenazgos (1-500) o de eventos (0-1000) fuera de rango.")
        plan = self._gen.generar(n_serenazgos, n_eventos, horas, inicio, semilla, estrategia,
                                 pct_programados=pct_programados)
        self._repo.guardar(plan)
        pl = self._planificador()
        pl.construir(plan)                      # reparte la agenda conocida de antemano
        pl.mejorar(plan, PRESUPUESTO_S)
        self._procesar_instante(plan, pl)
        self._bus.publicar(ev.PlanGenerado(serenazgos=n_serenazgos, eventos=n_eventos, estrategia=estrategia))
        return plan

    # ---- lógica de eventos del plan (opera sobre un plan dado, sirve también para "qué pasa si") ----
    def _procesar_instante(self, plan: PlanDeTurno, pl: Planificador) -> list[int]:
        """Aplica llegadas y cancelaciones programadas cuyo momento ya ocurrió."""
        pl.resimular(plan)
        nuevos = []
        for e in [g for g in plan.guion if plan.minutos_de(g) <= plan.ahora + EPS]:
            plan.guion.remove(e)
            plan.reportar(e)
            pl.insertar(plan, e.id)
            nuevos.append(e.id)
        cancelados = [e for e in plan.eventos.values()
                      if e.cancelar_en and not e.cancelado and plan.turno.a_minutos(e.cancelar_en) <= plan.ahora + EPS]
        for e in cancelados:
            try:
                self._cancelar(plan, pl, e.id)
            except Conflicto:                  # ya se atendió antes de la cancelación programada
                e.cancelar_en = None
        return nuevos

    def _cancelar(self, plan: PlanDeTurno, pl: Planificador, eid: int) -> list[dict]:
        antes = plan.asignacion()
        plan.cancelar(eid)
        pl.resimular(plan)
        pl.reintentar_pendientes(plan)          # lo que quedó sin cobertura puede entrar ahora
        pl.mejorar(plan, PRESUPUESTO_S / 2)
        return self._cambios(antes, plan.asignacion(), excluir={eid})

    @staticmethod
    def _cambios(antes: dict, despues: dict, excluir: set[int] = frozenset()) -> list[dict]:
        out = []
        for eid in sorted(set(antes) | set(despues)):
            if eid in excluir or antes.get(eid) == despues.get(eid):
                continue
            out.append({"evento_id": eid, "de": antes.get(eid), "a": despues.get(eid)})
        return out

    def _avanzar(self, plan: PlanDeTurno, pl: Planificador, hasta: float) -> None:
        hasta = min(hasta, plan.turno.duracion_min)
        while True:
            prox = [plan.minutos_de(g) for g in plan.guion if plan.minutos_de(g) > plan.ahora + EPS]
            prox += [plan.turno.a_minutos(e.cancelar_en) for e in plan.eventos.values()
                     if e.cancelar_en and not e.cancelado and plan.turno.a_minutos(e.cancelar_en) > plan.ahora + EPS]
            prox = [t for t in prox if t <= hasta + EPS]
            if not prox:
                break
            plan.ahora = min(prox)
            plan.fijar(plan.ahora)
            self._procesar_instante(plan, pl)
        plan.ahora = hasta
        plan.fijar(hasta)
        pl.resimular(plan)
        pl.reintentar_pendientes(plan)
        pl.mejorar(plan, PRESUPUESTO_S)

    # ---- casos de uso -------------------------------------------------------------
    def avanzar_reloj(self, minutos: float) -> dict:
        if minutos <= 0:
            raise Invalido("Los minutos a avanzar deben ser positivos.")
        plan, pl = self.plan(), self._planificador()
        antes = plan.asignacion()
        self._avanzar(plan, pl, plan.ahora + minutos)
        hora = plan.turno.a_fecha(plan.ahora).strftime("%H:%M")
        self._bus.publicar(ev.RelojAvanzado(minutos=minutos, hora=hora))
        return {"hora": hora, "ahora_min": plan.ahora, "reasignados": self._cambios(antes, plan.asignacion())}

    def registrar_evento(self, tipologia: str, direccion: str, prioridad: Prioridad, x: float, y: float,
                         duracion_min: float | None = None) -> dict:
        plan, pl = self.plan(), self._planificador()
        lim = self._red.limites()
        if not (lim["xmin"] <= x <= lim["xmax"] and lim["ymin"] <= y <= lim["ymax"]):
            raise Invalido("La ubicación está fuera del distrito.")
        pl.resimular(plan)
        nuevo_id = max([*plan.eventos, *(g.id for g in plan.guion)], default=0) + 1
        e = Evento(nuevo_id, tipologia, direccion, prioridad, x, y, self._red.nodo_mas_cercano(x, y),
                   plan.turno.a_fecha(plan.ahora),
                   duracion_min or plan.reglas.duracion_min[prioridad], plan.reglas.plazo_min[prioridad])
        plan.reportar(e)
        asignado = pl.insertar(plan, e.id)
        pl.mejorar(plan, PRESUPUESTO_S / 2)
        sid = plan.asignacion().get(e.id)
        self._bus.publicar(ev.EventoReportado(evento=e.id, prioridad=prioridad.value, serenazgo=sid))
        return {"evento_id": e.id, "serenazgo_id": sid, "asignado": asignado and sid is not None}

    def cancelar_evento(self, eid: int) -> dict:
        plan, pl = self.plan(), self._planificador()
        cambios = self._cancelar(plan, pl, eid)
        self._bus.publicar(ev.EventoCancelado(evento=eid, reasignados=len(cambios)))
        return {"evento_id": eid, "reasignados": cambios}

    def baja_serenazgo(self, sid: int) -> dict:
        plan, pl = self.plan(), self._planificador()
        antes = plan.asignacion()
        plan.dar_de_baja(sid)
        pl.resimular(plan)
        pl.reintentar_pendientes(plan)
        pl.mejorar(plan, PRESUPUESTO_S / 2)
        cambios = self._cambios(antes, plan.asignacion())
        self._bus.publicar(ev.SerenazgoDadoDeBaja(serenazgo=sid, reasignados=len(cambios)))
        return {"serenazgo_id": sid, "reasignados": cambios}

    def optimizar(self) -> dict:
        plan, pl = self.plan(), self._planificador()
        antes, r0 = plan.asignacion(), plan.resumen()
        pl.resimular(plan)
        pl.reintentar_pendientes(plan)
        mejoras = pl.mejorar(plan, PRESUPUESTO_S * 2)
        return {"mejoras": mejoras, "antes": r0, "despues": plan.resumen(),
                "reasignados": self._cambios(antes, plan.asignacion())}

    def cambiar_estrategia(self, nombre: str) -> dict:
        if nombre not in ESTRATEGIAS:
            raise Invalido(f"Estrategia desconocida: {nombre}.")
        plan, pl = self.plan(), self._planificador()
        antes, r0 = plan.asignacion(), plan.resumen()
        plan.estrategia = ESTRATEGIAS[nombre]
        pl.construir(plan)
        pl.mejorar(plan, PRESUPUESTO_S * 2)
        self._bus.publicar(ev.EstrategiaCambiada(nombre=nombre))
        return {"antes": r0, "despues": plan.resumen(), "reasignados": self._cambios(antes, plan.asignacion())}

    def redistribuir(self) -> dict:
        plan, pl = self.plan(), self._planificador()
        pl.resimular(plan)
        r = Redistribuidor(pl).proponer(plan)
        plan.aplicar_movimientos(r.movimientos)
        self._bus.publicar(ev.SerenazgosRedistribuidos(
            movimientos=len(r.movimientos), cobertura_antes=r.cobertura_antes, cobertura_despues=r.cobertura_despues))
        return {"libres": r.libres, "movimientos": [
            {"serenazgo_id": m.serenazgo_id, "desde": list(self._red.coordenadas(m.nodo_desde)),
             "hacia": list(self._red.coordenadas(m.nodo_hasta)), "minutos": m.minutos} for m in r.movimientos],
            "cobertura_antes": r.cobertura_antes, "cobertura_despues": r.cobertura_despues,
            "tiempo_medio_antes": r.tiempo_medio_antes, "tiempo_medio_despues": r.tiempo_medio_despues}

    # ---- "qué pasa si": simula sobre una copia, sin tocar el plan real -------------
    def que_pasa_si(self, tipo: str, evento_id: int | None = None, serenazgo_id: int | None = None) -> dict:
        real = self.plan()
        plan, pl = copy.deepcopy(real), self._planificador()
        pl.resimular(plan)
        antes, r0 = plan.asignacion(), plan.resumen()
        if tipo == "cancelar_evento" and evento_id is not None:
            self._cancelar(plan, pl, evento_id)
            txt = f"Se cancela el evento {evento_id}."
        elif tipo == "baja_serenazgo" and serenazgo_id is not None:
            plan.dar_de_baja(serenazgo_id)
            pl.resimular(plan)
            pl.reintentar_pendientes(plan)
            pl.mejorar(plan, PRESUPUESTO_S / 2)
            txt = f"El serenazgo {serenazgo_id} sale de servicio."
        else:
            raise Invalido("Indica tipo=cancelar_evento con evento_id, o tipo=baja_serenazgo con serenazgo_id.")
        return {"tipo": tipo, "descripcion": txt, "antes": r0, "despues": plan.resumen(),
                "reasignados": self._cambios(antes, plan.asignacion(),
                                             excluir={evento_id} if evento_id else set())}

    def comparar_estrategias(self) -> dict:
        """Aplica cada estrategia a una copia del plan y compara los resultados."""
        out = {}
        for nombre, est in ESTRATEGIAS.items():
            plan, pl = copy.deepcopy(self.plan()), self._planificador()
            plan.estrategia = est
            pl.construir(plan)
            pl.mejorar(plan, PRESUPUESTO_S)
            out[nombre] = {"descripcion": est.descripcion, **plan.resumen()}
        return out

    # ---- modelo de lectura ------------------------------------------------------------
    def serenazgo_ruta(self, sid: int) -> list[list[float]]:
        plan = self.plan()
        if sid not in plan.serenazgos:
            raise NoEncontrado("Serenazgo no encontrado.")
        nodo = plan.serenazgos[sid].nodo_base
        puntos: list[list[float]] = []
        for t in [*plan.fijas[sid], *plan.tareas_futuras[sid]]:
            if t.tipo == "cancelada" or t.nodo == nodo:
                continue
            tramo = self._red.ruta(nodo, t.nodo)
            puntos += tramo if not puntos else tramo[1:]
            nodo = t.nodo
        return puntos

    def vista(self) -> dict:
        plan = self.plan()
        pl = self._planificador()
        pl.resimular(plan)
        idx = plan.indice()
        fecha = plan.turno.a_fecha
        eventos = []
        for e in sorted(plan.eventos.values(), key=lambda e: e.id):
            sid, t, _ = idx.get(e.id, (None, None, False))
            eventos.append({
                "id": e.id, "tipologia": e.tipologia, "direccion": e.direccion, "prioridad": e.prioridad.value,
                "x": round(e.x, 3), "y": round(e.y, 3), "reportado_min": round(plan.minutos_de(e), 1),
                "programado": plan.minutos_de(e) > plan.ahora + EPS,
                "reportado_en": e.reportado_en.isoformat(timespec="minutes"), "duracion_min": e.duracion_min,
                "plazo_min": e.plazo_min, "estado": plan.estado_evento(e, idx), "serenazgo_id": sid,
                "llegada": round(t.llegada, 1) if t else None, "inicio": round(t.inicio, 1) if t else None,
                "retraso": round(t.retraso, 1) if t else None, "respuesta": round(t.respuesta, 1) if t else None})
        serenazgos = []
        for sid, s in plan.serenazgos.items():
            tareas = [*plan.fijas[sid], *plan.tareas_futuras[sid]]
            ev_ids = [t.evento_id for t in tareas if t.tipo == "evento"]
            pos, estado = self._posicion_y_estado(plan, sid)
            serenazgos.append({
                "id": sid, "etiqueta": s.etiqueta, "tipo": s.tipo, "id_base": s.id_base,
                "en_servicio": s.en_servicio, "estado": estado, "x": pos[0], "y": pos[1],
                "eventos": ev_ids, "carga_min": round(plan.carga_total(sid), 1),
                "utilizacion_pct": round(100 * plan.carga_total(sid) / plan.turno.duracion_min, 1),
                "tareas": [{"tipo": t.tipo, "evento_id": t.evento_id, "salida": round(t.salida, 1),
                            "llegada": round(t.llegada, 1), "inicio": round(t.inicio, 1), "fin": round(t.fin, 1),
                            "retraso": round(t.retraso, 1), "x": round(self._red.coordenadas(t.nodo)[0], 3),
                            "y": round(self._red.coordenadas(t.nodo)[1], 3)} for t in tareas]})
        return {
            "turno": {"inicio": plan.turno.inicio.isoformat(timespec="minutes"),
                      "fin": plan.turno.fin.isoformat(timespec="minutes"), "horas": plan.turno.horas,
                      "duracion_min": plan.turno.duracion_min, "ahora_min": round(plan.ahora, 1),
                      "ahora": fecha(plan.ahora).isoformat(timespec="minutes"),
                      "hora": fecha(plan.ahora).strftime("%H:%M")},
            "estrategia": plan.estrategia.nombre,
            "estrategias": [{"nombre": n, "descripcion": e.descripcion} for n, e in ESTRATEGIAS.items()],
            "serenazgos": serenazgos, "eventos": eventos, "sin_cobertura": plan.pendientes_sin_asignar(),
            "bases": [{"id": b.id, "nombre": b.nombre, "x": round(b.x, 3), "y": round(b.y, 3)}
                      for b in self._bases.bases()],
            "metricas": plan.resumen(),
        }

    def _posicion_y_estado(self, plan: PlanDeTurno, sid: int):
        s = plan.serenazgos[sid]
        prev = s.nodo_base
        estado = "baja" if not s.en_servicio else "libre"
        for t in plan.fijas[sid]:
            if plan.ahora < t.llegada - EPS:
                (x0, y0), (x1, y1) = self._red.coordenadas(prev), self._red.coordenadas(t.nodo)
                f = (plan.ahora - t.salida) / (t.llegada - t.salida) if t.llegada > t.salida else 1.0
                if s.en_servicio:
                    estado = "en_camino"
                return (round(x0 + (x1 - x0) * f, 3), round(y0 + (y1 - y0) * f, 3)), estado
            if t.tipo == "evento" and plan.ahora < t.fin - EPS and s.en_servicio:
                estado = "atendiendo"
            prev = t.nodo
        x, y = self._red.coordenadas(prev)
        return (round(x, 3), round(y, 3)), estado
