"""Capa de datos: fuente del grafo vial G1 (RNF02).

Los algoritmos solo dependen de la interfaz GraphProvider, de modo que la red
simulada (NetworkX) puede sustituirse por la real (OSMnx) sin modificarlos.
"""
from __future__ import annotations

import heapq
import math
import random
from abc import ABC, abstractmethod

import networkx as nx


class GraphProvider(ABC):
    @property
    @abstractmethod
    def version(self) -> int:
        """Cambia cada vez que se modifica el grafo (invalida cachés)."""

    @abstractmethod
    def coordenadas(self) -> list[tuple[float, float]]: ...

    @abstractmethod
    def adyacencia(self) -> list[list[tuple[int, float]]]:
        """Lista de adyacencia [(vecino, tiempo_min), ...] por nodo."""

    @abstractmethod
    def aristas_viales(self) -> list[tuple[int, int]]:
        """Tramos de calle entre intersecciones (para dibujar el mapa)."""

    @abstractmethod
    def n_intersecciones(self) -> int: ...

    @abstractmethod
    def n_aristas(self) -> int: ...

    @abstractmethod
    def limites(self) -> dict: ...

    @abstractmethod
    def ubicar(self, x: float, y: float, k: int = 2) -> int:
        """Ubica un punto (base o incidente) en la red y devuelve su nodo."""

    @abstractmethod
    def bloquear_tramo(self, a: int, b: int) -> bool: ...

    @abstractmethod
    def restablecer(self) -> None: ...

    @abstractmethod
    def bloqueados(self) -> list[tuple[int, int]]: ...

    def n_nodos(self) -> int:
        return len(self.coordenadas())


class SimulatedGraphProvider(GraphProvider):
    """Red vial simulada: intersecciones aleatorias unidas a sus 4 vecinas
    más cercanas. Tiempo de arista = distancia / velocidad (15-40 km/h),
    con un mínimo de 0,2 min (sección 2.3 del informe). Coordenadas en km."""

    def __init__(self, n_intersecciones: int = 900, ancho: float = 8.0,
                 alto: float = 5.0, vecinos: int = 4, semilla: int = 42):
        self._rng = random.Random(semilla)
        self._ancho, self._alto = ancho, alto
        self._n = n_intersecciones
        self._k = vecinos
        self._G = nx.Graph()
        self._bloq: dict[tuple[int, int], float] = {}
        self._ver = 0
        self._adj: list[list[tuple[int, float]]] | None = None
        self._adj_ver = -1
        self._construir()

    # --- construcción -----------------------------------------------------
    def _tiempo(self, a: int, b: int) -> float:
        (xa, ya), (xb, yb) = self._xy[a], self._xy[b]
        dist = math.hypot(xa - xb, ya - yb)
        vel = self._rng.uniform(15, 40)
        return max(0.2, dist / vel * 60)

    def _cercanos(self, x: float, y: float, k: int, excluir: int | None = None):
        cand = (j for j in range(self._n) if j != excluir)
        return heapq.nsmallest(
            k, cand, key=lambda j: math.hypot(self._xy[j][0] - x, self._xy[j][1] - y))

    def _construir(self) -> None:
        r = self._rng
        self._xy = [(r.uniform(0, self._ancho), r.uniform(0, self._alto))
                    for _ in range(self._n)]
        for i in range(self._n):
            self._G.add_node(i)
        for i in range(self._n):
            for j in self._cercanos(*self._xy[i], self._k, excluir=i):
                if not self._G.has_edge(i, j):
                    self._G.add_edge(i, j, tiempo=self._tiempo(i, j))
        # Garantiza conectividad: une cada componente con la principal.
        comps = sorted(nx.connected_components(self._G), key=len, reverse=True)
        principal = set(comps[0])
        for c in comps[1:]:
            a, b = min(((a, b) for a in c for b in principal),
                       key=lambda p: math.hypot(self._xy[p[0]][0] - self._xy[p[1]][0],
                                                self._xy[p[0]][1] - self._xy[p[1]][1]))
            self._G.add_edge(a, b, tiempo=self._tiempo(a, b))
            principal |= set(c)

    # --- interfaz ---------------------------------------------------------
    @property
    def version(self) -> int:
        return self._ver

    @property
    def grafo(self) -> nx.Graph:
        return self._G

    def coordenadas(self):
        return self._xy

    def adyacencia(self):
        if self._adj is None or self._adj_ver != self._ver:
            adj = [[] for _ in range(len(self._xy))]
            for a, b, d in self._G.edges(data=True):
                adj[a].append((b, d["tiempo"]))
                adj[b].append((a, d["tiempo"]))
            self._adj, self._adj_ver = adj, self._ver
        return self._adj

    def aristas_viales(self):
        return [(a, b) for a, b in self._G.edges if a < self._n and b < self._n]

    def n_intersecciones(self):
        return self._n

    def n_aristas(self):
        return self._G.number_of_edges()

    def limites(self):
        return {"xmin": 0.0, "xmax": self._ancho, "ymin": 0.0, "ymax": self._alto}

    def ubicar(self, x, y, k=2):
        idx = len(self._xy)
        self._xy.append((x, y))
        self._G.add_node(idx)
        for j in self._cercanos(x, y, k):
            self._G.add_edge(idx, j, tiempo=self._tiempo(idx, j))
        self._ver += 1
        return idx

    def bloquear_tramo(self, a, b):
        if not self._G.has_edge(a, b):
            return False
        self._bloq[(min(a, b), max(a, b))] = self._G[a][b]["tiempo"]
        self._G.remove_edge(a, b)
        self._ver += 1
        return True

    def restablecer(self):
        for (a, b), t in self._bloq.items():
            self._G.add_edge(a, b, tiempo=t)
        self._bloq.clear()
        self._ver += 1

    def bloqueados(self):
        return list(self._bloq)


