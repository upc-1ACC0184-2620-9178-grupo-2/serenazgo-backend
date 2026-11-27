"""Tráfico por horarios (hora de Lima): cuánto se alarga un viaje según la hora del día.

Se distinguen dos tipos de vía: las *avenidas* (arteriales, rápidas pero con mucho flujo) se congestionan más en
hora punta que las calles *locales*. El factor multiplica el tiempo de viaje de libre circulación.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# factor por hora del día (0-23): 1.0 = vía libre, 2.0 = el viaje tarda el doble
ARTERIAL = [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.4, 1.9, 2.0, 1.6, 1.35, 1.3,
            1.35, 1.4, 1.35, 1.4, 1.5, 1.9, 2.1, 2.0, 1.6, 1.3, 1.15, 1.05]
LOCAL = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.15, 1.35, 1.4, 1.2, 1.1, 1.1,
         1.15, 1.15, 1.1, 1.15, 1.2, 1.35, 1.4, 1.35, 1.2, 1.1, 1.05, 1.0]


@dataclass(frozen=True)
class Trafico:
    arterial: float = 1.0
    local: float = 1.0

    @property
    def clave(self) -> tuple[float, float]:
        return (round(self.arterial, 2), round(self.local, 2))

    @property
    def nivel(self) -> str:
        if self.arterial >= 1.8:
            return "hora punta"
        if self.arterial >= 1.35:
            return "intenso"
        if self.arterial >= 1.1:
            return "moderado"
        return "fluido"


LIBRE = Trafico()


def trafico_a_las(momento: datetime) -> Trafico:
    """Tráfico de la hora en que cae `momento` (constante dentro de cada hora)."""
    return Trafico(ARTERIAL[momento.hour], LOCAL[momento.hour])
