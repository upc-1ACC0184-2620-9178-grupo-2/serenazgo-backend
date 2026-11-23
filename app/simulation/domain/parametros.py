from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParametrosDeEscenario:
    """Parámetros del escenario del Hito 2."""
    semilla: int = 42
    n_incidentes: int = 600        # muestra de la MPC
    n_activos: int = 50            # incidentes activos por ciclo
    p_disponible: float = 0.45     # probabilidad de que una unidad esté disponible
    # 94 unidades (el acta del Congreso suma 114 si se incluyen 20 bicicletas)
    flota: tuple[tuple[str, int], ...] = (("Camioneta", 25), ("Auto", 19), ("Moto", 50))
    # nombres de las bases; se ubican en el norte, centro y sur de Ventanilla (sobre nodos de la red)
    bases: tuple[str, ...] = ("Base Norte", "Base Centro", "Base Sur")
    dataset_csv: str | None = None  # CSV real de la MPC (N_DE_CASO, TIPOLOGIA, DIRECCION)