class OsmnxGraphProvider(GraphProvider):
    """Red vial real de OpenStreetMap (Boeing, 2017). SIN PROBAR: requiere
    `pip install osmnx` y conexión a internet. Se usa con RED=osmnx.

    Las coordenadas se guardan como (lon, -lat) para que el eje y crezca hacia
    abajo, igual que en la red simulada. Los puntos se ajustan al nodo más
    cercano de la red (no se crean nodos nuevos)."""

    def __init__(self, lugar: str = "Ventanilla, Callao, Peru"):
        import osmnx as ox  # import perezoso: dependencia opcional

        gm = ox.graph_from_place(lugar, network_type="drive")
        gm = ox.add_edge_speeds(gm)
        gm = ox.add_edge_travel_times(gm)
        g = nx.Graph()
        for n, d in gm.nodes(data=True):
            g.add_node(n, x=d["x"], y=-d["y"])
        for u, v, d in gm.edges(data=True):
            t = d["travel_time"] / 60.0
            if not g.has_edge(u, v) or t < g[u][v]["tiempo"]:
                g.add_edge(u, v, tiempo=t)
        self._G = nx.convert_node_labels_to_integers(g)
        self._xy = [(self._G.nodes[i]["x"], self._G.nodes[i]["y"])
                    for i in range(self._G.number_of_nodes())]
        self._bloq: dict[tuple[int, int], float] = {}
        self._ver = 0
        self._adj, self._adj_ver = None, -1

    @property
    def version(self): return self._ver
    def coordenadas(self): return self._xy
    def n_intersecciones(self): return len(self._xy)
    def n_aristas(self): return self._G.number_of_edges()
    def aristas_viales(self): return list(self._G.edges)
    def bloqueados(self): return list(self._bloq)

    def limites(self):
        xs, ys = zip(*self._xy)
        return {"xmin": min(xs), "xmax": max(xs), "ymin": min(ys), "ymax": max(ys)}

    def adyacencia(self):
        if self._adj is None or self._adj_ver != self._ver:
            adj = [[] for _ in self._xy]
            for a, b, d in self._G.edges(data=True):
                adj[a].append((b, d["tiempo"]))
                adj[b].append((a, d["tiempo"]))
            self._adj, self._adj_ver = adj, self._ver
        return self._adj

    def ubicar(self, x, y, k=2):
        return min(range(len(self._xy)),
                   key=lambda j: (self._xy[j][0] - x) ** 2 + (self._xy[j][1] - y) ** 2)

    def bloquear_tramo(self, a, b):
        if not self._G.has_edge(a, b):
            return False
        self._bloq[(min(a, b), max(a, b))] = self._G[a][b]["tiempo"]
        self._G.remove_edge(a, b)
        self._ver += 1
        return True

    def restablecer(self):
        for (a, b), t in self._bloq.items():
            self._G.add_edge(a, b, tiempo=t)
        self._bloq.clear()
        self._ver += 1
