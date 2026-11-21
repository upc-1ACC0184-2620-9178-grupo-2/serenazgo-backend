"""Problema de asignación (algoritmo húngaro / Kuhn-Munkres), O(n²·m)."""
from __future__ import annotations

INF = float("inf")


def asignacion_minima(costos: list[list[float]]) -> list[int]:
    """costos[i][j]: costo de asignar la fila i a la columna j (n filas <= m columnas).
    Devuelve, para cada fila, la columna asignada (costo total mínimo)."""
    n = len(costos)
    if n == 0:
        return []
    m = len(costos[0])
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        usado = [False] * (m + 1)
        while True:
            usado[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not usado[j]:
                    cur = costos[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if usado[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    res = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            res[p[j] - 1] = j - 1
    return res
