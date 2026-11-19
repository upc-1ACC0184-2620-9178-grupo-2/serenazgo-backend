"""Entidades del dominio (Tablas 1 y 2 del informe)."""
from __future__ import annotations

from dataclasses import dataclass

LETRAS = {"Camioneta": "C", "Auto": "A", "Moto": "M", "Bicicleta": "B"}


@dataclass
class Base:
    id: int
    nombre: str
    x: float
    y: float
    nodo: int = -1  # nodo de la base en G1


@dataclass
class Unidad:
    id: int
    tipo: str
    id_base: int
    disponible: bool = True
    incidente_asignado: str | None = None

    @property
    def etiqueta(self) -> str:
        return f"{self.tipo} {LETRAS[self.tipo]}-{self.id:02d}"


@dataclass
class Incidente:
    id_caso: str
    tipologia: str
    direccion: str
    prioridad: str  # "A" | "M" | "B"
    x: float
    y: float
    nodo_vial: int  # nodo del incidente en G1 (unido a sus intersecciones cercanas)
    estado: str = "inactivo"  # inactivo | activo | atendido
    orden: int = 0  # orden de llegada dentro del ciclo
