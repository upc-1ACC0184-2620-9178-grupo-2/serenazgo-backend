"""Infraestructura de Red vial: red real con OSMnx."""
from __future__ import annotations

import heapq
import math
import random

import networkx as nx

from app.network.domain.graph_provider import GraphProvider


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

    def contiene(self, x, y):
        lim = self.limites()
        return lim["xmin"] <= x <= lim["xmax"] and lim["ymin"] <= y <= lim["ymax"]

    def region(self):
        return None

    def anclaje(self):
        return None

    def nodo_mas_cercano(self, x, y):
        return self.ubicar(x, y)

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
