"""Redistribución de serenazgos libres sobre el mapa.

1. Demanda = eventos del turno, con más peso los recientes, los graves y los sin cobertura.
2. k-medianas voraz: elige los puntos de espera que minimizan el tiempo ponderado a la demanda.
3. Reparte las unidades libres entre esos puntos según la demanda de cada uno.
4. Asigna unidades a puestos con el algoritmo húngaro (mínimo tiempo total de traslado).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.scheduling.domain.hungaro import asignacion_minima
from app.scheduling.domain.modelos import Movimiento
from app.scheduling.domain.plan import PlanDeTurno
from app.scheduling.domain.planificador import Planificador

TOPE_MIN = 60.0          # distancias mayores cuentan como 60 min
MEDIA_VIDA_MIN = 90.0    # un evento pierde la mitad de su peso cada 90 min


@dataclass(frozen=True)
class Redistribucion:
    movimientos: list[Movimiento]
    libres: int
    cobertura_antes: float      # % de la demanda a <= radio minutos de alguna unidad libre
    cobertura_despues: float
    tiempo_medio_antes: float   # minutos ponderados hasta la unidad libre más cercana
    tiempo_medio_despues: float


class Redistribuidor:
    def __init__(self, planificador: Planificador, radio_min: float = 10.0, max_puestos: int = 20,
                 max_demanda: int = 80, max_traslado_min: float = 25.0):
        self.p = planificador
        self.radio = radio_min
        self.max_puestos = max_puestos
        self.max_demanda = max_demanda
        self.max_traslado = max_traslado_min

    def _libres(self, plan: PlanDeTurno) -> list[tuple[int, int]]:
        out = []
        for sid, s in plan.serenazgos.items():
            nodo, libre = plan.estado_unidad(sid)
            if s.en_servicio and not plan.futuras[sid] and libre <= plan.ahora + 1e-9:
                out.append((sid, nodo))
        return out

    def _demanda(self, plan: PlanDeTurno) -> dict[int, float]:
        sin = set(plan.pendientes_sin_asignar())
        dem: dict[int, float] = {}
        for e in plan.eventos.values():
            if e.cancelado:
                continue
            edad = max(0.0, plan.ahora - plan.minutos_de(e))
            w = plan.reglas.peso[e.prioridad] * 0.5 ** (edad / MEDIA_VIDA_MIN) * (2.0 if e.id in sin else 1.0)
            dem[e.nodo] = dem.get(e.nodo, 0.0) + w
        top = sorted(dem.items(), key=lambda kv: -kv[1])[: self.max_demanda]
        return dict(top)

    def _medidas(self, posiciones: list[int], demanda: dict[int, float]) -> tuple[float, float]:
        total = sum(demanda.values()) or 1.0
        cubierto = costo = 0.0
        for nodo, w in demanda.items():
            fila = self.p.fila(nodo)
            d = min((fila[pos] for pos in posiciones), default=TOPE_MIN)
            d = min(d, TOPE_MIN)
            costo += w * d
            cubierto += w if d <= self.radio else 0.0
        return round(100 * cubierto / total, 1), round(costo / total, 2)

    def proponer(self, plan: PlanDeTurno, extra: dict[int, float] | None = None) -> Redistribucion:
        """Redistribuye a los serenazgos libres según la demanda reciente (más `extra`, la demanda histórica)."""
        demanda = self._demanda(plan)
        for nodo, w in (extra or {}).items():
            demanda[nodo] = demanda.get(nodo, 0.0) + w
        demanda = dict(sorted(demanda.items(), key=lambda kv: -kv[1])[: self.max_demanda])
        return self._colocar(plan, self._libres(plan), demanda, self.max_traslado)

    def desplegar(self, plan: PlanDeTurno, demanda: dict[int, float]) -> Redistribucion:
        """Inicio de turno: todos salen de sus bases hacia puestos de patrullaje repartidos por el distrito."""
        libres = [(sid, s.nodo_base) for sid, s in plan.serenazgos.items() if s.en_servicio]
        return self._colocar(plan, libres, demanda, max_traslado=1e9)

    def _colocar(self, plan: PlanDeTurno, libres: list[tuple[int, int]], demanda: dict[int, float],
                 max_traslado: float) -> Redistribucion:
        pos_antes = [nodo for _, nodo in libres]
        cob0, med0 = self._medidas(pos_antes, demanda)
        if not libres or not demanda:
            return Redistribucion([], len(libres), cob0, cob0, med0, med0)

        bases = {s.nodo_base for s in plan.serenazgos.values()}
        candidatos = list(dict.fromkeys([*demanda, *bases]))
        filas = {j: self.p.fila(j) for j in demanda}

        # k-medianas voraz
        mejor = {j: TOPE_MIN for j in demanda}
        puestos: list[int] = []
        for _ in range(min(len(libres), self.max_puestos, len(candidatos))):
            elegido, ganancia_max = None, 0.0
            for c in candidatos:
                if c in puestos:
                    continue
                g = sum(w * max(0.0, mejor[j] - filas[j][c]) for j, w in demanda.items())
                if g > ganancia_max:
                    elegido, ganancia_max = c, g
            if elegido is None:
                break
            puestos.append(elegido)
            for j in demanda:
                mejor[j] = min(mejor[j], filas[j][elegido])
        if not puestos:
            return Redistribucion([], len(libres), cob0, cob0, med0, med0)

        # peso de cada puesto = demanda que le queda más cerca
        peso = {c: 0.0 for c in puestos}
        for j, w in demanda.items():
            peso[min(puestos, key=lambda c: filas[j][c])] += w
        k = len(libres)
        total = sum(peso.values()) or 1.0
        cuotas = {c: 1 for c in puestos}
        extra = k - len(puestos)
        ideal = {c: extra * peso[c] / total for c in puestos}
        for c in puestos:
            cuotas[c] += int(ideal[c])
        resto = k - sum(cuotas.values())
        for c in sorted(puestos, key=lambda c: ideal[c] - int(ideal[c]), reverse=True)[:resto]:
            cuotas[c] += 1
        slots = [c for c in puestos for _ in range(cuotas[c])]

        # húngaro: unidad -> puesto
        costos = [[self.p.fila(c)[nodo] for c in slots] for _, nodo in libres]
        elegido = asignacion_minima(costos)
        movs: list[Movimiento] = []
        pos_despues = []
        for idx, ((sid, nodo), j) in enumerate(zip(libres, elegido)):
            destino, minutos = slots[j], costos[idx][j]
            if destino != nodo and 0.5 <= minutos <= max_traslado:
                movs.append(Movimiento(sid, nodo, destino, round(minutos, 2)))
                pos_despues.append(destino)
            else:
                pos_despues.append(nodo)
        cob1, med1 = self._medidas(pos_despues, demanda)
        return Redistribucion(movs, len(libres), cob0, cob1, med0, med1)
