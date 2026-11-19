"""Núcleo algorítmico: Dijkstra (G1) y Ford-Fulkerson con prioridad (G2)."""
from __future__ import annotations

import heapq

INF = float("inf")


def dijkstra(adj: list[list[tuple[int, float]]], fuente: int):
    """Tiempos mínimos desde `fuente` a todos los nodos. O((V+E) log V)."""
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


class RedDeFlujo:
    """Red de flujo con capacidades enteras y búsqueda de caminos por DFS."""

    def __init__(self, n: int):
        self.n = n
        self.g: list[list[int]] = [[] for _ in range(n)]
        self.to: list[int] = []
        self.cap: list[int] = []

    def agregar_arista(self, u: int, v: int, c: int) -> int:
        idx = len(self.to)
        self.to += [v, u]
        self.cap += [c, 0]
        self.g[u].append(idx)
        self.g[v].append(idx + 1)
        return idx

    def _camino(self, u: int, t: int, visto: list[bool]) -> bool:
        if u == t:
            return True
        visto[u] = True
        for e in self.g[u]:
            v = self.to[e]
            if self.cap[e] > 0 and not visto[v] and self._camino(v, t, visto):
                self.cap[e] -= 1
                self.cap[e ^ 1] += 1
                return True
        return False

    def maximizar(self, s: int, t: int) -> int:
        """Aumenta el flujo mientras exista camino aumentante. Devuelve el
        flujo añadido (cada camino aumenta 1 porque las capacidades son 1)."""
        total = 0
        while self._camino(s, t, [False] * self.n):
            total += 1
        return total


def asignar_ford_fulkerson(tiempos, prioridades, umbrales, tmax, orden=("A", "M", "B")):
    """Asignación unidad-incidente (pseudocódigo ASIGNAR del informe).

    tiempos[u][i]: tiempo mínimo (Dijkstra) de la unidad u al incidente i.
    prioridades[i]: "A" | "M" | "B".
    Devuelve (pares [(u, i)], flujo máximo alcanzado).
    """
    n_u, n_i = len(tiempos), len(prioridades)
    S, T = 0, n_u + n_i + 1
    red = RedDeFlujo(T + 1)
    for u in range(n_u):
        red.agregar_arista(S, 1 + u, 1)
    aristas: dict[tuple[int, int], int] = {}
    flujo = 0
    tramos = [x for x in umbrales if x < tmax] + [tmax]
    for nivel in orden:                                   # criterio voraz
        clase = [i for i in range(n_i) if prioridades[i] == nivel]
        for i in clase:
            red.agregar_arista(1 + n_u + i, T, 1)
        previo = -1.0
        for umbral in tramos:                             # umbrales escalonados
            for u in range(n_u):
                fila = tiempos[u]
                for i in clase:
                    if previo < fila[i] <= umbral:
                        aristas[(u, i)] = red.agregar_arista(1 + u, 1 + n_u + i, 1)
            previo = umbral
            flujo += red.maximizar(S, T)
    pares = [(u, i) for (u, i), e in aristas.items() if red.cap[e] == 0]
    return pares, flujo
