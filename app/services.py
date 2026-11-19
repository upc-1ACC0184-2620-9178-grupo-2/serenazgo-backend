"""Servicios de aplicación: ShortestPathService, AssignmentService y PriorityPolicy."""
from __future__ import annotations

import time
from dataclasses import dataclass

from .algorithms import INF, asignar_ford_fulkerson, dijkstra, reconstruir_ruta
from .graph_provider import GraphProvider
from .repository import Repositorio


@dataclass(frozen=True)
class PriorityPolicy:
    orden: tuple = ("A", "M", "B")
    umbrales: tuple = (3.0, 5.0, 7.0, 9.0)
    tmax: float = 10.0


class ShortestPathService:
    """Ejecuta Dijkstra desde cada base y guarda el resultado en caché."""

    def __init__(self, proveedor: GraphProvider):
        self._p = proveedor
        self._cache: dict[int, tuple] = {}
        self._version = -1

    def desde(self, nodo_base: int):
        if self._version != self._p.version:
            self._cache.clear()
            self._version = self._p.version
        if nodo_base not in self._cache:
            self._cache[nodo_base] = dijkstra(self._p.adyacencia(), nodo_base)
        return self._cache[nodo_base]


class AssignmentService:
    def __init__(self, proveedor: GraphProvider, politica: PriorityPolicy | None = None):
        self.proveedor = proveedor
        self.politica = politica or PriorityPolicy()
        self.rutas = ShortestPathService(proveedor)

    def _ruta(self, prev, nodo):
        xy = self.proveedor.coordenadas()
        return [[round(xy[n][0], 3), round(xy[n][1], 3)] for n in reconstruir_ruta(prev, nodo)]

    def recomendar(self, repo: Repositorio) -> dict:
        t0 = time.perf_counter()
        pol = self.politica
        unidades = repo.disponibles()
        incs = repo.activos()
        dist_base = {b.id: self.rutas.desde(b.nodo) for b in repo.bases.values()}
        tiempos = [[dist_base[u.id_base][0][i.nodo_vial] for i in incs] for u in unidades]

        pares, flujo = asignar_ford_fulkerson(
            tiempos, [i.prioridad for i in incs], pol.umbrales, pol.tmax, pol.orden)

        usadas = {u for u, _ in pares}
        libres = [k for k in range(len(unidades)) if k not in usadas]
        asignaciones, cubiertos = [], set()
        for u, i in sorted(pares, key=lambda p: tiempos[p[0]][p[1]]):
            uni, inc = unidades[u], incs[i]
            cubiertos.add(i)
            alts = sorted((k for k in libres if tiempos[k][i] <= pol.tmax),
                          key=lambda k: tiempos[k][i])[:3]
            asignaciones.append({
                "incidente_id": inc.id_caso, "unidad_id": uni.id, "unidad": uni.etiqueta,
                "base_id": uni.id_base, "base": repo.bases[uni.id_base].nombre,
                "tiempo": round(tiempos[u][i], 2),
                "ruta": self._ruta(dist_base[uni.id_base][1], inc.nodo_vial),
                "alternativas": [{
                    "unidad_id": unidades[k].id, "unidad": unidades[k].etiqueta,
                    "base_id": unidades[k].id_base,
                    "base": repo.bases[unidades[k].id_base].nombre,
                    "tiempo": round(tiempos[k][i], 2),
                    "ruta": self._ruta(dist_base[unidades[k].id_base][1], inc.nodo_vial),
                } for k in alts]})

        sin_cobertura = []
        for i, inc in enumerate(incs):  # RF08
            if i in cubiertos:
                continue
            alcanzable = any(tiempos[u][i] <= pol.tmax for u in range(len(unidades)))
            sin_cobertura.append({
                "incidente_id": inc.id_caso,
                "motivo": "unidades_insuficientes" if alcanzable else "fuera_de_alcance"})

        por_base = []
        for b in repo.bases.values():
            propias = [u for u in repo.unidades.values() if u.id_base == b.id]
            por_base.append({
                "id": b.id, "nombre": b.nombre, "total": len(propias),
                "libres": sum(u.disponible for u in propias),
                "asignaciones": sum(1 for a in asignaciones if a["base_id"] == b.id)})

        tiempo_medio = (sum(a["tiempo"] for a in asignaciones) / len(asignaciones)
                        if asignaciones else 0.0)
        return {
            "asignaciones": asignaciones,
            "sin_cobertura": sin_cobertura,
            "por_base": por_base,
            "metricas": {
                "incidentes_activos": len(incs), "atendibles": len(asignaciones),
                "unidades_disponibles": len(unidades), "unidades_total": len(repo.unidades),
                "tiempo_medio": round(tiempo_medio, 2), "flujo_maximo": flujo,
                "tmax": pol.tmax, "calculo_ms": round((time.perf_counter() - t0) * 1000, 1)},
        }
