"""Entidades del contexto Flota (Tabla 2 del informe)."""
from __future__ import annotations

from dataclasses import dataclass

from app.shared.kernel.errores import Conflicto

LETRAS = {"Camioneta": "C", "Auto": "A", "Moto": "M", "Bicicleta": "B"}


@dataclass(eq=False)
class Base:
    id: int
    nombre: str
    x: float
    y: float
    nodo: int  # nodo de la base en la red vial

    def a_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "x": round(self.x, 3), "y": round(self.y, 3)}


@dataclass(eq=False)
class Unidad:
    """Raíz de agregado: una unidad atiende un solo incidente a la vez."""
    id: int
    tipo: str
    id_base: int
    disponible: bool = True
    incidente_asignado: str | None = None

    @property
    def etiqueta(self) -> str:
        return f"{self.tipo} {LETRAS[self.tipo]}-{self.id:02d}"

    def ocupar(self, id_incidente: str) -> None:
        if not self.disponible:
            raise Conflicto(f"La unidad {self.id} no está disponible.")
        self.disponible = False
        self.incidente_asignado = id_incidente

    def cambiar_disponibilidad(self, disponible: bool) -> None:
        self.disponible = disponible
        if disponible:
            self.incidente_asignado = None

    def a_dict(self) -> dict:
        return {"id": self.id, "tipo": self.tipo, "id_base": self.id_base,
                "disponible": self.disponible, "incidente_asignado": self.incidente_asignado,
                "etiqueta": self.etiqueta}
