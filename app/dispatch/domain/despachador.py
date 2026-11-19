"""Servicio de dominio Despachador: arma la Propuesta del ciclo (lógica pura, sin E/S)."""
from __future__ import annotations

from app.dispatch.domain.asignador import asignar_ford_fulkerson
from app.dispatch.domain.modelos import (
    FUERA_DE_ALCANCE, UNIDADES_INSUFICIENTES, Alternativa, Asignacion, BaseOperativa,
    CargaDeBase, CaminosDesde, IncidenteADespachar, Metricas, Propuesta, ResumenBase,
    SinCobertura, UnidadDisponible,
)
from app.dispatch.domain.politica import PoliticaDePrioridad


class Despachador:
    def __init__(self, politica: PoliticaDePrioridad):
        self.politica = politica

    def proponer(self, unidades: list[UnidadDisponible], incidentes: list[IncidenteADespachar],
                 bases: list[BaseOperativa], caminos: dict[int, CaminosDesde],
                 resumen_bases: list[ResumenBase], total_unidades: int) -> Propuesta:
        pol = self.politica
        nombre_base = {b.id: b.nombre for b in bases}
        tiempos = [[caminos[u.id_base].tiempo_a(i.nodo_vial) for i in incidentes] for u in unidades]

        pares, flujo = asignar_ford_fulkerson(
            tiempos, [i.prioridad for i in incidentes], pol.umbrales, pol.tmax, pol.orden)

        usadas = {u for u, _ in pares}
        libres = [k for k in range(len(unidades)) if k not in usadas]

        def alternativa(k: int, i: int) -> Alternativa:
            return Alternativa(unidades[k].id, unidades[k].etiqueta, unidades[k].id_base,
                               nombre_base[unidades[k].id_base], round(tiempos[k][i], 2),
                               caminos[unidades[k].id_base].ruta_a(incidentes[i].nodo_vial))

        asignaciones, cubiertos = [], set()
        for u, i in sorted(pares, key=lambda p: tiempos[p[0]][p[1]]):
            uni, inc = unidades[u], incidentes[i]
            cubiertos.add(i)
            alts = sorted((k for k in libres if tiempos[k][i] <= pol.tmax),
                          key=lambda k: tiempos[k][i])[:3]
            asignaciones.append(Asignacion(
                inc.id_caso, uni.id, uni.etiqueta, uni.id_base, nombre_base[uni.id_base],
                round(tiempos[u][i], 2), caminos[uni.id_base].ruta_a(inc.nodo_vial),
                [alternativa(k, i) for k in alts]))

        sin_cobertura = []
        for i, inc in enumerate(incidentes):  # RF08
            if i in cubiertos:
                continue
            alcanzable = any(tiempos[u][i] <= pol.tmax for u in range(len(unidades)))
            sin_cobertura.append(SinCobertura(
                inc.id_caso, UNIDADES_INSUFICIENTES if alcanzable else FUERA_DE_ALCANCE))

        por_base = [CargaDeBase(r.id, r.nombre, r.total, r.libres,
                                sum(1 for a in asignaciones if a.base_id == r.id))
                    for r in resumen_bases]
        medio = sum(a.tiempo for a in asignaciones) / len(asignaciones) if asignaciones else 0.0
        return Propuesta(asignaciones, sin_cobertura, por_base, Metricas(
            incidentes_activos=len(incidentes), atendibles=len(asignaciones),
            unidades_disponibles=len(unidades), unidades_total=total_unidades,
            tiempo_medio=round(medio, 2), flujo_maximo=flujo, tmax=pol.tmax))
