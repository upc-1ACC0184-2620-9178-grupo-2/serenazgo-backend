from __future__ import annotations

from dataclasses import dataclass

from app.shared.kernel.prioridad import Prioridad


@dataclass(frozen=True)
class PoliticaDePrioridad:
    """Value object: orden de clases, umbrales escalonados y tiempo máximo aceptable."""
    orden: tuple[Prioridad, ...] = (Prioridad.ALTA, Prioridad.MEDIA, Prioridad.BAJA)
    umbrales: tuple[float, ...] = (3.0, 5.0, 7.0, 9.0)
    tmax: float = 10.0
