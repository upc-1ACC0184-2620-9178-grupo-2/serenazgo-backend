"""Servicio de dominio: caminos mínimos con Dijkstra. O((V+E) log V)."""
from __future__ import annotations

import heapq
from dataclasses import dataclass

INF = float("inf")


def dijkstra(adj: list[list[tuple[int, float]]], fuente: int):
    """Tiempos mínimos desde `fuente` a todos los nodos."""
    n = len(adj)
    dist = [INF] * n
    prev = [-1] * n
    dist[fuente] = 0.0
    cola = [(0.0, fuente)]
    while cola:
        d, u = heapq.heappop(cola)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(cola, (nd, v))
    return dist, prev


def reconstruir_ruta(prev: list[int], destino: int) -> list[int]:
    ruta = [destino]
    while prev[ruta[-1]] != -1:
        ruta.append(prev[ruta[-1]])
    return ruta[::-1]


@dataclass(frozen=True)
class CaminosMinimos:
    """Value object: resultado de Dijkstra desde un nodo fuente."""
    fuente: int
    dist: list[float]
    prev: list[int]

    def tiempo_a(self, nodo: int) -> float:
        return self.dist[nodo]

    def ruta_a(self, nodo: int) -> list[int]:
        return reconstruir_ruta(self.prev, nodo)


def calcular_caminos(adj: list[list[tuple[int, float]]], fuente: int) -> CaminosMinimos:
    dist, prev = dijkstra(adj, fuente)
    return CaminosMinimos(fuente, dist, prev)
