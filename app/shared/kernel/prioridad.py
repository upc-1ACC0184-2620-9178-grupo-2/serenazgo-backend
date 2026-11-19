"""Prioridad de un incidente: concepto del Shared Kernel (lo usan incidentes y despacho)."""
from enum import Enum


class Prioridad(str, Enum):
    ALTA = "A"
    MEDIA = "M"
    BAJA = "B"

    @property
    def nivel(self) -> int:
        """0 = más urgente."""
        return {"A": 0, "M": 1, "B": 2}[self.value]

    @property
    def nombre(self) -> str:
        return {"A": "Alta", "M": "Media", "B": "Baja"}[self.value]
