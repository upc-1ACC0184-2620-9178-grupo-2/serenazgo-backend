"""Raíz de agregado Incidente (Tabla 1 del informe)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.shared.kernel.errores import Conflicto
from app.shared.kernel.prioridad import Prioridad


class EstadoIncidente(str, Enum):
    INACTIVO = "inactivo"
    ACTIVO = "activo"
    ATENDIDO = "atendido"


@dataclass(eq=False)
class Incidente:
    id_caso: str
    tipologia: str
    direccion: str
    prioridad: Prioridad
    x: float
    y: float
    nodo_vial: int          # nodo del incidente en la red vial
    estado: EstadoIncidente = EstadoIncidente.INACTIVO
    orden: int = 0          # orden de llegada

    @classmethod
    def reportado(cls, numero: int, tipologia: str, direccion: str, prioridad: Prioridad,
                  x: float, y: float, nodo_vial: int, orden: int) -> "Incidente":
        return cls(f"N{numero:03d}", tipologia, direccion, prioridad, x, y, nodo_vial,
                   EstadoIncidente.ACTIVO, orden)

    @property
    def activo(self) -> bool:
        return self.estado == EstadoIncidente.ACTIVO

    def activar(self, orden: int) -> None:
        self.estado, self.orden = EstadoIncidente.ACTIVO, orden

    def desactivar(self) -> None:
        self.estado = EstadoIncidente.INACTIVO

    def marcar_atendido(self) -> None:
        if not self.activo:
            raise Conflicto(f"El incidente {self.id_caso} no está activo.")
        self.estado = EstadoIncidente.ATENDIDO

    def a_dict(self) -> dict:
        return {"id_caso": self.id_caso, "tipologia": self.tipologia, "direccion": self.direccion,
                "prioridad": self.prioridad.value, "x": self.x, "y": self.y,
                "nodo_vial": self.nodo_vial, "estado": self.estado.value, "orden": self.orden}
