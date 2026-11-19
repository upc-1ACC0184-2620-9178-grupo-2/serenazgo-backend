"""Generación de la muestra de incidentes: dataset real de la MPC o datos sintéticos."""
from __future__ import annotations

import csv
import random
from pathlib import Path

from app.incidents.domain.catalogo import TIPOLOGIAS


def _leer_dataset(ruta: str) -> list[tuple[str, str, str]]:
    texto = Path(ruta).read_text(encoding="utf-8-sig", errors="replace")
    primera = texto.splitlines()[0]
    sep = ";" if primera.count(";") > primera.count(",") else ","
    vistos, filas = set(), []
    for r in csv.DictReader(texto.splitlines(), delimiter=sep):
        caso, tip, dire = ((r.get("N_DE_CASO") or "").strip(), (r.get("TIPOLOGIA") or "").strip(),
                           (r.get("DIRECCION") or "").strip())
        if caso and tip and dire and caso not in vistos:
            vistos.add(caso)
            filas.append((caso, tip, dire))
    return filas


def muestra_de_incidentes(rng: random.Random, n: int, dataset_csv: str | None):
    """Devuelve [(id_caso, tipologia, direccion)]."""
    if dataset_csv:
        base = _leer_dataset(dataset_csv)
        return rng.sample(base, min(n, len(base)))
    return [(f"{k + 1:04d}", rng.choice(TIPOLOGIAS),
             f"Mz. {rng.choice('ABCDEFGHJK')} Lt. {rng.randint(1, 30)}") for k in range(n)]
