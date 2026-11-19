"""Generación de datos del Hito 2: bases, unidades e incidentes."""
from __future__ import annotations

import csv
import random
from pathlib import Path

from .domain import Base, Incidente, Unidad
from .graph_provider import GraphProvider
from .repository import Repositorio

TIPOLOGIAS = ["Robo en vía pública", "Disturbios en vía pública", "Persona sospechosa",
              "Vehículo abandonado", "Ruidos molestos", "Violencia familiar",
              "Accidente de tránsito", "Agresión física", "Robo a vivienda"]
# 94 unidades según el informe (la suma de cada tipo del acta del Congreso
# da 114 si se incluyen las 20 bicicletas; aquí se usan 25 + 19 + 50 = 94).
FLOTA = [("Camioneta", 25), ("Auto", 19), ("Moto", 50)]
NOMBRES_BASE = [("Base Norte", 0.30, 0.20), ("Base Centro", 0.50, 0.50),
                ("Base Sur", 0.70, 0.80)]


def _leer_dataset(ruta: str) -> list[tuple[str, str, str]]:
    """Lee el CSV de la MPC (columnas N_DE_CASO, TIPOLOGIA, DIRECCION)."""
    texto = Path(ruta).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if texto.splitlines()[0].count(";") > texto.splitlines()[0].count(",") else ","
    vistos, filas = set(), []
    for r in csv.DictReader(texto.splitlines(), delimiter=sep):
        caso, tip, dire = (r.get("N_DE_CASO") or "").strip(), \
            (r.get("TIPOLOGIA") or "").strip(), (r.get("DIRECCION") or "").strip()
        if caso and tip and dire and caso not in vistos:
            vistos.add(caso)
            filas.append((caso, tip, dire))
    return filas


def crear_repositorio(proveedor: GraphProvider, semilla: int = 42,
                      n_incidentes: int = 600, dataset_csv: str | None = None) -> Repositorio:
    rng = random.Random(semilla)
    lim = proveedor.limites()
    ancho, alto = lim["xmax"] - lim["xmin"], lim["ymax"] - lim["ymin"]

    bases = []
    for k, (nombre, fx, fy) in enumerate(NOMBRES_BASE):
        x, y = lim["xmin"] + fx * ancho, lim["ymin"] + fy * alto
        bases.append(Base(k, nombre, x, y, proveedor.ubicar(x, y, k=3)))

    tipos = [t for t, n in FLOTA for _ in range(n)]
    rng.shuffle(tipos)
    unidades = [Unidad(i + 1, t, i % len(bases)) for i, t in enumerate(tipos)]

    if dataset_csv:
        base = _leer_dataset(dataset_csv)
        muestra = rng.sample(base, min(n_incidentes, len(base)))
    else:  # datos sintéticos con la misma estructura
        muestra = [(f"{k + 1:04d}", rng.choice(TIPOLOGIAS),
                    f"Mz. {rng.choice('ABCDEFGHJK')} Lt. {rng.randint(1, 30)}")
                   for k in range(n_incidentes)]
    incidentes = []
    for caso, tip, dire in muestra:
        x, y = lim["xmin"] + rng.random() * ancho, lim["ymin"] + rng.random() * alto
        prio = rng.choices(["A", "M", "B"], weights=[20, 50, 30])[0]
        incidentes.append(Incidente(caso, tip, dire, prio, x, y, proveedor.ubicar(x, y, k=2)))
    return Repositorio(bases, unidades, incidentes, semilla=semilla)
