"""Infraestructura de Red vial: red simulada con NetworkX."""
from __future__ import annotations

import heapq
import math
import random

import networkx as nx

from app.network.domain.graph_provider import GraphProvider
from app.network.infrastructure.distrito_ventanilla import VENTANILLA


class SimulatedGraphProvider(GraphProvider):
    """Red vial simulada: intersecciones aleatorias unidas a sus 4 vecinas
    más cercanas. Tiempo de arista = distancia / velocidad (15-40 km/h),
    con un mínimo de 0,2 min (sección 2.3 del informe).

    Coordenadas en km sobre un plano local: x hacia el este, y hacia el sur, con origen en el centro del
    distrito. Por defecto las intersecciones se generan **solo dentro del distrito de Ventanilla**
    (`distrito`, polígono [lat, lng]); con `distrito=None` se usa un rectángulo de `ancho` × `alto` km."""

    def __init__(self, n_intersecciones: int = 900, ancho: float = 8.0,
                 alto: float = 5.0, vecinos: int = 4, semilla: int = 42,
                 distrito: list[tuple[float, float]] | None = VENTANILLA):
        self._rng = random.Random(semilla)
        self._anclaje = None
        self._poly: list[tuple[float, float]] | None = None
        if distrito:
            lats, lngs = [p[0] for p in distrito], [p[1] for p in distrito]
            lat0, lng0 = (min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2
            self._anclaje = (lat0, lng0)
            self._kml = 111.32 * math.cos(math.radians(abs(lat0)))
            self._poly = [self.a_plano(la, lo) for la, lo in distrito]
            xs, ys = [p[0] for p in self._poly], [p[1] for p in self._poly]
            self._bbox = (min(xs), max(xs), min(ys), max(ys))
        else:
            self._bbox = (0.0, ancho, 0.0, alto)
        self._ancho, self._alto = self._bbox[1] - self._bbox[0], self._bbox[3] - self._bbox[2]
        self._n = n_intersecciones
        self._k = vecinos
        self._G = nx.Graph()
        self._bloq: dict[tuple[int, int], dict] = {}
        self._ver = 0
        self._adj: list[list[tuple[int, float]]] | None = None
        self._adj_ver = -1
        self._adj_tr: dict[tuple[float, float], list[list[tuple[int, float]]]] = {}
        self._adj_tr_ver = -1
        self._construir()

    # --- construcción -----------------------------------------------------
    def _arista(self, a: int, b: int) -> dict:
        """Tiempo de libre circulación y tipo de vía: las rápidas (≥ 30 km/h) son avenidas."""
        (xa, ya), (xb, yb) = self._xy[a], self._xy[b]
        dist = math.hypot(xa - xb, ya - yb)
        vel = self._rng.uniform(15, 40)
        return {"tiempo": max(0.2, dist / vel * 60), "clase": "arterial" if vel >= 30 else "local"}

    def _cercanos(self, x: float, y: float, k: int, excluir: int | None = None):
        cand = (j for j in range(self._n) if j != excluir)
        return heapq.nsmallest(
            k, cand, key=lambda j: math.hypot(self._xy[j][0] - x, self._xy[j][1] - y))

    def _construir(self) -> None:
        r = self._rng
        x0, x1, y0, y1 = self._bbox
        self._xy = []
        while len(self._xy) < self._n:                 # solo puntos dentro del distrito
            x, y = r.uniform(x0, x1), r.uniform(y0, y1)
            if self.contiene(x, y):
                self._xy.append((x, y))
        for i in range(self._n):
            self._G.add_node(i)
        for i in range(self._n):
            for j in self._cercanos(*self._xy[i], self._k, excluir=i):
                if not self._G.has_edge(i, j):
                    self._G.add_edge(i, j, **self._arista(i, j))
        # Garantiza conectividad: une cada componente con la principal.
        comps = sorted(nx.connected_components(self._G), key=len, reverse=True)
        principal = set(comps[0])
        for c in comps[1:]:
            a, b = min(((a, b) for a in c for b in principal),
                       key=lambda p: math.hypot(self._xy[p[0]][0] - self._xy[p[1]][0],
                                                self._xy[p[0]][1] - self._xy[p[1]][1]))
            self._G.add_edge(a, b, **self._arista(a, b))
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

    def adyacencia_en(self, trafico):
        """Tiempos con el tráfico de la hora: avenidas y calles locales se congestionan distinto."""
        if self._adj_tr_ver != self._ver:
            self._adj_tr, self._adj_tr_ver = {}, self._ver
        clave = trafico.clave
        if clave not in self._adj_tr:
            f = {"arterial": trafico.arterial, "local": trafico.local}
            adj = [[] for _ in range(len(self._xy))]
            for a, b, d in self._G.edges(data=True):
                t = d["tiempo"] * f[d.get("clase", "local")]
                adj[a].append((b, t))
                adj[b].append((a, t))
            self._adj_tr[clave] = adj
        return self._adj_tr[clave]

    def aristas_viales(self):
        return [(a, b) for a, b in self._G.edges if a < self._n and b < self._n]

    def n_intersecciones(self):
        return self._n

    def n_aristas(self):
        return self._G.number_of_edges()

    def limites(self):
        x0, x1, y0, y1 = self._bbox
        return {"xmin": x0, "xmax": x1, "ymin": y0, "ymax": y1}

    # --- geografía del plano ---
    def a_plano(self, lat: float, lng: float) -> tuple[float, float]:
        """(lat, lng) -> (x este, y sur) en km desde el origen del plano."""
        lat0, lng0 = self._anclaje
        return (lng - lng0) * self._kml, (lat0 - lat) * 111.32

    def a_geo(self, x: float, y: float) -> tuple[float, float]:
        lat0, lng0 = self._anclaje
        return lat0 - y / 111.32, lng0 + x / self._kml

    def anclaje(self):
        return self._anclaje

    def region(self):
        return list(self._poly) if self._poly else None

    def contiene(self, x, y):
        if not self._poly:
            x0, x1, y0, y1 = self._bbox
            return x0 <= x <= x1 and y0 <= y <= y1
        dentro, n, j = False, len(self._poly), len(self._poly) - 1       # punto en polígono (rayo)
        for i in range(n):
            xi, yi = self._poly[i]
            xj, yj = self._poly[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                dentro = not dentro
            j = i
        return dentro

    def ubicar(self, x, y, k=2):
        idx = len(self._xy)
        self._xy.append((x, y))
        self._G.add_node(idx)
        for j in self._cercanos(x, y, k):
            self._G.add_edge(idx, j, **self._arista(idx, j))
        self._ver += 1
        return idx

    def nodo_mas_cercano(self, x, y):
        return self._cercanos(x, y, 1)[0]

    def bloquear_tramo(self, a, b):
        if not self._G.has_edge(a, b):
            return False
        self._bloq[(min(a, b), max(a, b))] = dict(self._G[a][b])
        self._G.remove_edge(a, b)
        self._ver += 1
        return True

    def restablecer(self):
        for (a, b), atributos in self._bloq.items():
            self._G.add_edge(a, b, **atributos)
        self._bloq.clear()
        self._ver += 1

    def bloqueados(self):
        return list(self._bloq)
